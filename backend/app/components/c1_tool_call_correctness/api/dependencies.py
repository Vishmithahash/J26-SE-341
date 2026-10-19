from fastapi import Header, HTTPException, status


def verify_project_access(
    project_id: str,
    x_project_id: str | None = Header(default=None, alias="X-Project-ID"),
) -> str:
    """Verifies that the caller's authorization context matches the requested project scope.
    Strictly forbids cross-project access attempts.
    """
    if x_project_id is not None and x_project_id.strip() != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Cross-project access denied: caller project context '{x_project_id}' "
                f"does not match route project '{project_id}'."
            ),
        )
    return project_id
