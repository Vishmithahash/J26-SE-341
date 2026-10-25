"""Controlled-defect lab: a disposable NexaCart copy with one seeded defect on a local port.

Component: C1 - Explainable Tool-Call Correctness Testing

The proposal evaluates code-level diagnosis and correction on controlled defects introduced into
permitted code areas (argument mapping). The lab builds such a copy with its own database
(``nexacart_sandbox``), starts it as a separate local NexaCart process, and a C1 configuration
imported "from the lab" targets it. The developer's NexaCart tree, database and main instance are
never changed. Lab results are labelled as controlled-defect evidence.

Labs survive a QA backend restart: their state is kept in ``labs.json`` next to the copies and the
NexaCart process runs in its own process group. On the next access a lab whose process is still
healthy is re-adopted, one whose process died is restarted from its build, and one interrupted
while building is marked FAILED and cleaned up.
"""

import asyncio
import json
import threading
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.components.c1_tool_call_correctness.services import nexacart_correction
from app.components.c1_tool_call_correctness.services.nexacart_correction import (
    BUILD_TIMEOUT_SECONDS,
    CONTROLLED_DEFECTS,
    NexaCartInstance,
    create_workspace,
    free_port,
    node_command,
    remove_workspace,
    run_command,
    seed_defect,
)
from app.components.c1_tool_call_correctness.services.nexacart_sandbox import (
    provision_database,
)

ACTIVE_STATUSES = ("BUILDING", "RUNNING")


@dataclass
class DefectLab:
    project_id: str
    defect_id: str
    status: str = "BUILDING"  # BUILDING, RUNNING, FAILED, STOPPED
    message: str = "Creating the disposable NexaCart copy."
    workspace: str | None = None
    port: int | None = None
    base_url: str | None = None
    pid: int | None = None
    sandbox_database: str | None = None
    seeding_diff: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    recovered_at: str | None = None

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("pid", None)
        defect = CONTROLLED_DEFECTS.get(self.defect_id)
        data["defect"] = {
            "defect_id": self.defect_id,
            "description": defect.description if defect else "",
            "tool_name": defect.tool_name if defect else "",
            "file_path": defect.file_path if defect else "",
        }
        return data


_LABS: dict[str, DefectLab] = {}
_LOCK = threading.RLock()
_LOADED = False


def _registry_path() -> Path:
    return nexacart_correction.WORKSPACE_ROOT / "labs.json"


def _save() -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({pid: asdict(lab) for pid, lab in _LABS.items()}, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def _load() -> None:
    """Read the registry once per process and reconcile it with what is really running."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    path = _registry_path()
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    names = {f.name for f in fields(DefectLab)}
    for project_id, raw in data.items():
        _LABS[project_id] = DefectLab(**{k: v for k, v in raw.items() if k in names})
    for lab in _LABS.values():
        _reconcile(lab)
    _save()


def _reconcile(lab: DefectLab) -> None:
    """Bring a lab loaded from the registry in line with the processes that actually exist."""
    workspace = Path(lab.workspace) if lab.workspace else None
    now = datetime.now(UTC).isoformat()
    if lab.status == "BUILDING":
        # The build ran inside the QA backend that restarted; it cannot be resumed.
        if workspace is not None:
            remove_workspace(workspace)
        lab.status = "FAILED"
        lab.message = (
            "The QA backend restarted while this lab was building; start it again."
        )
        lab.pid = None
        return
    if lab.status != "RUNNING" or workspace is None or lab.port is None:
        return
    instance = NexaCartInstance(workspace, lab.port, lab.pid)
    if instance.is_alive() and instance.is_healthy():
        lab.recovered_at = now
        lab.message = f"Re-adopted after a QA backend restart: seeded NexaCart still running at {lab.base_url}."
        return
    if (workspace / "dist" / "src" / "main.js").is_file():
        instance.stop()
        instance.start()
        if instance.wait_healthy():
            lab.pid = instance.pid
            lab.recovered_at = now
            lab.message = (
                f"Restarted after a QA backend restart: seeded NexaCart running again at "
                f"{lab.base_url} (same copy and sandbox database)."
            )
            return
        instance.stop()
    remove_workspace(workspace)
    lab.status, lab.pid = "FAILED", None
    lab.message = (
        "The lab process could not be recovered after a restart; its copy was removed."
    )


def available_defects() -> list[dict[str, str]]:
    return [
        {
            "defect_id": d.defect_id,
            "tool_name": d.tool_name,
            "file_path": d.file_path,
            "description": d.description,
        }
        for d in CONTROLLED_DEFECTS.values()
    ]


def get_lab(project_id: str) -> DefectLab | None:
    with _LOCK:
        _load()
        return _LABS.get(project_id)


def begin_lab(project_id: str, defect_id: str) -> DefectLab:
    if defect_id not in CONTROLLED_DEFECTS:
        raise ValueError(f"Unknown controlled defect '{defect_id}'.")
    with _LOCK:
        _load()
        current = _LABS.get(project_id)
        if current is not None and current.status in ACTIVE_STATUSES:
            raise ValueError(
                "A defect lab is already active for this project; stop it first."
            )
        lab = DefectLab(project_id=project_id, defect_id=defect_id)
        _LABS[project_id] = lab
        _save()
        return lab


def _update(lab: DefectLab, **changes: Any) -> None:
    with _LOCK:
        for key, value in changes.items():
            setattr(lab, key, value)
        _save()


async def build_lab(lab: DefectLab, source_root: Path) -> None:
    """Background job: copy, seed the defect, create the sandbox database, build and start."""
    defect = CONTROLLED_DEFECTS[lab.defect_id]
    try:
        workspace = create_workspace(source_root, f"lab-{lab.defect_id}")
        _update(
            lab, workspace=str(workspace), seeding_diff=seed_defect(workspace, defect)
        )
        _update(lab, message="Creating the lab's own database (migrations + seed).")
        database = await provision_database(workspace)
        _update(
            lab,
            sandbox_database=database,
            message="Building the seeded copy (nest build).",
        )
        code, output, _ = await run_command(
            workspace,
            node_command(workspace, "@nestjs/cli/bin/nest.js", "build"),
            BUILD_TIMEOUT_SECONDS,
        )
        if code != 0:
            _update(lab, status="FAILED", message=f"Build failed: {output[-600:]}")
            return
        port = free_port()
        instance = NexaCartInstance(workspace, port)
        instance.start()
        if not await asyncio.to_thread(instance.wait_healthy):
            instance.stop()
            _update(
                lab,
                status="FAILED",
                message=f"Seeded NexaCart did not start on port {port}.",
            )
            return
        _update(
            lab,
            port=port,
            base_url=instance.base_url,
            pid=instance.pid,
            status="RUNNING",
            message=(
                f"Seeded NexaCart running at {instance.base_url} with controlled defect "
                f"'{defect.defect_id}' and its own database '{database}'. Import a C1 "
                "configuration from the lab to test it."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        _update(lab, status="FAILED", message=f"Defect lab failed: {exc}")


def stop_lab(project_id: str) -> DefectLab | None:
    with _LOCK:
        _load()
        lab = _LABS.get(project_id)
        if lab is None:
            return None
        if lab.workspace:
            NexaCartInstance(Path(lab.workspace), lab.port or 0, lab.pid).stop()
            remove_workspace(Path(lab.workspace))
        lab.status, lab.pid = "STOPPED", None
        lab.message = (
            "Defect lab stopped; its process, copy and sandbox database were removed."
        )
        _save()
        return lab
