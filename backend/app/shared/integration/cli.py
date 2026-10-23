"""Developer CLI for Cross-Component Shared Integration Execution.

Component: Shared Integration Coordination (Part 2)
Usage:
    python -m app.shared.integration.cli execute --project-id <id> --plan-id <id> [--target-mode CONTROLLED_TEST|LIVE_AUT]
    python -m app.shared.integration.cli status --project-id <id> --plan-id <id> --execution-id <id>
    python -m app.shared.integration.cli list --project-id <id> --plan-id <id>
    python -m app.shared.integration.cli cancel --project-id <id> --plan-id <id> --execution-id <id>
"""

import argparse
import json
import sys
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.shared.auth.models import User
from app.shared.integration.contracts import ExecutionStartRequest
from app.shared.integration.executor import SharedExecutionCoordinator
from app.shared.projects.models import Project


def get_admin_user(db: Any) -> User:
    """Find or create a local admin user for developer CLI operations."""
    user = db.execute(select(User).where(User.role == "ADMIN")).scalars().first()
    if not user:
        user = db.execute(select(User)).scalars().first()
    if not user:
        user = User(
            id=1,
            email="cli_admin@test.local",
            name="CLI Admin",
            role="ADMIN",
            is_active=True,
        )
    return user


def get_cli_project(db: Any, project_id: str) -> Project:
    """Retrieve authorized project for CLI."""
    proj = (
        db.execute(select(Project).where(Project.project_id == project_id))
        .scalars()
        .first()
    )
    if not proj:
        proj = Project(
            project_id=project_id,
            name=f"CLI Project {project_id}",
            description="Project initialized via developer CLI",
            owner_user_id=1,
            backend_base_url="http://localhost:8000",
            backend_health_url="http://localhost:8000/health",
        )
        db.add(proj)
        db.commit()
        db.refresh(proj)
    return proj


def handle_execute(args: argparse.Namespace) -> int:
    provided_db = getattr(args, "db", None)
    db = provided_db or SessionLocal()
    try:
        user = get_admin_user(db)
        project = get_cli_project(db, args.project_id)
        coordinator = SharedExecutionCoordinator(db)

        request = ExecutionStartRequest(
            target_mode=args.target_mode,
            timeout_seconds=args.timeout,
            max_tool_calls=args.max_tool_calls,
            task_prompt_override=args.prompt,
        )
        res = coordinator.execute_plan(
            project=project,
            user=user,
            plan_identifier=args.plan_id,
            request=request,
        )
        print(json.dumps(res.model_dump(mode="json"), indent=2))
        return 0 if res.lifecycle_status == "COMPLETED" else 1
    except Exception as exc:  # noqa: BLE001
        print(f"CLI Execution Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if provided_db is None:
            db.close()


def handle_status(args: argparse.Namespace) -> int:
    provided_db = getattr(args, "db", None)
    db = provided_db or SessionLocal()
    try:
        project = get_cli_project(db, args.project_id)
        coordinator = SharedExecutionCoordinator(db)
        res = coordinator.get_execution(project, args.plan_id, args.execution_id)
        print(json.dumps(res.model_dump(mode="json"), indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"CLI Status Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if provided_db is None:
            db.close()


def handle_list(args: argparse.Namespace) -> int:
    provided_db = getattr(args, "db", None)
    db = provided_db or SessionLocal()
    try:
        project = get_cli_project(db, args.project_id)
        coordinator = SharedExecutionCoordinator(db)
        res = coordinator.list_executions(project, args.plan_id)
        print(json.dumps(res.model_dump(mode="json"), indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"CLI List Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if provided_db is None:
            db.close()


def handle_cancel(args: argparse.Namespace) -> int:
    provided_db = getattr(args, "db", None)
    db = provided_db or SessionLocal()
    try:
        project = get_cli_project(db, args.project_id)
        coordinator = SharedExecutionCoordinator(db)
        res = coordinator.cancel_execution(project, args.plan_id, args.execution_id)
        print(json.dumps(res.model_dump(mode="json"), indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"CLI Cancel Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if provided_db is None:
            db.close()


def main(argv: list[str] | None = None, db: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description="Developer CLI for Cross-Component Shared Integration Execution"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Execute
    exec_parser = subparsers.add_parser(
        "execute", help="Execute an integration run plan"
    )
    exec_parser.add_argument(
        "--project-id", required=True, help="Target project identifier"
    )
    exec_parser.add_argument(
        "--plan-id", required=True, help="Run plan UUID or irun identifier"
    )
    exec_parser.add_argument(
        "--target-mode",
        choices=["CONTROLLED_TEST", "LIVE_AUT"],
        default="CONTROLLED_TEST",
        help="Target execution adapter mode",
    )
    exec_parser.add_argument(
        "--timeout", type=int, default=60, help="Timeout in seconds"
    )
    exec_parser.add_argument(
        "--max-tool-calls", type=int, default=50, help="Max tool calls budget"
    )
    exec_parser.add_argument(
        "--prompt", type=str, default=None, help="Optional task prompt override"
    )
    exec_parser.set_defaults(func=handle_execute)

    # Status
    status_parser = subparsers.add_parser("status", help="Get status of an execution")
    status_parser.add_argument("--project-id", required=True, help="Project ID")
    status_parser.add_argument("--plan-id", required=True, help="Run plan ID")
    status_parser.add_argument(
        "--execution-id", required=True, help="Execution record ID"
    )
    status_parser.set_defaults(func=handle_status)

    # List
    list_parser = subparsers.add_parser("list", help="List executions for a plan")
    list_parser.add_argument("--project-id", required=True, help="Project ID")
    list_parser.add_argument("--plan-id", required=True, help="Run plan ID")
    list_parser.set_defaults(func=handle_list)

    # Cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel an active execution")
    cancel_parser.add_argument("--project-id", required=True, help="Project ID")
    cancel_parser.add_argument("--plan-id", required=True, help="Run plan ID")
    cancel_parser.add_argument(
        "--execution-id", required=True, help="Execution record ID"
    )
    cancel_parser.set_defaults(func=handle_cancel)

    args = parser.parse_args(argv)
    args.db = db
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
