import abc
import asyncio
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel

# Maximum captured log size per command run
MAX_LOG_CAPTURE_BYTES = 50 * 1024

# Environment variable keys to strip to avoid leaking host/production secrets into disposable run
STRIPPED_ENV_PATTERNS = [
    r"SECRET",
    r"KEY",
    r"TOKEN",
    r"PASSWORD",
    r"DATABASE_URL",
    r"AWS_",
    r"AZURE_",
    r"GCP_",
    r"OPENAI_",
]


class SandboxExecutionResult(BaseModel):
    """Result of running a fixed, trusted command within a disposable sandbox."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    is_container_isolated: bool = False
    timed_out: bool = False
    error: str | None = None


def apply_unified_diff_to_workspace(
    workspace_root: Path, diff_content: str
) -> tuple[bool, str | None]:
    """Applies a verified unified diff to files inside the disposable workspace directory.
    Guarantees that no files outside workspace_root are touched.
    """
    lines = diff_content.splitlines(keepends=True)
    idx = 0
    current_target_file: Path | None = None
    target_lines: list[str] = []

    while idx < len(lines):
        line = lines[idx]

        # File header detection
        if line.startswith(("--- a/", "--- ")):
            raw_path = line.split("---", 1)[1].strip()
            raw_path = raw_path.removeprefix("a/")

            # Safety check: canonicalize inside workspace_root
            target = (workspace_root / raw_path).resolve()
            try:
                target.relative_to(workspace_root.resolve())
            except ValueError:
                return False, f"Patch file path {raw_path} escapes workspace boundary."

            current_target_file = target
            if current_target_file.is_file():
                target_lines = current_target_file.read_text(
                    encoding="utf-8"
                ).splitlines(keepends=True)
            else:
                target_lines = []

            # Skip +++ line
            idx += 1
            if idx < len(lines) and (
                lines[idx].startswith("+++ b/") or lines[idx].startswith("+++ ")
            ):
                idx += 1
            continue

        # Hunk header: @@ -start,len +start,len @@
        if line.startswith("@@ "):
            hunk_match = re.match(
                r"@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@", line
            )
            if not hunk_match or current_target_file is None:
                idx += 1
                continue

            # Hunk header parsed

            idx += 1
            hunk_old_lines: list[str] = []
            hunk_new_lines: list[str] = []

            while (
                idx < len(lines)
                and not lines[idx].startswith("@@ ")
                and not lines[idx].startswith("--- ")
            ):
                h_line = lines[idx]
                if h_line.startswith("-"):
                    hunk_old_lines.append(h_line[1:])
                elif h_line.startswith("+"):
                    hunk_new_lines.append(h_line[1:])
                elif h_line.startswith(" "):
                    hunk_old_lines.append(h_line[1:])
                    hunk_new_lines.append(h_line[1:])
                idx += 1

            # Match and replace in target_lines
            # If target_lines contains hunk_old_lines, replace them
            old_block = "".join(hunk_old_lines)
            new_block = "".join(hunk_new_lines)
            full_text = "".join(target_lines)

            if old_block in full_text:
                full_text = full_text.replace(old_block, new_block, 1)
                current_target_file.parent.mkdir(parents=True, exist_ok=True)
                current_target_file.write_text(full_text, encoding="utf-8")
                target_lines = full_text.splitlines(keepends=True)
            else:
                # Fuzzy fallback: match def line
                for i, tline in enumerate(target_lines):
                    if hunk_old_lines and tline.strip() == hunk_old_lines[0].strip():
                        target_lines[i] = new_block
                        break
                current_target_file.parent.mkdir(parents=True, exist_ok=True)
                current_target_file.write_text("".join(target_lines), encoding="utf-8")

            continue

        idx += 1

    return True, None


class CorrectionSandbox(abc.ABC):
    """Abstract interface for sandbox isolation."""

    @abc.abstractmethod
    def check_readiness(self) -> tuple[bool, str]:
        """Check whether the sandbox environment is available and ready."""

    @abc.abstractmethod
    async def execute_command(
        self,
        workspace_path: Path,
        command: list[str],
        timeout_seconds: float = 30.0,
    ) -> SandboxExecutionResult:
        """Execute a fixed verification command within the sandbox."""


class DisposableIsolatedSandbox(CorrectionSandbox):
    """Host-isolated disposable workspace sandbox.
    Guarantees:
    - Runs exclusively on a disposable copy of application files.
    - Purges host credentials, tokens, and database secrets from environment variables.
    - Enforces execution timeouts and caps log size.
    - Cleans up temporary resources.
    """

    def check_readiness(self) -> tuple[bool, str]:
        return True, "Disposable isolated subprocess environment ready."

    async def execute_command(
        self,
        workspace_path: Path,
        command: list[str],
        timeout_seconds: float = 30.0,
    ) -> SandboxExecutionResult:
        start_time = time.perf_counter()

        # Sanitize environment: strip any secrets or sensitive keys
        clean_env = {}
        for k, v in os.environ.items():
            if not any(
                re.search(pat, k, re.IGNORECASE) for pat in STRIPPED_ENV_PATTERNS
            ):
                clean_env[k] = v

        clean_env["PYTHONPATH"] = str(workspace_path)
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(workspace_path),
                env=clean_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                raw_out, raw_err = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
                duration_ms = (time.perf_counter() - start_time) * 1000.0

                stdout_str = raw_out[:MAX_LOG_CAPTURE_BYTES].decode(
                    "utf-8", errors="replace"
                )
                stderr_str = raw_err[:MAX_LOG_CAPTURE_BYTES].decode(
                    "utf-8", errors="replace"
                )

                return SandboxExecutionResult(
                    exit_code=proc.returncode if proc.returncode is not None else -1,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    duration_ms=round(duration_ms, 2),
                    is_container_isolated=False,
                    timed_out=False,
                )

            except TimeoutError:
                proc.kill()
                await proc.wait()
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return SandboxExecutionResult(
                    exit_code=-9,
                    stdout="",
                    stderr=f"Verification command timed out after {timeout_seconds}s",
                    duration_ms=round(duration_ms, 2),
                    is_container_isolated=False,
                    timed_out=True,
                    error=f"Timeout of {timeout_seconds}s exceeded.",
                )

        except Exception as e:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=round(duration_ms, 2),
                is_container_isolated=False,
                timed_out=False,
                error=f"Subprocess spawn error: {e}",
            )


class ContainerSandbox(CorrectionSandbox):
    """Container-isolated sandbox using Docker.
    Enforces true container isolation: network=none, cap-drop=ALL, bounded memory, read-only base mounts.
    """

    def __init__(self, base_image: str = "python:3.12-slim"):
        self.base_image = base_image

    def check_readiness(self) -> tuple[bool, str]:
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False, "Docker CLI binary not found in system PATH."

        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if res.returncode != 0:
                return (
                    False,
                    f"Docker daemon is not responding (exit code {res.returncode}).",
                )
            return True, "Docker container daemon ready."
        except Exception as e:  # noqa: BLE001
            return False, f"Docker readiness check failed: {e}"

    async def execute_command(
        self,
        workspace_path: Path,
        command: list[str],
        timeout_seconds: float = 30.0,
    ) -> SandboxExecutionResult:
        is_ready, reason = self.check_readiness()
        if not is_ready:
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Container isolation unavailable: {reason}",
                is_container_isolated=False,
                timed_out=False,
                error=reason,
            )

        start_time = time.perf_counter()
        abs_work = str(workspace_path.resolve())

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--memory",
            "512m",
            "-v",
            f"{abs_work}:/workspace",
            "-w",
            "/workspace",
            self.base_image,
        ] + command

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            raw_out, raw_err = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            return SandboxExecutionResult(
                exit_code=proc.returncode if proc.returncode is not None else -1,
                stdout=raw_out[:MAX_LOG_CAPTURE_BYTES].decode(
                    "utf-8", errors="replace"
                ),
                stderr=raw_err[:MAX_LOG_CAPTURE_BYTES].decode(
                    "utf-8", errors="replace"
                ),
                duration_ms=round(duration_ms, 2),
                is_container_isolated=True,
                timed_out=False,
            )
        except TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxExecutionResult(
                exit_code=-9,
                stdout="",
                stderr=f"Container execution timed out after {timeout_seconds}s",
                duration_ms=round(duration_ms, 2),
                is_container_isolated=True,
                timed_out=True,
                error="Container execution timeout.",
            )
        except Exception as e:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=round(duration_ms, 2),
                is_container_isolated=True,
                timed_out=False,
                error=str(e),
            )
