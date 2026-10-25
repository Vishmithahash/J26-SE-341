"""C1 individual live workflow on NexaCart: configuration import, generation, live execution.

The harness double returns exactly the shape of NexaCart's ``/qa/harness`` responses (as consumed
by LiveNexaCartTargetAdapter); its scripted agent either behaves correctly or makes one specific
tool-call mistake. No network access; real runs are covered by
tests/live/test_c1_nexacart_live_e2e.py.
"""

import re
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.api.routes import (
    get_c1_features,
    get_c1_live_adapter_factory,
    get_c1_session_factory,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    GenerationRequest,
)
from app.components.c1_tool_call_correctness.examples.nexacart_live import (
    NEXACART_C1_REQUIREMENTS,
    build_nexacart_live_config,
    is_nexacart_connection,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
)
from app.components.c1_tool_call_correctness.services.nexacart_live_adapter import (
    NexaCartLiveAgentAdapter,
)
from app.components.c1_tool_call_correctness.services.nexacart_live_generator import (
    NexaCartLiveCandidateGenerator,
    render_task_prompt,
    validate_nexacart_live_case,
)
from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.integration.adapters import LiveNexaCartTargetAdapter
from tests.auth_test_fixtures import AutoSeedingTestClient, seed_test_admin

PROJECT_ID = "proj-c1-nexacart-live"
READ_TOOLS = [
    "get_cart",
    "get_order",
    "get_product",
    "list_orders",
    "list_shipping_addresses",
    "search_products",
]
STATE_CHANGING = [
    "add_to_cart",
    "cancel_order",
    "checkout",
    "pay_order",
    "refund_order",
    "remove_cart_item",
    "reserve_cart_item",
    "update_cart_item",
]
SCHEMAS = {
    "refund_order": (
        {"orderNumber": "string", "amount": "string", "reason": "string"},
        ["orderNumber", "amount", "reason"],
    ),
    "cancel_order": (
        {"orderNumber": "string", "reason": "string"},
        ["orderNumber", "reason"],
    ),
    "get_order": ({"orderNumber": "string"}, ["orderNumber"]),
    "pay_order": ({"orderNumber": "string"}, ["orderNumber"]),
    "list_orders": ({"limit": "integer"}, ["limit"]),
    "add_to_cart": (
        {
            "productId": "integer",
            "quantity": "integer",
            "expectedCartVersion": "integer",
        },
        ["productId", "quantity", "expectedCartVersion"],
    ),
    "search_products": (
        {
            "search": ["string", "null"],
            "category": ["string", "null"],
            "inStock": ["boolean", "null"],
            "limit": "integer",
        },
        ["search", "category", "inStock", "limit"],
    ),
}


def _tool(name: str) -> dict[str, Any]:
    props, required = SCHEMAS.get(name, ({}, []))
    return {
        "name": name,
        "description": f"NexaCart tool {name}.",
        "parameters": {
            "type": "object",
            "properties": {k: {"type": v} for k, v in props.items()},
            "required": required,
            "additionalProperties": False,
        },
        "isStateChanging": name in STATE_CHANGING,
    }


CAPABILITIES = {
    "harnessVersion": "1.0.0",
    "agent": {"provider": "OLLAMA", "model": "qwen3.5:4b"},
    "tools": [_tool(n) for n in READ_TOOLS + STATE_CHANGING],
}


class C1Harness:
    """NexaCart-shaped harness double with a scripted customer agent.

    ``behaviour``: correct | oldest_cancelled | number_amount | provider_error | blocked
    """

    # The configured NexaCart instance (local by default); other hosts are never contacted.
    base_url = get_settings().nexacart_base_url

    def __init__(self, behaviour: str = "correct"):
        self.behaviour = behaviour
        self.fixtures: dict[str, dict[str, Any]] = {}
        self.instructions: list[str] = []
        self.released: list[str] = []

    def check_readiness(self):
        if self.behaviour == "blocked":
            return False, ["NexaCart is unreachable."]
        return True, []

    def get_capabilities(self):
        return CAPABILITIES

    def create_fixture(self, definition):
        n = len(self.fixtures) + 1
        short = f"fx{n:06d}"
        products = {}
        for i, p in enumerate(definition.get("products", [])):
            products[p["alias"]] = {
                "id": 500 + 10 * n + i,
                "name": f"QA-{short}-{p['name']}",
                "price": p["price"],
            }
        orders = {}
        for i, o in enumerate(definition.get("orders", [])):
            total = sum(
                Decimal(products[it["productAlias"]]["price"]) * it.get("quantity", 1)
                for it in o.get("items", [])
            )
            orders[o["alias"]] = {
                "orderNumber": f"NXC-QA-{short}-{i + 1}",
                "status": o.get("status", "PENDING"),
                "paymentStatus": "PAID" if o.get("isPaid") else "PENDING",
                "totalAmount": f"{total:.2f}",
                "minutesAgo": o.get("createdMinutesAgo", 0),
                "products": [it["productAlias"] for it in o.get("items", [])],
            }
        context = {
            "customerId": 900 + n,
            "products": products,
            "cartId": 70 + n,
            "cartVersion": 1,
            "orders": orders,
        }
        fixture_id = f"fixture-{n}"
        self.fixtures[fixture_id] = context
        return {
            "fixtureId": fixture_id,
            "context": context,
            "snapshot": {"orders": {"count": len(orders)}},
        }

    def release_fixture(self, fixture_id):
        self.released.append(fixture_id)
        return {"fixtureId": fixture_id, "released": True}

    # -- scripted agent ---------------------------------------------------

    def _plan(self, ctx: dict[str, Any], text: str) -> list[tuple[str, dict[str, Any]]]:
        orders = ctx["orders"]
        lower = text.lower()
        if m := re.search(r"status of my order (\S+?)\?", text):
            return [("get_order", {"orderNumber": m.group(1)})]
        if m := re.search(r"show me my (\d+) most recent", lower):
            return [("list_orders", {"limit": int(m.group(1))})]
        if m := re.search(r"add (\d+) units? of (.+?) to my cart", text):
            product = next(
                p for p in ctx["products"].values() if p["name"] == m.group(2)
            )
            return [
                ("get_cart", {}),
                (
                    "add_to_cart",
                    {
                        "productId": product["id"],
                        "quantity": int(m.group(1)),
                        "expectedCartVersion": 1,
                    },
                ),
            ]
        if "cancel my order" in lower:
            target = next(o for o in orders.values() if o["status"] == "PENDING")
            return [
                ("list_orders", {"limit": 10}),
                (
                    "cancel_order",
                    {
                        "orderNumber": target["orderNumber"],
                        "reason": "no longer needed",
                    },
                ),
            ]
        cancelled = [o for o in orders.values() if o["status"] == "CANCELLED"]
        named = [
            o
            for o in cancelled
            if any(ctx["products"][a]["name"] in text for a in o["products"])
        ]
        if "most recent" in lower:
            target = min(cancelled, key=lambda o: o["minutesAgo"])
            if self.behaviour == "oldest_cancelled":
                target = max(cancelled, key=lambda o: o["minutesAgo"])
        elif named:
            target = named[0]
        elif len(cancelled) == 1:
            target = cancelled[0]
        else:
            return [("list_orders", {"limit": 10})]  # asks which order
        lookup: list[tuple[str, dict[str, Any]]] = []
        if self.behaviour == "invented_lookup":
            # Observed live: qwen first passes the product name as the order number.
            name = ctx["products"][target["products"][0]]["name"]
            lookup = [("get_order", {"orderNumber": name})]
        amount = re.search(r"only ([\d.]+) USD", text)
        value: Any = amount.group(1) if amount else target["totalAmount"]
        if self.behaviour == "number_amount":
            value = float(value)
        return [
            *lookup,
            ("list_orders", {"limit": 10}),
            (
                "refund_order",
                {
                    "orderNumber": target["orderNumber"],
                    "amount": value,
                    "reason": "customer request",
                },
            ),
        ]

    def run_agent(self, fixture_id, instruction, qa_run_id=None, fault_profile=None):
        self.instructions.append(instruction)
        ctx = self.fixtures[fixture_id]
        run_id = f"run-{fixture_id}"
        base = {
            "fixtureId": fixture_id,
            "qaRunId": f"{qa_run_id}-x",
            "durationMs": 1200,
            "beforeSnapshot": {"orders": {"count": len(ctx["orders"])}},
            "intermediateSnapshots": [],
            "afterSnapshot": {"orders": {"count": len(ctx["orders"])}},
            "faultReceipts": [],
            "idempotencyKeys": {},
            "observationErrors": [],
        }
        if self.behaviour == "provider_error" or (
            self.behaviour == "provider_error_once" and len(self.instructions) == 1
        ):
            return {
                **base,
                "agentRun": {"id": run_id, "status": "FAILED", "toolCalls": []},
                "agentError": {
                    "errorCode": "LLM_PROVIDER_ERROR",
                    "message": "Ollama unreachable",
                },
            }
        numbers = {o["orderNumber"] for o in ctx["orders"].values()}
        calls = []
        for seq, (tool, args) in enumerate(self._plan(ctx, instruction), start=1):
            unknown = "orderNumber" in args and args["orderNumber"] not in numbers
            calls.append(
                {
                    "id": f"{fixture_id}-{seq}",
                    "sequenceNumber": seq,
                    "toolName": tool,
                    "arguments": args,
                    "status": "FAILED" if unknown else "SUCCEEDED",
                    "result": {"ok": False, "error": {"errorCode": "ORDER_NOT_FOUND"}}
                    if unknown
                    else {"ok": True, "data": {}},
                    "errorMessage": "Order not found." if unknown else None,
                    "durationMs": 4,
                    "createdAt": "2026-10-25T10:00:00Z",
                }
            )
        return {
            **base,
            "agentRun": {
                "id": run_id,
                "status": "COMPLETED",
                "provider": "OLLAMA",
                "model": "qwen3.5:4b",
                "finalAnswer": "Done.",
                "toolCalls": calls,
            },
            "agentError": None,
        }


def _config_model(seed_caps: dict[str, Any] = CAPABILITIES) -> C1ProjectConfigModel:
    payload = build_nexacart_live_config(seed_caps, C1Harness.base_url)
    return C1ProjectConfigModel(
        id="cfg",
        project_id=PROJECT_ID,
        version=1,
        agent_connection_ref=payload.agent_connection_ref,
        tools=[t.model_dump() for t in payload.tools],
        requirements=[r.model_dump() for r in payload.requirements],
        tool_constraints=payload.tool_constraints.model_dump(),
        expectations={},
        synthetic_fixture_refs=payload.synthetic_fixture_refs,
        reset_capability=payload.reset_capability.model_dump(),
        trace_capabilities=[
            t.model_dump(mode="json") for t in payload.trace_capabilities
        ],
    )


# -- configuration and generation ------------------------------------------------


def test_live_config_uses_real_tools_requirements_and_source_mapping():
    payload = build_nexacart_live_config(CAPABILITIES, C1Harness.base_url)
    assert is_nexacart_connection(payload.agent_connection_ref)
    assert "password" not in payload.agent_connection_ref.lower()
    assert [t.name for t in payload.tools] == READ_TOOLS + STATE_CHANGING
    refund = next(t for t in payload.tools if t.name == "refund_order")
    assert refund.code_mapping.file_path == "src/agent-tools/tools/refund-order.tool.ts"
    assert refund.parameters_schema.required == ["orderNumber", "amount", "reason"]
    assert payload.reset_capability.details["state_changing_tools"] == STATE_CHANGING
    assert {r.req_id for r in payload.requirements} == {
        r.req_id for r in NEXACART_C1_REQUIREMENTS
    }


def test_generator_covers_all_categories_with_valid_bound_expectations():
    config = _config_model()
    candidates = NexaCartLiveCandidateGenerator(
        config, GenerationRequest(seed=11, max_candidates=50)
    ).generate_all_candidates()

    assert {c.category for c in candidates} == set(CaseCategory)
    real_tools = set(READ_TOOLS + STATE_CHANGING)
    for case in candidates:
        assert validate_nexacart_live_case(case) == [] or all(
            i.severity.value == "WARNING" for i in validate_nexacart_live_case(case)
        ), case.case_id
        required = {s.tool_name for s in case.expected_tool_calls if not s.is_forbidden}
        forbidden = {s.tool_name for s in case.expected_tool_calls if s.is_forbidden}
        assert required | forbidden <= real_tools
        # every other state-changing tool is forbidden
        assert forbidden == set(STATE_CHANGING) - required, case.case_id
        for spec in case.expected_tool_calls:
            for constraint in spec.argument_constraints:
                rel = constraint.source_relationship
                assert rel is None or rel.source_record_id in (
                    "fixture",
                    "request",
                    "customer_records",
                )
                # values come from fixtures/requests, never invented constants
                assert constraint.operator is None or constraint.operator.value in (
                    "TYPE_EQUALS",
                    "REGEX_MATCH",
                )
        if case.fixture_plan.starting_conditions["nexacart_fixture"].get("orders"):
            # No call may look up an invented order number (NexaCart system prompt rule).
            lookups = [
                s for s in case.expected_tool_calls if s.tool_name == "get_order"
            ]
            assert lookups and (
                lookups[0].evaluate_all_invocations or lookups[0].min_count == 1
            ), case.case_id
    ambiguous = next(
        c for c in candidates if c.category == CaseCategory.INSUFFICIENT_EVIDENCE
    )
    assert ambiguous.evidence_limitations
    assert all(s.is_forbidden for s in ambiguous.expected_tool_calls if s.min_count > 0)
    assert "refund_order" in {
        s.tool_name for s in ambiguous.expected_tool_calls if s.is_forbidden
    }


def test_generation_is_reproducible_per_seed():
    config = _config_model()

    def hashes(seed):
        return [
            c.canonical_hash
            for c in NexaCartLiveCandidateGenerator(
                config, GenerationRequest(seed=seed, max_candidates=50)
            ).generate_all_candidates()
        ]

    assert hashes(3) == hashes(3)
    assert hashes(3) != hashes(4)


def test_live_case_validation_rejects_hidden_or_unplanned_values():
    config = _config_model()
    case = NexaCartLiveCandidateGenerator(
        config,
        GenerationRequest(seed=1, case_categories=[CaseCategory.CORRECT_BEHAVIOUR]),
    ).generate_all_candidates()[0]

    leaked = case.model_copy(
        update={
            "agent_task_prompt": case.agent_task_prompt
            + " {{fixture.orders.target.totalAmount}}"
        }
    )
    assert "ERR_NXC_TASK_PLACEHOLDER" in {
        i.code for i in validate_nexacart_live_case(leaked)
    }

    spec = case.expected_tool_calls[0].model_copy(deep=True)
    spec.argument_constraints[
        0
    ].source_relationship.source_path = "orders.ghost.orderNumber"
    unplanned = case.model_copy(update={"expected_tool_calls": [spec]})
    assert "ERR_NXC_UNPLANNED_SOURCE" in {
        i.code for i in validate_nexacart_live_case(unplanned)
    }


def test_render_task_prompt_fills_only_from_fixture():
    text, unresolved = render_task_prompt(
        "Refund my {{fixture.products.item.name}} order {{fixture.orders.x.orderNumber}}",
        {"fixture": {"products": {"item": {"name": "QA-1-Desk Lamp"}}}},
    )
    assert text.startswith("Refund my QA-1-Desk Lamp order")
    assert unresolved == ["fixture.orders.x.orderNumber"]


# -- live execution through the C1 API ---------------------------------------------


@pytest.fixture
def harness_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    admin = seed_test_admin(db)
    state = {"harness": C1Harness()}

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: admin
    app.dependency_overrides[get_c1_session_factory] = lambda: factory
    app.dependency_overrides[get_c1_live_adapter_factory] = lambda: (
        lambda base_url=None: NexaCartLiveAgentAdapter(
            LiveNexaCartTargetAdapter(
                client=state.get(base_url or "harness") or state["harness"]
            )
        )
    )
    with AutoSeedingTestClient(db, admin) as client:
        yield client, state
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)


def _base(project_id: str = PROJECT_ID) -> str:
    return f"/api/v1/projects/{project_id}/c1"


def _import_and_generate(client, categories=None, seed=5, suite_id="nxc_live"):
    readiness = client.get(f"{_base()}/live/nexacart/readiness")
    assert readiness.status_code == 200 and readiness.json()["status"] == "READY"
    cfg = client.post(f"{_base()}/live/nexacart/config")
    assert cfg.status_code == 201, cfg.text
    body = {
        "config_version": cfg.json()["version"],
        "seed": seed,
        "max_candidates": 30,
        "max_accepted_cases": 20,
        "auto_promote_suite": True,
        "suite_id": suite_id,
    }
    if categories:
        body["case_categories"] = categories
    job = client.post(f"{_base()}/generation/jobs", json=body)
    assert job.status_code == 201, job.text
    return cfg.json(), job.json()


def _run(client, suite_id="nxc_live"):
    started = client.post(f"{_base()}/runs", json={"suite_id": suite_id})
    assert started.status_code == 201, started.text
    # TestClient runs the background job before returning; the run is then terminal.
    return client.get(f"{_base()}/runs/{started.json()['summary']['run_id']}").json()


def test_import_generate_and_run_live_suite_correct_agent(harness_env):
    client, state = harness_env
    _cfg, job = _import_and_generate(client)
    assert job["summary"]["invalid_candidates"] == 0
    assert set(job["summary"]["category_counts"]) == {c.value for c in CaseCategory}

    run = _run(client)
    summary = run["summary"]
    assert summary["status"] == "COMPLETED"
    assert summary["passed_cases"] == summary["total_cases"] > 0
    assert run["effective_config"]["adapter_type"] == "NEXACART_LIVE_AGENT_ADAPTER"
    # Primary keys are varchar(36) in PostgreSQL (SQLite does not enforce the length).
    assert len(summary["run_id"]) <= 36
    assert all(len(c["execution_id"]) <= 36 for c in run["case_executions"])
    assert run["effective_config"]["execution_target"]["agent"]["model"] == "qwen3.5:4b"
    # provenance is corroborated by the recorded agent runs, in the detail and the run list
    assert summary["execution_provenance"] == "LIVE_EXECUTION"
    listed = client.get(f"{_base()}/runs").json()
    assert next(r for r in listed if r["run_id"] == summary["run_id"])[
        "execution_provenance"
    ] == "LIVE_EXECUTION"

    for case in run["case_executions"]:
        task = case["agent_task_sent"]["task_prompt"]
        assert "{{" not in task
        assert task in state["harness"].instructions  # the only text NexaCart received
        assert case["raw_trace"]["agent_run_id"].startswith("run-fixture-")
        assert case["raw_trace"]["is_live_execution"] is True
        for spec in case["resolved_expectations"]:
            for constraint in spec["argument_constraints"]:
                rel = constraint["source_relationship"]
                if rel and constraint["operator"] is None:
                    assert (
                        constraint["expected_value"] is not None
                    )  # frozen from real fixture
        if "refund" in case["case_id"]:
            fixture_numbers = re.findall(r"NXC-QA-\S+", task)
            assert (
                not fixture_numbers
            )  # the oracle order number is never in a refund task
    assert len(state["harness"].released) == summary["total_cases"]


def test_wrong_order_selection_fails_with_source_mismatch(harness_env):
    client, state = harness_env
    state["harness"] = C1Harness("oldest_cancelled")
    _import_and_generate(client, categories=["CONTEXTUAL_SOURCE_MISMATCH"])
    run = _run(client)
    latest = next(c for c in run["case_executions"] if "most_recent" in c["case_id"])
    assert latest["verdict"] == "FAIL"
    mismatch = [
        ch
        for ch in latest["check_results"]
        if ch["verdict"] == "FAIL" and ch["target_argument"] == "orderNumber"
    ]
    assert mismatch and mismatch[0]["reason_code"] == "SOURCE_VALUE_MISMATCH"
    assert mismatch[0]["expected_value"] != mismatch[0]["actual_value"]

    diagnosis = client.post(
        f"{_base()}/runs/{run['summary']['run_id']}/diagnose",
        json={"case_id": latest["case_id"]},
    )
    assert diagnosis.status_code == 200, diagnosis.text
    assert diagnosis.json()[0]["cause_category"] == "AGENT_BEHAVIOUR"


def test_invented_order_number_lookup_fails_even_when_refund_is_right(harness_env):
    client, state = harness_env
    state["harness"] = C1Harness("invented_lookup")
    _import_and_generate(client, categories=["CORRECT_BEHAVIOUR"])
    run = _run(client)
    case = run["case_executions"][0]
    assert case["verdict"] == "FAIL"
    failed = [c for c in case["check_results"] if c["verdict"] == "FAIL"]
    assert len(failed) == 1
    assert failed[0]["rule_name"] == "ARG_CONSTRAINT_ALL_CALLS_orderNumber"
    assert failed[0]["reason_code"] == "SOURCE_VALUE_MISMATCH"
    assert failed[0]["requirement_refs"] == ["NXC-C1-NO-INVENTED-IDS"]
    assert failed[0]["actual_value"].startswith("QA-")  # the product name
    # the refund itself was correct
    refund_checks = [
        c for c in case["check_results"] if c["target_tool"] == "refund_order"
    ]
    assert refund_checks and all(c["verdict"] == "PASS" for c in refund_checks)


def test_optional_lookup_absent_passes_and_is_reported():
    from app.components.c1_tool_call_correctness.contracts.execution import (
        TraceCompleteness,
    )
    from app.components.c1_tool_call_correctness.contracts.generation import (
        ExpectedToolCallSpec,
    )
    from app.components.c1_tool_call_correctness.services.correctness_evaluator import (
        DeterministicCorrectnessEvaluator,
    )

    verdict, checks = DeterministicCorrectnessEvaluator().evaluate_case(
        case_id="c",
        category=CaseCategory.CORRECT_BEHAVIOUR,
        resolved_expectations=[
            ExpectedToolCallSpec(
                tool_name="get_order",
                min_count=0,
                max_count=None,
                evaluate_all_invocations=True,
            )
        ],
        captured_events=[],
        trace_completeness=TraceCompleteness.COMPLETE,
        context_data={},
        requirement_refs=[],
    )
    assert verdict.value == "PASS"
    assert checks[0].rule_name == "OPTIONAL_TOOL_USAGE"


def test_numeric_amount_type_is_reported(harness_env):
    client, state = harness_env
    state["harness"] = C1Harness("number_amount")
    _import_and_generate(client, categories=["CORRECT_BEHAVIOUR"])
    run = _run(client)
    case = run["case_executions"][0]
    assert case["verdict"] == "FAIL"
    failed = {
        (c["target_argument"], c["reason_code"])
        for c in case["check_results"]
        if c["verdict"] == "FAIL"
    }
    assert ("amount", "ARGUMENT_VALUE_MISMATCH") in failed  # TYPE_EQUALS string


def test_provider_error_is_not_scored_as_agent_behaviour(harness_env):
    client, state = harness_env
    state["harness"] = C1Harness("provider_error")
    _import_and_generate(client, categories=["CORRECT_BEHAVIOUR"])
    run = _run(client)
    assert run["summary"]["error_cases"] == run["summary"]["total_cases"]
    case = run["case_executions"][0]
    assert case["execution_status"] == "EXECUTION_ERROR"
    assert case["verdict"] == "INCONCLUSIVE"
    assert case["check_results"][0]["reason_code"] == "ADAPTER_ERROR"


def test_blocked_target_records_failed_run_without_simulation(harness_env):
    client, state = harness_env
    _import_and_generate(client, categories=["CORRECT_BEHAVIOUR"])
    state["harness"] = C1Harness("blocked")
    run = _run(client)
    assert run["summary"]["status"] == "FAILED"
    assert run["case_executions"] == []
    assert state["harness"].instructions == []
    readiness = client.get(f"{_base()}/adapter/readiness").json()
    assert readiness["is_ready"] is False
    assert readiness["adapter_type"] == "NEXACART_LIVE_AGENT_ADAPTER"


def test_rerun_of_live_run_uses_live_adapter(harness_env):
    client, state = harness_env
    _import_and_generate(client, categories=["WRONG_TOOL_SELECTION"])
    run = _run(client)
    before = len(state["harness"].instructions)
    rerun = client.post(f"{_base()}/runs/{run['summary']['run_id']}/rerun")
    assert rerun.status_code == 200, rerun.text
    assert len(state["harness"].instructions) == before + run["summary"]["total_cases"]
    detail = client.get(f"{_base()}/runs/{run['summary']['run_id']}").json()
    assert all(c["attempt_number"] == 2 for c in detail["case_executions"])
    assert all(
        c["raw_trace"]["adapter"] == "NEXACART_LIVE_AGENT_ADAPTER"
        for c in detail["case_executions"]
    )


def test_repetitions_run_each_case_and_report_per_case_rates(harness_env):
    client, state = harness_env
    _import_and_generate(client, categories=["CORRECT_BEHAVIOUR"])
    started = client.post(
        f"{_base()}/runs", json={"suite_id": "nxc_live", "repetitions": 3}
    )
    assert started.status_code == 201, started.text
    run = client.get(f"{_base()}/runs/{started.json()['summary']['run_id']}").json()
    summary = run["summary"]
    assert summary["repetitions"] == 3
    assert summary["total_cases"] == 6  # 2 cases x 3 runs
    assert len(state["harness"].instructions) == 6  # 6 real agent runs, fresh fixtures
    assert len(run["case_executions"]) == 6
    assert {c["case_id"].split("::r")[1] for c in run["case_executions"]} == {
        "1",
        "2",
        "3",
    }
    for entry in summary["repetition_summary"].values():
        assert entry == {
            "runs": 3,
            "PASS": 3,
            "FAIL": 0,
            "INCONCLUSIVE": 0,
            "ERROR": 0,
            "pass_rate": 1.0,
        }


def test_correction_for_agent_behaviour_is_ineligible(harness_env, monkeypatch):
    client, state = harness_env
    monkeypatch.setattr(get_settings(), "c1_code_correction_enabled", True)
    state["harness"] = C1Harness("oldest_cancelled")
    _import_and_generate(client, categories=["CONTEXTUAL_SOURCE_MISMATCH"])
    run = _run(client)
    case = next(c for c in run["case_executions"] if c["verdict"] == "FAIL")
    diagnosis = client.post(
        f"{_base()}/runs/{run['summary']['run_id']}/diagnose",
        json={"case_id": case["case_id"]},
    ).json()[0]
    assert diagnosis["cause_category"] == "AGENT_BEHAVIOUR"
    attempt = client.post(
        f"{_base()}/corrections/attempts",
        json={"diagnosis_id": diagnosis["diagnosis_id"]},
    )
    assert attempt.status_code == 200, attempt.text
    body = attempt.json()
    assert body["status"] == "INELIGIBLE"
    assert body["candidate_patch"] is None
    assert any(
        "SUPPORTED_APPLICATION_CODE_DEFECT" in r for r in body["ineligibility_reasons"]
    )


def test_defect_lab_lists_controlled_defects_and_requires_running_lab(harness_env):
    client, _state = harness_env
    app.dependency_overrides[get_c1_features] = lambda: {
        "code_correction_enabled": True
    }
    status = client.get(f"{_base()}/live/nexacart/defect-lab").json()
    assert status["lab"] is None
    assert {d["defect_id"] for d in status["defects"]} == {
        "refund_order_number_mapping",
        "refund_order_amount_mapping",
        "add_to_cart_product_mapping",
        "get_order_number_mapping",
        "cancel_order_reason_mapping",
    }
    assert client.post(f"{_base()}/live/nexacart/config?target=lab").status_code == 409


def test_provider_error_is_retried_once_on_a_fresh_fixture(harness_env):
    client, state = harness_env
    state["harness"] = C1Harness("provider_error_once")
    _import_and_generate(client, categories=["WRONG_TOOL_SELECTION"])
    run = _run(client)
    first = run["case_executions"][0]
    statuses = {c["execution_status"] for c in run["case_executions"]}
    assert statuses == {
        "EXECUTED"
    }  # the provider timeout of the first agent run was retried
    retried = [
        c
        for c in run["case_executions"]
        if c["raw_trace"].get("infrastructure_retries")
    ]
    assert len(retried) == 1
    assert (
        retried[0]["raw_trace"]["infrastructure_retries"][0]["caller_outcome"]
        == "LLM_PROVIDER_ERROR"
    )
    assert retried[0]["session_id"].endswith("_retry")
    assert first["verdict"] in ("PASS", "FAIL")
    # one extra agent run, one extra fixture (both released)
    assert len(state["harness"].instructions) == run["summary"]["total_cases"] + 1
    assert len(state["harness"].released) == run["summary"]["total_cases"] + 1


def test_code_correction_and_defect_lab_are_off_by_default(harness_env):
    """Progress-presentation-1 build: testing + explanation only; correction is a later stage."""
    client, state = harness_env
    assert client.get(f"{_base()}/features").json()["code_correction_enabled"] is False
    lab = client.get(f"{_base()}/live/nexacart/defect-lab").json()
    assert lab == {"enabled": False, "lab": None, "defects": []}
    started = client.post(
        f"{_base()}/live/nexacart/defect-lab",
        json={"defect_id": "refund_order_number_mapping"},
    )
    assert started.status_code == 404
    assert client.post(f"{_base()}/live/nexacart/config?target=lab").status_code == 404

    state["harness"] = C1Harness("oldest_cancelled")
    _import_and_generate(client, categories=["CONTEXTUAL_SOURCE_MISMATCH"])
    run = _run(client)
    case = next(c for c in run["case_executions"] if c["verdict"] == "FAIL")
    diagnosis = client.post(
        f"{_base()}/runs/{run['summary']['run_id']}/diagnose",
        json={"case_id": case["case_id"]},
    ).json()[0]
    attempt = client.post(
        f"{_base()}/corrections/attempts",
        json={"diagnosis_id": diagnosis["diagnosis_id"]},
    ).json()
    assert attempt["status"] == "INELIGIBLE"
    assert "disabled in this build" in attempt["ineligibility_reasons"][0]


def test_explanations_name_requirement_expected_source_and_provenance(harness_env):
    """FR-07: relevant requirement, expected-value source and inferred argument provenance."""
    client, state = harness_env
    state["harness"] = C1Harness("invented_lookup")
    _import_and_generate(client, categories=["CORRECT_BEHAVIOUR"])
    run = _run(client)
    case = run["case_executions"][0]
    diagnosis = client.post(
        f"{_base()}/runs/{run['summary']['run_id']}/diagnose",
        json={"case_id": case["case_id"]},
    ).json()[0]
    assert diagnosis["cause_category"] == "AGENT_BEHAVIOUR"
    explanation = diagnosis["check_explanations"][0]
    assert explanation["tool_name"] == "get_order"
    assert explanation["requirements"][0]["req_id"] == "NXC-C1-NO-INVENTED-IDS"
    assert explanation["requirements"][0]["title"] == "Order numbers are never invented"
    assert explanation["expected_value_source"].startswith(
        "customer_records.orderNumbers (SUBSET_OF)"
    )
    # the product name the agent used as an order number came from the customer's request
    assert explanation["source_relationship_status"] == "INFERRED"
    assert "customer's request" in explanation["argument_provenance"]
    assert "customer's request" in diagnosis["explanation_summary"]


def test_run_execution_provenance_needs_recorded_agent_run():
    from app.components.c1_tool_call_correctness.services.execution_service import (
        run_execution_provenance,
    )

    live = {"adapter": "NEXACART_LIVE_AGENT_ADAPTER", "is_live_execution": True}
    assert run_execution_provenance([]) is None
    assert run_execution_provenance([live]) is None  # no NexaCart agent run was started
    assert run_execution_provenance([None, {**live, "agent_run_id": "r1"}]) == "LIVE_EXECUTION"
    assert run_execution_provenance([{"adapter": "SIMULATED_FAKE_ADAPTER"}]) == "SYNTHETIC_DEMO"
