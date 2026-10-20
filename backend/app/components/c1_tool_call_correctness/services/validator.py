import re

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ProjectConfigCreate,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationIssue,
    ValidationSeverity,
    ValidationSummary,
)


def detect_secret_patterns(value: str) -> bool:
    """Checks if a string appears to be an actual raw credential/secret rather than a reference ID."""
    suspicious_patterns = [
        r"^sk-[A-Za-z0-9_-]{20,}",  # OpenAI / Anthropic key format
        r"^ghp_[A-Za-z0-9]{20,}",  # GitHub personal token
        r"^Bearer\s+[A-Za-z0-9._-]{20,}",  # Bearer token
        r"-----BEGIN (RSA |EC )?PRIVATE KEY",  # PEM private key
    ]
    for pat in suspicious_patterns:
        if re.search(pat, value):
            return True
    return False


def validate_project_config(config: ProjectConfigCreate) -> ValidationSummary:
    """Performs deep semantic validation of a Component 1 project configuration specification.
    Verifies reference integrity, detects conflicts and cycles, and ensures bounded contracts.
    """
    issues: list[ValidationIssue] = []

    # 1. Connection reference validation
    conn_ref = config.agent_connection_ref.strip()
    if not conn_ref:
        issues.append(
            ValidationIssue(
                code="ERR_EMPTY_CONNECTION_REF",
                severity=ValidationSeverity.ERROR,
                message="agent_connection_ref must not be empty.",
                path="agent_connection_ref",
            )
        )
    elif detect_secret_patterns(conn_ref):
        issues.append(
            ValidationIssue(
                code="ERR_RAW_SECRET_EXPOSED",
                severity=ValidationSeverity.ERROR,
                message=(
                    "agent_connection_ref appears to contain a raw API key or secret. "
                    "Component payloads must store credential references, not plaintext secrets."
                ),
                path="agent_connection_ref",
            )
        )

    # 2. Tool definitions validation
    declared_tools: set[str] = set()
    for idx, tool in enumerate(config.tools):
        tname = tool.name.strip()
        path = f"tools[{idx}]"
        if not tname:
            issues.append(
                ValidationIssue(
                    code="ERR_EMPTY_TOOL_NAME",
                    severity=ValidationSeverity.ERROR,
                    message="Tool name cannot be empty.",
                    path=f"{path}.name",
                )
            )
            continue
        if tname in declared_tools:
            issues.append(
                ValidationIssue(
                    code="ERR_DUPLICATE_TOOL_NAME",
                    severity=ValidationSeverity.ERROR,
                    message=f"Duplicate tool definition name '{tname}'.",
                    path=f"{path}.name",
                )
            )
        declared_tools.add(tname)

        # Check properties in parameters_schema
        if tool.parameters_schema:
            props = tool.parameters_schema.properties
            reqs = tool.parameters_schema.required
            for req in reqs:
                if req not in props:
                    issues.append(
                        ValidationIssue(
                            code="WARN_UNDECLARED_REQUIRED_PROP",
                            severity=ValidationSeverity.WARNING,
                            message=f"Required argument '{req}' is not declared in properties of tool '{tname}'.",
                            path=f"{path}.parameters_schema.required",
                        )
                    )

    # 3. Requirements validation
    declared_req_ids: set[str] = set()
    for idx, req in enumerate(config.requirements):
        rid = req.req_id.strip()
        path = f"requirements[{idx}]"
        if not rid:
            issues.append(
                ValidationIssue(
                    code="ERR_EMPTY_REQ_ID",
                    severity=ValidationSeverity.ERROR,
                    message="Requirement ID cannot be empty.",
                    path=f"{path}.req_id",
                )
            )
            continue
        if rid in declared_req_ids:
            issues.append(
                ValidationIssue(
                    code="ERR_DUPLICATE_REQ_ID",
                    severity=ValidationSeverity.ERROR,
                    message=f"Duplicate requirement ID '{rid}'.",
                    path=f"{path}.req_id",
                )
            )
        declared_req_ids.add(rid)

    # 4. Tool constraints reference validation
    tc = config.tool_constraints
    if tc:
        for t in tc.required_tools:
            if t not in declared_tools:
                issues.append(
                    ValidationIssue(
                        code="ERR_UNKNOWN_TOOL_REF",
                        severity=ValidationSeverity.ERROR,
                        message=f"required_tools references undeclared tool '{t}'.",
                        path=f"tool_constraints.required_tools['{t}']",
                    )
                )
        for t in tc.permitted_tools:
            if t not in declared_tools:
                issues.append(
                    ValidationIssue(
                        code="ERR_UNKNOWN_TOOL_REF",
                        severity=ValidationSeverity.ERROR,
                        message=f"permitted_tools references undeclared tool '{t}'.",
                        path=f"tool_constraints.permitted_tools['{t}']",
                    )
                )
        # Negative constraints in forbidden_tools are allowed even if not in positive tool catalog.

        # Conflict check: required vs forbidden
        conflicts = set(tc.required_tools).intersection(set(tc.forbidden_tools))
        for conflict in conflicts:
            issues.append(
                ValidationIssue(
                    code="ERR_TOOL_CONSTRAINT_CONFLICT",
                    severity=ValidationSeverity.ERROR,
                    message=f"Tool '{conflict}' cannot be both required and forbidden.",
                    path="tool_constraints",
                )
            )

    # 5. Declarative expectations validation
    exp_dict = config.expectations or {}
    tool_selections = exp_dict.get("tool_selections", [])
    if isinstance(tool_selections, list):
        precedence_graph: dict[str, set[str]] = {}
        for idx, sel in enumerate(tool_selections):
            if not isinstance(sel, dict):
                continue
            t_name = sel.get("tool_name", "")
            path = f"expectations.tool_selections[{idx}]"
            if t_name not in declared_tools:
                issues.append(
                    ValidationIssue(
                        code="ERR_UNKNOWN_TOOL_REF",
                        severity=ValidationSeverity.ERROR,
                        message=f"Expectation targets undeclared tool '{t_name}'.",
                        path=f"{path}.tool_name",
                    )
                )

            # Check requirement references
            req_refs = sel.get("requirement_refs", [])
            for rref in req_refs:
                if rref not in declared_req_ids:
                    issues.append(
                        ValidationIssue(
                            code="ERR_UNKNOWN_REQ_REF",
                            severity=ValidationSeverity.ERROR,
                            message=f"Expectation references undeclared requirement '{rref}'.",
                            path=f"{path}.requirement_refs",
                            requirement_ref=rref,
                        )
                    )

            # Build precedence graph for cycle detection
            precedes = sel.get("must_precede_tools", [])
            for prec in precedes:
                if prec not in declared_tools:
                    issues.append(
                        ValidationIssue(
                            code="ERR_UNKNOWN_TOOL_REF",
                            severity=ValidationSeverity.ERROR,
                            message=f"must_precede_tools references undeclared tool '{prec}'.",
                            path=f"{path}.must_precede_tools",
                        )
                    )
                else:
                    precedence_graph.setdefault(t_name, set()).add(prec)

        # Detect cycle in precedence graph using DFS
        visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

        def has_cycle(node: str) -> bool:
            visited[node] = 1
            for neighbor in precedence_graph.get(node, []):
                if visited.get(neighbor) == 1:
                    return True
                if visited.get(neighbor) != 2 and has_cycle(neighbor):
                    return True
            visited[node] = 2
            return False

        for node in list(precedence_graph.keys()):
            if visited.get(node) != 2 and has_cycle(node):
                issues.append(
                    ValidationIssue(
                        code="ERR_CYCLIC_TOOL_PRECEDENCE",
                        severity=ValidationSeverity.ERROR,
                        message=f"Cyclic tool precedence dependency detected involving tool '{node}'.",
                        path="expectations.tool_selections",
                    )
                )
                break

    # Argument constraints validation
    arg_constraints = exp_dict.get("argument_constraints", {})
    if isinstance(arg_constraints, dict):
        for tool_name, constraints in arg_constraints.items():
            if tool_name not in declared_tools:
                issues.append(
                    ValidationIssue(
                        code="ERR_UNKNOWN_TOOL_REF",
                        severity=ValidationSeverity.ERROR,
                        message=f"argument_constraints defined for undeclared tool '{tool_name}'.",
                        path=f"expectations.argument_constraints.{tool_name}",
                    )
                )
            if isinstance(constraints, list):
                for c_idx, constraint in enumerate(constraints):
                    if not isinstance(constraint, dict):
                        continue
                    path = f"expectations.argument_constraints.{tool_name}[{c_idx}]"
                    r_refs = constraint.get("requirement_refs", [])
                    for r_ref in r_refs:
                        if r_ref not in declared_req_ids:
                            issues.append(
                                ValidationIssue(
                                    code="ERR_UNKNOWN_REQ_REF",
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Argument constraint references undeclared requirement '{r_ref}'.",
                                    path=f"{path}.requirement_refs",
                                    requirement_ref=r_ref,
                                )
                            )

                    # Source relationship validation
                    src_rel = constraint.get("source_relationship")
                    if isinstance(src_rel, dict):
                        src_rec_id = src_rel.get("source_record_id")
                        if not src_rec_id:
                            issues.append(
                                ValidationIssue(
                                    code="ERR_INVALID_SOURCE_RELATIONSHIP",
                                    severity=ValidationSeverity.ERROR,
                                    message="Source relationship must specify 'source_record_id'.",
                                    path=f"{path}.source_relationship.source_record_id",
                                )
                            )

    # 6. Trace capabilities check
    active_channels = [tc for tc in config.trace_capabilities if tc.enabled]
    if not active_channels:
        issues.append(
            ValidationIssue(
                code="WARN_NO_ACTIVE_TRACE_CHANNEL",
                severity=ValidationSeverity.WARNING,
                message="No active trace or evidence channels configured. Tool-call evaluation evidence may be limited.",
                path="trace_capabilities",
            )
        )

    error_count = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)

    return ValidationSummary(
        is_valid=(error_count == 0),
        error_count=error_count,
        warning_count=warning_count,
        issues=issues,
    )
