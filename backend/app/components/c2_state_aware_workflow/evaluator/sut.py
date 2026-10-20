"""Resettable in-process synthetic System Under Test (SUT) for C2 workflow demonstrations.

Provides an independent, mutable application state and realistic business tools
for the NexaCart refund domain (and configurable variations with different entity IDs).
Does NOT reference EFSM models, solution paths, or oracle expectations.
"""

import copy
from datetime import UTC, datetime
from typing import Any


class SyntheticRefundSUT:
    """In-process mock SUT maintaining independent mutable application state.

    Tools provided:
    - get_customer_orders(customer_id)
    - select_order(customer_id, order_id)
    - inspect_order_details(order_id)
    - request_refund(customer_id, order_id, reason)
    - verify_refund_status(refund_id)
    """

    def __init__(self, initial_fixture: dict[str, Any] | None = None):
        self._initial_fixture = initial_fixture
        self.reset(initial_fixture)

    def reset(self, fixture_data: dict[str, Any] | None = None) -> None:
        """Reset mutable application state to clean initial baseline."""
        data = fixture_data or self._initial_fixture or {}

        # Default entities if not provided in fixture_data
        customer_id = data.get("customer_id", 42)
        customer_email = data.get(
            "customer_email", f"customer{customer_id}@example.com"
        )
        customer_balance = float(data.get("customer_balance", 0.0))

        # Orders can be passed in fixture_data or use canonical NexaCart defaults
        default_orders = {
            501: {
                "order_id": 501,
                "customer_id": customer_id,
                "status": "PAID",
                "payment_status": "PAID",
                "amount": 45.0,
                "currency": "USD",
                "ordered_at": "2026-10-10T10:00:00Z",
                "items": [
                    {"item_id": 101, "name": "USB-C Cable", "price": 45.0, "qty": 1}
                ],
            },
            502: {
                "order_id": 502,
                "customer_id": customer_id,
                "status": "UNPAID",
                "payment_status": "UNPAID",
                "amount": 120.0,
                "currency": "USD",
                "ordered_at": "2026-10-12T12:00:00Z",
                "items": [
                    {
                        "item_id": 102,
                        "name": "Mechanical Keyboard",
                        "price": 120.0,
                        "qty": 1,
                    }
                ],
            },
            503: {
                "order_id": 503,
                "customer_id": customer_id,
                "status": "PAID",
                "payment_status": "PAID",
                "amount": 85.0,
                "currency": "USD",
                "ordered_at": "2026-10-15T15:00:00Z",
                "items": [
                    {"item_id": 103, "name": "Wireless Mouse", "price": 85.0, "qty": 1}
                ],
            },
        }

        # Override or merge orders from fixture if declared
        orders = default_orders
        if "orders" in data and isinstance(data["orders"], list):
            orders = {}
            for o in data["orders"]:
                oid = int(o["order_id"])
                orders[oid] = copy.deepcopy(o)

        self._state: dict[str, Any] = {
            "customers": {
                customer_id: {
                    "customer_id": customer_id,
                    "email": customer_email,
                    "balance": customer_balance,
                }
            },
            "orders": orders,
            "refunds": {},
            "audit_log": [],
        }

    def get_state_snapshot(self) -> dict[str, Any]:
        """Capture an independent snapshot of current mutable state with flattened query paths."""
        snapshot = copy.deepcopy(self._state)
        # Flattened convenience paths for scoped predicate evaluation
        for oid, order in snapshot["orders"].items():
            snapshot[f"order_{oid}_payment_status"] = order.get("payment_status")
            snapshot[f"order_{oid}_status"] = order.get("status")
        for cid, cust in snapshot["customers"].items():
            snapshot[f"customer_{cid}_balance"] = cust.get("balance")

        # Global latest payment status if any refund processed
        latest_refunded_order = None
        for ref in snapshot["refunds"].values():
            if ref.get("status") == "SUCCESS":
                latest_refunded_order = ref.get("order_id")
        if latest_refunded_order:
            snapshot["payment_status"] = "REFUNDED"
            snapshot["latest_refunded_order_id"] = latest_refunded_order
        else:
            snapshot["payment_status"] = "PENDING"
            snapshot["latest_refunded_order_id"] = None

        return snapshot

    # --- Tool Call Implementations ---

    def get_customer_orders(self, customer_id: int, **kwargs: Any) -> dict[str, Any]:
        """Retrieve list of orders for customer. Read-only operation."""
        customer = self._state["customers"].get(customer_id)
        if not customer:
            return {"status": "ERROR", "error": f"Customer {customer_id} not found."}

        matching_orders = [
            copy.deepcopy(order)
            for order in self._state["orders"].values()
            if order.get("customer_id") == customer_id
        ]
        # Return sorted by ordered_at
        matching_orders.sort(key=lambda x: str(x.get("ordered_at", "")))

        self._state["audit_log"].append(
            {
                "action": "get_customer_orders",
                "customer_id": customer_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        return {
            "status": "SUCCESS",
            "customer_id": customer_id,
            "orders": matching_orders,
            "total_orders": len(matching_orders),
        }

    def select_order(
        self, customer_id: int, order_id: int, **kwargs: Any
    ) -> dict[str, Any]:
        """Select an order for subsequent operations. Verifies ownership."""
        order = self._state["orders"].get(order_id)
        if not order:
            return {"status": "ERROR", "error": f"Order {order_id} not found."}
        if order.get("customer_id") != customer_id:
            return {
                "status": "ERROR",
                "error": f"Order {order_id} does not belong to customer {customer_id}.",
            }

        self._state["audit_log"].append(
            {
                "action": "select_order",
                "customer_id": customer_id,
                "order_id": order_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "customer_id": customer_id,
            "payment_status": order.get("payment_status"),
            "amount": order.get("amount"),
            "ordered_at": order.get("ordered_at"),
        }

    def inspect_order_details(self, order_id: int, **kwargs: Any) -> dict[str, Any]:
        """Inspect detailed line items for an order. Read-only optional step."""
        order = self._state["orders"].get(order_id)
        if not order:
            return {"status": "ERROR", "error": f"Order {order_id} not found."}

        self._state["audit_log"].append(
            {
                "action": "inspect_order_details",
                "order_id": order_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "items": copy.deepcopy(order.get("items", [])),
            "amount": order.get("amount"),
            "payment_status": order.get("payment_status"),
        }

    get_order_details = inspect_order_details

    def request_refund(
        self,
        customer_id: int,
        order_id: int,
        reason: str = "customer_request",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Process refund for specified order.

        Mutates payment status to REFUNDED and logs refund if eligible (PAID).
        Rejects without modifying state if ineligible (UNPAID).
        """
        order = self._state["orders"].get(order_id)
        if not order:
            return {"status": "ERROR", "error": f"Order {order_id} not found."}
        if order.get("customer_id") != customer_id:
            return {
                "status": "ERROR",
                "error": f"Order {order_id} does not belong to customer {customer_id}.",
            }

        # Check eligibility
        if order.get("payment_status") != "PAID":
            self._state["audit_log"].append(
                {
                    "action": "request_refund_rejected",
                    "customer_id": customer_id,
                    "order_id": order_id,
                    "reason": "ORDER_UNPAID",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            return {
                "status": "REJECTED",
                "error": f"Order {order_id} has payment status '{order.get('payment_status')}' and is ineligible for refund.",
            }

        if order.get("payment_status") == "REFUNDED":
            return {
                "status": "ERROR",
                "error": f"Order {order_id} has already been refunded.",
            }

        # Apply state mutation
        order["payment_status"] = "REFUNDED"
        order["status"] = "REFUNDED"
        order["refunded_at"] = datetime.now(UTC).isoformat()

        refund_id = f"ref_{customer_id}_{order_id}_{len(self._state['refunds']) + 1}"
        self._state["refunds"][refund_id] = {
            "refund_id": refund_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": order.get("amount"),
            "status": "SUCCESS",
            "reason": reason,
            "created_at": datetime.now(UTC).isoformat(),
        }

        self._state["audit_log"].append(
            {
                "action": "request_refund_approved",
                "customer_id": customer_id,
                "order_id": order_id,
                "refund_id": refund_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        return {
            "status": "SUCCESS",
            "refund_id": refund_id,
            "order_id": order_id,
            "customer_id": customer_id,
            "amount_refunded": order.get("amount"),
        }

    def verify_refund_status(self, refund_id: str, **kwargs: Any) -> dict[str, Any]:
        """Verify the final status of a refund transaction."""
        ref = self._state["refunds"].get(refund_id)
        if not ref:
            return {
                "status": "ERROR",
                "error": f"Refund record '{refund_id}' not found.",
            }

        self._state["audit_log"].append(
            {
                "action": "verify_refund_status",
                "refund_id": refund_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        return {
            "status": "SUCCESS",
            "refund_id": refund_id,
            "order_id": ref.get("order_id"),
            "customer_id": ref.get("customer_id"),
            "refund_status": ref.get("status"),
            "amount": ref.get("amount"),
        }

    def reject_unpaid_order(
        self,
        customer_id: int,
        order_id: int,
        reason: str = "order_unpaid",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Explicitly record rejection of an ineligible refund request."""
        self._state["audit_log"].append(
            {
                "action": "reject_unpaid_order",
                "customer_id": customer_id,
                "order_id": order_id,
                "reason": reason,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        return {
            "status": "SUCCESS",
            "action": "REJECTED",
            "order_id": order_id,
            "customer_id": customer_id,
            "message": f"Refund request for order {order_id} cleanly rejected: {reason}",
        }
