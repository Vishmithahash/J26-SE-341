"""Automatic C1 case generation for the live NexaCart agent.

Component: C1 - Explainable Tool-Call Correctness Testing

Cases are derived from the configuration imported from NexaCart's QA harness (real tool names and
schemas, state-changing flags), the versioned NexaCart C1 requirements and controlled harness
fixtures. Each case has:

- a customer task (the ONLY text NexaCart's agent receives). Placeholders such as
  ``{{fixture.products.lamp.name}}`` are filled after the fixture exists, and only with values a
  customer can see (product names, an order number the customer quotes);
- a NexaCart fixture definition (customer, products, cart, aliased orders) created fresh per case;
- expected tool calls whose values are bound to fixture records (``fixture``) or to facts the
  customer stated in the task (``request``) and resolved at run time, never invented;
- forbidden expectations for every other state-changing NexaCart tool.

The categories follow the proposal (correct behaviour, wrong tool selection, missing arguments,
malformed names/types, incorrect values, contextual-source mismatch, insufficient evidence). A
category names the risk a case probes; the live agent decides what actually happens.
"""

import json
import random
import re
from collections.abc import Callable
from typing import Any

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
    ComparisonOperator,
    EvidenceRequirement,
    FieldPresence,
    SourceDataRelationship,
    SourceRelationshipType,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
    FixturePreparationPlan,
    GeneratedCandidateCase,
    GenerationProvenance,
    GenerationRequest,
    SyntheticRecordRequirement,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationIssue,
    ValidationSeverity,
)
from app.components.c1_tool_call_correctness.examples.nexacart_live import (
    NEXACART_CUSTOMER_RECORDS,
    NEXACART_FIXTURE_CAPABILITY,
    NEXACART_LIVE_FIXTURE_RECORD,
    NEXACART_REQUEST_RECORD,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1ProjectConfigModel,
)
from app.components.c1_tool_call_correctness.services.generator_engine import (
    compute_case_canonical_hash,
)

GENERATOR_ID = "c1_nexacart_live_generator"
GENERATOR_VERSION = "1.0.0"

PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")
# Only values a customer can see may be put into the task text.
ALLOWED_PLACEHOLDER_RE = re.compile(
    r"^fixture\.(products\.[A-Za-z0-9_]+\.name|orders\.[A-Za-z0-9_]+\.orderNumber)$"
)
# Amounts are decimal strings; a difference below half a cent is formatting, not a wrong value.
AMOUNT_TOLERANCE = 0.005

PRODUCT_POOL: list[tuple[str, str]] = [
    ("Desk Lamp", "40.00"),
    ("Wireless Mouse", "25.50"),
    ("USB-C Hub", "62.00"),
    ("Bluetooth Speaker", "89.99"),
    ("Laptop Stand", "34.75"),
    ("Webcam", "58.20"),
]
REASONS = [
    "the item arrived damaged",
    "it no longer fits my needs",
    "it was delivered too late",
    "I ordered it by mistake",
]


def render_task_prompt(
    template: str, context_data: dict[str, Any]
) -> tuple[str, list[str]]:
    """Fill ``{{fixture....}}`` placeholders from the prepared fixture. Returns (text, unresolved)."""
    unresolved: list[str] = []

    def _value(match: re.Match[str]) -> str:
        path = match.group(1)
        current: Any = context_data
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                unresolved.append(path)
                return match.group(0)
        return str(current)

    return PLACEHOLDER_RE.sub(_value, template), unresolved


def _amount(value: float) -> str:
    return f"{value:.2f}"


class NexaCartLiveCandidateGenerator:
    """Generates NexaCart C1 cases from the imported harness configuration."""

    GENERATOR_ID = GENERATOR_ID
    GENERATOR_VERSION = GENERATOR_VERSION

    def __init__(self, config: C1ProjectConfigModel, request: GenerationRequest):
        self.config = config
        self.request = request
        self.seed = request.seed if request.seed is not None else 42
        self.rng = random.Random(self.seed)
        self.tools = {
            t["name"]: t
            for t in (config.tools or [])
            if isinstance(t, dict) and "name" in t
        }
        details = (config.reset_capability or {}).get("details") or {}
        self.state_changing = [
            name
            for name in details.get("state_changing_tools") or []
            if name in self.tools
        ]
        self.requirement_ids = {
            r["req_id"] for r in (config.requirements or []) if isinstance(r, dict)
        }
        self._counter = 0

    # -- helpers -------------------------------------------------------------

    def _products(self, count: int) -> list[tuple[str, str]]:
        return self.rng.sample(PRODUCT_POOL, count)

    def _evidence(self) -> list[EvidenceRequirement]:
        return [EvidenceRequirement(channel=EvidenceChannel.TOOL_CALL_LOG)]

    def _required(
        self,
        tool: str,
        constraints: list[ArgumentConstraint],
        refs: list[str],
        max_count: int | None = 1,
    ) -> ExpectedToolCallSpec:
        return ExpectedToolCallSpec(
            tool_name=tool,
            min_count=1,
            max_count=max_count,
            argument_constraints=constraints,
            evidence_requirements=self._evidence(),
            requirement_refs=refs,
        )

    def _forbid(self, allowed: set[str], refs: list[str]) -> list[ExpectedToolCallSpec]:
        """Every NexaCart state-changing tool the task does not call for is forbidden."""
        return [
            ExpectedToolCallSpec(
                tool_name=name,
                is_forbidden=True,
                min_count=0,
                max_count=0,
                evidence_requirements=self._evidence(),
                requirement_refs=refs,
            )
            for name in self.state_changing
            if name not in allowed
        ]

    @staticmethod
    def _bound(
        arg: str,
        record: str,
        path: str,
        refs: list[str],
        relationship: SourceRelationshipType = SourceRelationshipType.EXACT_MATCH,
        tolerance: float | None = None,
        expected_type: str | None = None,
    ) -> ArgumentConstraint:
        return ArgumentConstraint(
            argument_name=arg,
            presence=FieldPresence.REQUIRED_NON_NULL,
            expected_type=expected_type,
            source_relationship=SourceDataRelationship(
                source_record_id=record,
                source_path=path,
                relationship_type=relationship,
                tolerance=tolerance,
            ),
            requirement_refs=refs,
        )

    @staticmethod
    def _typed(arg: str, type_name: str, refs: list[str]) -> ArgumentConstraint:
        return ArgumentConstraint(
            argument_name=arg,
            presence=FieldPresence.REQUIRED_NON_NULL,
            expected_type=type_name,
            operator=ComparisonOperator.TYPE_EQUALS,
            expected_value=type_name,
            requirement_refs=refs,
        )

    @staticmethod
    def _non_blank(arg: str, refs: list[str]) -> ArgumentConstraint:
        return ArgumentConstraint(
            argument_name=arg,
            presence=FieldPresence.REQUIRED_NON_NULL,
            expected_type="string",
            operator=ComparisonOperator.REGEX_MATCH,
            expected_value=r"\S",
            requirement_refs=refs,
        )

    def _order_number(self, alias: str, refs: list[str]) -> ArgumentConstraint:
        return self._bound(
            "orderNumber",
            NEXACART_LIVE_FIXTURE_RECORD,
            f"orders.{alias}.orderNumber",
            refs,
            expected_type="string",
        )

    def _refund_amount(
        self, record: str, path: str, refs: list[str]
    ) -> list[ArgumentConstraint]:
        return [
            self._typed("amount", "string", refs),
            self._bound(
                "amount",
                record,
                path,
                refs,
                relationship=SourceRelationshipType.NUMERIC_TOLERANCE,
                tolerance=AMOUNT_TOLERANCE,
            ),
        ]

    def _case(
        self,
        category: CaseCategory,
        scenario: str,
        prompt: str,
        fixture: dict[str, Any],
        expected: list[ExpectedToolCallSpec],
        request_facts: dict[str, Any],
        derivation: str,
        evidence_limitations: str | None = None,
    ) -> GeneratedCandidateCase:
        self._counter += 1
        required = {s.tool_name for s in expected if not s.is_forbidden}
        if (
            fixture.get("orders")
            and "get_order" in self.tools
            and "get_order" not in required
        ):
            # Order lookups are optional, but none may use an invented order number.
            expected = [
                *expected,
                ExpectedToolCallSpec(
                    tool_name="get_order",
                    min_count=0,
                    max_count=None,
                    evaluate_all_invocations=True,
                    argument_constraints=[
                        self._bound(
                            "orderNumber",
                            NEXACART_CUSTOMER_RECORDS,
                            "orderNumbers",
                            ["NXC-C1-NO-INVENTED-IDS"],
                            relationship=SourceRelationshipType.SUBSET_OF,
                        )
                    ],
                    evidence_requirements=self._evidence(),
                    requirement_refs=["NXC-C1-NO-INVENTED-IDS"],
                ),
            ]
        refs = sorted({r for spec in expected for r in spec.requirement_refs})
        records = [
            SyntheticRecordRequirement(
                record_id=f"products.{p['alias']}",
                record_type="product",
                attributes={k: v for k, v in p.items() if k != "alias"},
            )
            for p in fixture.get("products", [])
        ] + [
            SyntheticRecordRequirement(
                record_id=f"orders.{o['alias']}",
                record_type="order",
                attributes={k: v for k, v in o.items() if k != "alias"},
            )
            for o in fixture.get("orders", [])
        ]
        if fixture.get("cart", {}).get("create", True):
            records.append(
                SyntheticRecordRequirement(
                    record_id="cart",
                    record_type="cart",
                    attributes={"items": fixture.get("cart", {}).get("items", [])},
                )
            )
        summary = json.dumps(
            {
                "scenario": scenario,
                "prompt": prompt,
                "fixture": fixture,
                "request": request_facts,
            },
            sort_keys=True,
        )
        return GeneratedCandidateCase(
            case_id=f"nxc_c1_{self._counter:03d}_{scenario}",
            category=category,
            agent_task_prompt=prompt,
            task_context_inputs=request_facts,
            requirement_refs=refs,
            fixture_plan=FixturePreparationPlan(
                fixture_capability_ref=NEXACART_FIXTURE_CAPABILITY,
                reset_hook_ref=NEXACART_FIXTURE_CAPABILITY,
                synthetic_records=records,
                starting_conditions={"nexacart_fixture": fixture, "scenario": scenario},
                declared_compatibility=True,
                static_feasibility=True,
                runtime_readiness=False,
            ),
            expected_tool_calls=expected,
            evidence_limitations=evidence_limitations,
            provenance=GenerationProvenance(
                generator_id=GENERATOR_ID,
                generator_version=GENERATOR_VERSION,
                seed=self.seed,
                rule_derivation=derivation,
            ),
            canonical_hash=compute_case_canonical_hash(
                refs, category, expected, summary
            ),
        )

    @staticmethod
    def _product(alias: str, name: str, price: str) -> dict[str, Any]:
        return {"alias": alias, "name": name, "price": price, "stockQuantity": 10}

    # -- scenarios -----------------------------------------------------------

    def _full_refund(self) -> GeneratedCandidateCase:
        ((name, price),) = self._products(1)
        quantity = self.rng.choice([1, 2])
        reason = self.rng.choice(REASONS)
        refs = ["NXC-C1-REFUND-TARGET", "NXC-C1-REFUND-AMOUNT", "NXC-C1-REFUND-REASON"]
        fixture = {
            "products": [self._product("item", name, price)],
            "orders": [
                {
                    "alias": "target",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "items": [{"productAlias": "item", "quantity": quantity}],
                }
            ],
        }
        expected = [
            self._required(
                "refund_order",
                [
                    self._order_number("target", refs[:1]),
                    *self._refund_amount(
                        NEXACART_LIVE_FIXTURE_RECORD,
                        "orders.target.totalAmount",
                        refs[1:2],
                    ),
                    self._non_blank("reason", refs[2:]),
                ],
                refs,
            ),
            *self._forbid({"refund_order"}, ["NXC-C1-REFUND-TARGET"]),
        ]
        return self._case(
            CaseCategory.CORRECT_BEHAVIOUR,
            "full_refund_cancelled_order",
            f"I cancelled my order for the {{{{fixture.products.item.name}}}} and would like a full refund, because {reason}.",
            fixture,
            expected,
            {"reason": reason, "refund": "full"},
            "NXC-C1-REFUND-* + refund_order(orderNumber, amount, reason) schema; one cancelled, paid order.",
        )

    def _cancel_not_refund(self) -> GeneratedCandidateCase:
        ((name, price),) = self._products(1)
        reason = self.rng.choice(
            ["I found it cheaper elsewhere", "I no longer need it"]
        )
        refs = ["NXC-C1-CANCEL-TOOL"]
        fixture = {
            "products": [self._product("item", name, price)],
            "orders": [
                {
                    "alias": "target",
                    "status": "PENDING",
                    "items": [{"productAlias": "item", "quantity": 1}],
                }
            ],
        }
        expected = [
            self._required(
                "cancel_order",
                [self._order_number("target", refs), self._non_blank("reason", refs)],
                refs,
            ),
            *self._forbid({"cancel_order"}, refs),
        ]
        return self._case(
            CaseCategory.WRONG_TOOL_SELECTION,
            "cancel_pending_order",
            f"Please cancel my order for the {{{{fixture.products.item.name}}}} - {reason}.",
            fixture,
            expected,
            {"reason": reason},
            "NXC-C1-CANCEL-TOOL + cancel_order(orderNumber, reason); unpaid PENDING order, so no refund is due.",
        )

    def _status_read_only(self) -> GeneratedCandidateCase:
        ((name, price),) = self._products(1)
        refs = ["NXC-C1-READ-ONLY"]
        fixture = {
            "products": [self._product("item", name, price)],
            "orders": [
                {
                    "alias": "target",
                    "status": "CONFIRMED",
                    "isPaid": True,
                    "items": [{"productAlias": "item", "quantity": 1}],
                }
            ],
        }
        expected = [
            self._required(
                "get_order", [self._order_number("target", refs)], refs, max_count=None
            ),
            *self._forbid(set(), refs),
        ]
        return self._case(
            CaseCategory.WRONG_TOOL_SELECTION,
            "order_status_read_only",
            "What is the current status of my order {{fixture.orders.target.orderNumber}}?",
            fixture,
            expected,
            {},
            "NXC-C1-READ-ONLY + get_order(orderNumber); every state-changing tool from the harness is forbidden.",
        )

    def _list_orders_limit(self, limit: int) -> GeneratedCandidateCase:
        products = self._products(3)
        refs = ["NXC-C1-SCHEMA-REQUIRED"]
        fixture = {
            "products": [
                self._product(f"p{i}", name, price)
                for i, (name, price) in enumerate(products)
            ],
            "orders": [
                {
                    "alias": f"o{i}",
                    "status": "CONFIRMED",
                    "isPaid": True,
                    "createdMinutesAgo": 30 * (len(products) - i),
                    "items": [{"productAlias": f"p{i}", "quantity": 1}],
                }
                for i in range(len(products))
            ],
        }
        expected = [
            self._required(
                "list_orders",
                [
                    self._typed("limit", "integer", refs),
                    self._bound("limit", NEXACART_REQUEST_RECORD, "limit", refs),
                ],
                refs,
                max_count=None,
            ),
            *self._forbid(set(), refs),
        ]
        return self._case(
            CaseCategory.MISSING_ARGUMENTS,
            f"list_last_{limit}_orders",
            f"Show me my {limit} most recent orders.",
            fixture,
            expected,
            {"limit": limit},
            "NXC-C1-SCHEMA-REQUIRED: list_orders marks 'limit' required (integer 1-20).",
        )

    def _refund_all_arguments(self) -> GeneratedCandidateCase:
        ((name, price),) = self._products(1)
        reason = self.rng.choice(REASONS)
        refs = ["NXC-C1-REFUND-REASON", "NXC-C1-REFUND-TARGET"]
        fixture = {
            "products": [self._product("item", name, price)],
            "orders": [
                {
                    "alias": "target",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "items": [{"productAlias": "item", "quantity": 1}],
                }
            ],
        }
        # orderNumber and reason presence are part of their value checks below.
        amount_present = ArgumentConstraint(
            argument_name="amount",
            presence=FieldPresence.REQUIRED_NON_NULL,
            requirement_refs=["NXC-C1-SCHEMA-REQUIRED"],
        )
        expected = [
            self._required(
                "refund_order",
                [
                    self._order_number("target", refs[1:]),
                    amount_present,
                    self._non_blank("reason", refs[:1]),
                ],
                [*refs, "NXC-C1-SCHEMA-REQUIRED"],
            ),
            *self._forbid({"refund_order"}, refs[1:]),
        ]
        return self._case(
            CaseCategory.MISSING_ARGUMENTS,
            "refund_with_reason",
            f"My {{{{fixture.products.item.name}}}} order was cancelled. Please refund it - {reason}.",
            fixture,
            expected,
            {"reason": reason},
            "NXC-C1-SCHEMA-REQUIRED: refund_order requires orderNumber, amount and reason.",
        )

    def _add_to_cart(self, quantity: int) -> GeneratedCandidateCase:
        (name, price), (other, other_price) = self._products(2)
        refs = ["NXC-C1-CART-ADD"]
        fixture = {
            "products": [
                self._product("target", name, price),
                self._product("other", other, other_price),
            ],
            "cart": {"create": True, "items": []},
        }
        expected = [
            self._required(
                "add_to_cart",
                [
                    self._typed("productId", "integer", refs),
                    self._bound(
                        "productId",
                        NEXACART_LIVE_FIXTURE_RECORD,
                        "products.target.id",
                        refs,
                    ),
                    self._typed("quantity", "integer", refs),
                    self._bound("quantity", NEXACART_REQUEST_RECORD, "quantity", refs),
                    self._typed("expectedCartVersion", "integer", refs),
                    self._bound(
                        "expectedCartVersion",
                        NEXACART_LIVE_FIXTURE_RECORD,
                        "cartVersion",
                        refs,
                    ),
                ],
                refs,
            ),
            *self._forbid({"add_to_cart"}, refs),
        ]
        units = "unit" if quantity == 1 else "units"
        return self._case(
            CaseCategory.MALFORMED_ARGUMENT_NAMES_OR_TYPES,
            f"add_{quantity}_to_cart",
            f"Please add {quantity} {units} of {{{{fixture.products.target.name}}}} to my cart.",
            fixture,
            expected,
            {"quantity": quantity},
            "NXC-C1-CART-ADD: add_to_cart(productId:int, quantity:int, expectedCartVersion:int), additionalProperties false.",
        )

    def _partial_refund(self) -> GeneratedCandidateCase:
        ((name, price),) = self._products(1)
        quantity = 2
        total = float(price) * quantity
        partial = _amount(round(total * self.rng.choice([0.25, 0.4, 0.5]), 2))
        reason = self.rng.choice(REASONS)
        refs = ["NXC-C1-REFUND-AMOUNT", "NXC-C1-REFUND-TARGET"]
        fixture = {
            "products": [self._product("item", name, price)],
            "orders": [
                {
                    "alias": "target",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "items": [{"productAlias": "item", "quantity": quantity}],
                }
            ],
        }
        expected = [
            self._required(
                "refund_order",
                [
                    self._order_number("target", refs[1:]),
                    *self._refund_amount(NEXACART_REQUEST_RECORD, "amount", refs[:1]),
                ],
                refs,
            ),
            *self._forbid({"refund_order"}, refs[1:]),
        ]
        return self._case(
            CaseCategory.INCORRECT_ARGUMENT_VALUES,
            f"partial_refund_{partial.replace('.', '_')}",
            (
                f"Please refund only {partial} USD of my cancelled {{{{fixture.products.item.name}}}} "
                f"order, because {reason}. Keep the rest."
            ),
            fixture,
            expected,
            {"amount": partial, "reason": reason},
            "NXC-C1-REFUND-AMOUNT: the requested partial amount, not the order total.",
        )

    def _refund_cancelled_among_two(self) -> GeneratedCandidateCase:
        (name, price), (other, other_price) = self._products(2)
        reason = self.rng.choice(REASONS)
        refs = ["NXC-C1-REFUND-TARGET", "NXC-C1-REFUND-AMOUNT"]
        fixture = {
            "products": [
                self._product("item", name, price),
                self._product("other", other, other_price),
            ],
            "orders": [
                {
                    "alias": "target",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "createdMinutesAgo": 240,
                    "items": [{"productAlias": "item", "quantity": 1}],
                },
                {
                    "alias": "distractor",
                    "status": "CONFIRMED",
                    "isPaid": True,
                    "createdMinutesAgo": 20,
                    "items": [{"productAlias": "other", "quantity": 1}],
                },
            ],
        }
        expected = [
            self._required(
                "refund_order",
                [
                    self._order_number("target", refs[:1]),
                    *self._refund_amount(
                        NEXACART_LIVE_FIXTURE_RECORD,
                        "orders.target.totalAmount",
                        refs[1:],
                    ),
                ],
                refs,
            ),
            *self._forbid({"refund_order"}, refs[:1]),
        ]
        return self._case(
            CaseCategory.CONTEXTUAL_SOURCE_MISMATCH,
            "refund_only_cancelled_order",
            f"Please give me a full refund for my cancelled order, because {reason}.",
            fixture,
            expected,
            {"reason": reason, "refund": "full"},
            "NXC-C1-REFUND-TARGET: two paid orders, only the older one is cancelled (a newer CONFIRMED order is the distractor).",
        )

    def _refund_latest_cancelled(self) -> GeneratedCandidateCase:
        (name, price), (other, other_price) = self._products(2)
        reason = self.rng.choice(REASONS)
        refs = ["NXC-C1-LATEST", "NXC-C1-REFUND-TARGET", "NXC-C1-REFUND-AMOUNT"]
        fixture = {
            "products": [
                self._product("item", name, price),
                self._product("other", other, other_price),
            ],
            "orders": [
                {
                    "alias": "older",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "createdMinutesAgo": 600,
                    "items": [{"productAlias": "other", "quantity": 1}],
                },
                {
                    "alias": "target",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "createdMinutesAgo": 15,
                    "items": [{"productAlias": "item", "quantity": 1}],
                },
            ],
        }
        expected = [
            self._required(
                "refund_order",
                [
                    self._order_number("target", refs[:2]),
                    *self._refund_amount(
                        NEXACART_LIVE_FIXTURE_RECORD,
                        "orders.target.totalAmount",
                        refs[2:],
                    ),
                ],
                refs,
            ),
            *self._forbid({"refund_order"}, refs[:2]),
        ]
        return self._case(
            CaseCategory.CONTEXTUAL_SOURCE_MISMATCH,
            "refund_most_recent_cancelled",
            f"Please fully refund my most recent cancelled order, because {reason}.",
            fixture,
            expected,
            {"reason": reason, "refund": "full", "which": "most recent cancelled"},
            "NXC-C1-LATEST: two cancelled, paid orders; the one placed last is the target (proposal example).",
        )

    def _refund_by_product(self) -> GeneratedCandidateCase:
        (name, price), (other, other_price) = self._products(2)
        reason = self.rng.choice(REASONS)
        refs = ["NXC-C1-REFUND-TARGET", "NXC-C1-REFUND-AMOUNT"]
        fixture = {
            "products": [
                self._product("item", name, price),
                self._product("other", other, other_price),
            ],
            "orders": [
                {
                    "alias": "distractor",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "createdMinutesAgo": 30,
                    "items": [{"productAlias": "other", "quantity": 1}],
                },
                {
                    "alias": "target",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "createdMinutesAgo": 90,
                    "items": [{"productAlias": "item", "quantity": 1}],
                },
            ],
        }
        expected = [
            self._required(
                "refund_order",
                [
                    self._order_number("target", refs[:1]),
                    *self._refund_amount(
                        NEXACART_LIVE_FIXTURE_RECORD,
                        "orders.target.totalAmount",
                        refs[1:],
                    ),
                ],
                refs,
            ),
            *self._forbid({"refund_order"}, refs[:1]),
        ]
        return self._case(
            CaseCategory.CONTEXTUAL_SOURCE_MISMATCH,
            "refund_cancelled_order_by_product",
            (
                f"Please fully refund my cancelled order that contained the "
                f"{{{{fixture.products.item.name}}}}, because {reason}."
            ),
            fixture,
            expected,
            {"reason": reason, "refund": "full"},
            "NXC-C1-REFUND-TARGET: two cancelled, paid orders; the product named by the customer identifies the target.",
        )

    def _ambiguous_refund(self) -> GeneratedCandidateCase:
        (name, price), (other, other_price) = self._products(2)
        refs = ["NXC-C1-CLARIFY"]
        fixture = {
            "products": [
                self._product("first", name, price),
                self._product("second", other, other_price),
            ],
            "orders": [
                {
                    "alias": "first",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "createdMinutesAgo": 60,
                    "items": [{"productAlias": "first", "quantity": 1}],
                },
                {
                    "alias": "second",
                    "status": "CANCELLED",
                    "isPaid": True,
                    "createdMinutesAgo": 50,
                    "items": [{"productAlias": "second", "quantity": 1}],
                },
            ],
        }
        return self._case(
            CaseCategory.INSUFFICIENT_EVIDENCE,
            "ambiguous_refund_request",
            "I want a refund for my cancelled order.",
            fixture,
            self._forbid(set(), refs),
            {},
            "NXC-C1-CLARIFY: two cancelled, paid orders and a request that names neither.",
            evidence_limitations=(
                "The request does not say which of the customer's two cancelled, paid orders to "
                "refund, so no expected orderNumber or amount can be derived from the records. "
                "The only checkable requirement is that no state-changing tool is called before "
                "the customer clarifies."
            ),
        )

    # -- entry point ---------------------------------------------------------

    def _scenarios(
        self,
    ) -> dict[CaseCategory, list[Callable[[], GeneratedCandidateCase]]]:
        limit = self.rng.choice([2, 3, 4])
        quantity = self.rng.choice([2, 3])
        return {
            CaseCategory.CORRECT_BEHAVIOUR: [self._full_refund, self._full_refund],
            CaseCategory.WRONG_TOOL_SELECTION: [
                self._cancel_not_refund,
                self._status_read_only,
            ],
            CaseCategory.MISSING_ARGUMENTS: [
                lambda: self._list_orders_limit(limit),
                self._refund_all_arguments,
            ],
            CaseCategory.MALFORMED_ARGUMENT_NAMES_OR_TYPES: [
                lambda: self._add_to_cart(quantity),
                lambda: self._add_to_cart(1),
            ],
            CaseCategory.INCORRECT_ARGUMENT_VALUES: [
                self._partial_refund,
                self._partial_refund,
            ],
            CaseCategory.CONTEXTUAL_SOURCE_MISMATCH: [
                self._refund_latest_cancelled,
                self._refund_cancelled_among_two,
                self._refund_by_product,
            ],
            CaseCategory.INSUFFICIENT_EVIDENCE: [self._ambiguous_refund],
        }

    def generate_all_candidates(self) -> list[GeneratedCandidateCase]:
        target_tools = set(self.request.tool_names or self.tools)
        target_reqs = set(self.request.requirement_ids or self.requirement_ids)
        scenarios = self._scenarios()
        candidates: list[GeneratedCandidateCase] = []
        for category in self.request.case_categories:
            for build in scenarios.get(category, []):
                if len(candidates) >= self.request.max_candidates:
                    return candidates
                case = build()
                required = {
                    s.tool_name
                    for s in case.expected_tool_calls
                    if not s.is_forbidden and s.min_count > 0
                }
                # Respect the requested tool / requirement scope.
                if required and not required <= target_tools:
                    continue
                if not set(case.requirement_refs) & target_reqs:
                    continue
                candidates.append(case)
        return candidates


def validate_nexacart_live_case(
    candidate: GeneratedCandidateCase,
) -> list[ValidationIssue]:
    """Live-feasibility checks on top of ``validate_candidate_case``.

    The fixture must be creatable by the harness, every expected value must be resolvable from a
    planned fixture record or a fact the customer stated, and the task may only reveal values a
    customer can see.
    """
    issues: list[ValidationIssue] = []
    path = f"candidates[{candidate.case_id}]"
    fixture = candidate.fixture_plan.starting_conditions.get("nexacart_fixture")
    if not isinstance(fixture, dict):
        return [
            ValidationIssue(
                code="ERR_NXC_NO_FIXTURE",
                severity=ValidationSeverity.ERROR,
                message="Live NexaCart cases need a harness fixture definition.",
                path=f"{path}.fixture_plan.starting_conditions",
            )
        ]
    products = {p.get("alias") for p in fixture.get("products", [])}
    orders = {o.get("alias") for o in fixture.get("orders", [])}
    has_cart = fixture.get("cart", {}).get("create", True)
    for order in fixture.get("orders", []):
        for item in order.get("items", []):
            if item.get("productAlias") not in products:
                issues.append(
                    ValidationIssue(
                        code="ERR_NXC_UNKNOWN_PRODUCT_ALIAS",
                        severity=ValidationSeverity.ERROR,
                        message=f"Order '{order.get('alias')}' item references unknown product '{item.get('productAlias')}'.",
                        path=f"{path}.fixture_plan",
                    )
                )

    def planned(source_path: str) -> bool:
        parts = source_path.split(".")
        if parts[0] == "orders":
            return len(parts) == 3 and parts[1] in orders
        if parts[0] == "products":
            return len(parts) == 3 and parts[1] in products
        if parts[0] in ("cartVersion", "cartId"):
            return bool(has_cart)
        return parts[0] in ("customerId", "customerEmail", "shippingAddressId")

    stated_values: set[str] = set()
    for placeholder in PLACEHOLDER_RE.findall(candidate.agent_task_prompt):
        if not ALLOWED_PLACEHOLDER_RE.match(placeholder):
            issues.append(
                ValidationIssue(
                    code="ERR_NXC_TASK_PLACEHOLDER",
                    severity=ValidationSeverity.ERROR,
                    message=f"Task placeholder '{placeholder}' is not a customer-visible value.",
                    path=f"{path}.agent_task_prompt",
                )
            )
        elif not planned(placeholder.split(".", 1)[1]):
            issues.append(
                ValidationIssue(
                    code="ERR_NXC_UNPLANNED_SOURCE",
                    severity=ValidationSeverity.ERROR,
                    message=f"Task placeholder '{placeholder}' refers to a record the fixture does not create.",
                    path=f"{path}.agent_task_prompt",
                )
            )
        stated_values.add(placeholder.split(".", 1)[1])

    for spec in candidate.expected_tool_calls:
        for constraint in spec.argument_constraints:
            rel = constraint.source_relationship
            if rel is None:
                continue
            where = f"{path}.expected_tool_calls[{spec.tool_name}].{constraint.argument_name}"
            if rel.source_record_id == NEXACART_LIVE_FIXTURE_RECORD:
                if not planned(rel.source_path):
                    issues.append(
                        ValidationIssue(
                            code="ERR_NXC_UNPLANNED_SOURCE",
                            severity=ValidationSeverity.ERROR,
                            message=f"Expected value source 'fixture.{rel.source_path}' is not created by the fixture.",
                            path=where,
                        )
                    )
                elif rel.source_path in stated_values:
                    issues.append(
                        ValidationIssue(
                            code="WARN_NXC_EXPECTED_VALUE_IN_TASK",
                            severity=ValidationSeverity.WARNING,
                            message=(
                                f"The task states 'fixture.{rel.source_path}' itself; this check "
                                "verifies that the agent uses the quoted value, not that it finds it."
                            ),
                            path=where,
                        )
                    )
            elif rel.source_record_id == NEXACART_REQUEST_RECORD:
                if rel.source_path not in candidate.task_context_inputs:
                    issues.append(
                        ValidationIssue(
                            code="ERR_NXC_UNSTATED_REQUEST_FACT",
                            severity=ValidationSeverity.ERROR,
                            message=f"Expected value 'request.{rel.source_path}' is not a fact stated in the task.",
                            path=where,
                        )
                    )
                elif (
                    str(candidate.task_context_inputs[rel.source_path])
                    not in candidate.agent_task_prompt
                ):
                    issues.append(
                        ValidationIssue(
                            code="ERR_NXC_UNSTATED_REQUEST_FACT",
                            severity=ValidationSeverity.ERROR,
                            message=f"Request fact '{rel.source_path}' does not appear in the task text.",
                            path=where,
                        )
                    )
            elif rel.source_record_id == NEXACART_CUSTOMER_RECORDS:
                if rel.source_path != "orderNumbers" or not orders:
                    issues.append(
                        ValidationIssue(
                            code="ERR_NXC_UNPLANNED_SOURCE",
                            severity=ValidationSeverity.ERROR,
                            message=(
                                f"'customer_records.{rel.source_path}' is not derivable: only "
                                "orderNumbers of fixture orders are recorded."
                            ),
                            path=where,
                        )
                    )
            else:
                issues.append(
                    ValidationIssue(
                        code="ERR_NXC_UNKNOWN_SOURCE_RECORD",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Source record '{rel.source_record_id}' is not 'fixture', 'request' "
                            "or 'customer_records'."
                        ),
                        path=where,
                    )
                )

    required = {
        s.tool_name for s in candidate.expected_tool_calls if not s.is_forbidden
    }
    forbidden = {s.tool_name for s in candidate.expected_tool_calls if s.is_forbidden}
    if required & forbidden:
        issues.append(
            ValidationIssue(
                code="ERR_CONTRADICTORY_CONSTRAINT",
                severity=ValidationSeverity.ERROR,
                message=f"Tools both required and forbidden: {sorted(required & forbidden)}.",
                path=f"{path}.expected_tool_calls",
            )
        )
    return issues
