"""Isolation of disposable NexaCart copies without containers (monolithic deployment).

Component: C1 - Explainable Tool-Call Correctness Testing

Owner decision (session 7): no Docker. A disposable copy is isolated at the process and data
level instead:

- **Own database.** Every copy gets a fresh PostgreSQL database (``nxc_c1_sbx_*``) on the local
  server, created from NexaCart's own migrations and seed. Lab fixtures, agent runs, refunds and
  verification reruns are written there, never into the developer's ``nexacart`` database. The
  database is dropped with the copy.
- **Own process.** The copy runs as a separate Node process on its own port, in its own process
  group, with an environment stripped of the QA backend's variables and secrets (NexaCart reads
  its settings from the copy's ``.env``).
- **Own files.** Commands run with the copy as working directory; the developer's tree is only read.

Process handles are plain PIDs so a lab can be re-adopted after the QA backend restarts.
"""

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from app.components.c1_tool_call_correctness.services.sandbox_interface import (
    STRIPPED_ENV_PATTERNS,
)

SANDBOX_DB_PREFIX = "nxc_c1_sbx_"
MARKER_FILE = ".c1-sandbox.json"
DB_STEP_TIMEOUT_SECONDS = 300.0
IS_WINDOWS = sys.platform.startswith("win")


# -- environment ------------------------------------------------------------------


def read_env_file(workspace: Path) -> dict[str, str]:
    env_file = workspace / ".env"
    values: dict[str, str] = {}
    if not env_file.is_file():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def set_env_value(workspace: Path, key: str, value: str) -> None:
    env_file = workspace / ".env"
    lines = (
        env_file.read_text(encoding="utf-8").splitlines() if env_file.is_file() else []
    )
    replaced = False
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key and not line.lstrip().startswith("#"):
            lines[i] = f'{key}="{value}"'
            replaced = True
    if not replaced:
        lines.append(f'{key}="{value}"')
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def isolated_environment(
    workspace: Path, extra: dict[str, str] | None = None
) -> dict[str, str]:
    """Inherited environment minus QA-backend secrets and every key NexaCart's .env defines.

    NexaCart's ConfigModule lets process variables override its .env file, so anything inherited
    from the QA backend (its DATABASE_URL, NEXACART_* credentials, API keys) must not leak in.
    """
    own_keys = set(read_env_file(workspace))
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in own_keys
        and k != "DATABASE_URL"
        and not k.startswith("NEXACART_")
        and not any(re.search(p, k, re.IGNORECASE) for p in STRIPPED_ENV_PATTERNS)
    }
    env.update(extra or {})
    return env


async def run_isolated(
    workspace: Path,
    command: list[str],
    timeout_seconds: float,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run a fixed command in the copy with the isolated environment."""
    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(workspace),
        env=isolated_environment(workspace, extra_env),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return -9, f"Timed out after {timeout_seconds}s."
    return proc.returncode or 0, out.decode("utf-8", errors="replace")[-4000:]


# -- dedicated database ----------------------------------------------------------------


def _database_name(workspace: Path) -> str:
    suffix = re.sub(r"[^a-z0-9_]", "_", workspace.name.lower())[-40:]
    return f"{SANDBOX_DB_PREFIX}{suffix}"


def _admin_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    return parsed._replace(path="/postgres", query="").geturl()


def sandbox_database(workspace: Path) -> str | None:
    marker = workspace / MARKER_FILE
    if not marker.is_file():
        return None
    return json.loads(marker.read_text(encoding="utf-8")).get("database")


async def provision_database(workspace: Path) -> str:
    """Create, migrate and seed a dedicated database for the copy; returns its name."""
    import psycopg

    source_url = read_env_file(workspace).get("DATABASE_URL")
    if not source_url:
        raise RuntimeError("The NexaCart copy has no DATABASE_URL in its .env.")
    parsed = urlparse(source_url)
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError(
            "Sandbox databases are only created on a local PostgreSQL server."
        )
    name = _database_name(workspace)
    with psycopg.connect(_admin_url(source_url), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')
    (workspace / MARKER_FILE).write_text(
        json.dumps({"database": name}), encoding="utf-8"
    )
    sandbox_url = parsed._replace(path=f"/{name}").geturl()
    set_env_value(workspace, "DATABASE_URL", sandbox_url)
    modules = workspace / "node_modules"
    for label, command in (
        (
            "migrate",
            ["node", str(modules / "prisma/build/index.js"), "migrate", "deploy"],
        ),
        ("seed", ["node", str(modules / "tsx/dist/cli.mjs"), "prisma/seed.ts"]),
    ):
        code, output = await run_isolated(
            workspace, command, DB_STEP_TIMEOUT_SECONDS, {"DATABASE_URL": sandbox_url}
        )
        if code != 0:
            raise RuntimeError(
                f"Sandbox database {label} failed (exit {code}): {output[-600:]}"
            )
    return name


def drop_database(workspace: Path) -> None:
    """Drop the copy's dedicated database (only names this module created)."""
    import psycopg

    name = sandbox_database(workspace)
    url = read_env_file(workspace).get("DATABASE_URL")
    if not name or not url or not name.startswith(SANDBOX_DB_PREFIX):
        return
    try:
        with psycopg.connect(_admin_url(url), autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    except psycopg.Error:
        pass  # the copy is removed regardless; a leftover database keeps its sandbox prefix


# -- processes ------------------------------------------------------------------------


def start_detached(
    workspace: Path, command: list[str], env: dict[str, str], log_path: Path
) -> int:
    """Start a process that outlives the QA backend (own process group); returns its PID."""
    log = log_path.open("w", encoding="utf-8")
    kwargs: dict = {
        "cwd": str(workspace),
        "env": env,
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    return process.pid


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if IS_WINDOWS:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_pid(pid: int | None, timeout: float = 15.0) -> None:
    if not pid or not pid_alive(pid):
        return
    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and pid_alive(pid):
            time.sleep(0.5)
        if pid_alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGKILL)
