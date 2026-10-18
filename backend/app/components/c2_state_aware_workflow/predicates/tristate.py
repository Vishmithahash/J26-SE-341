"""Three-valued logic (Kleene logic) implementation for C2 workflow predicates.

In three-valued logic:
- FALSE AND UNKNOWN = FALSE
- TRUE AND UNKNOWN = UNKNOWN
- TRUE OR UNKNOWN = TRUE
- NOT UNKNOWN = UNKNOWN

Explicit TriState comparisons are enforced; Python truthiness evaluation is disallowed.
"""

from enum import Enum
from typing import Any, Self


class TriState(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

    def is_true(self) -> bool:
        return self == TriState.TRUE

    def is_false(self) -> bool:
        return self == TriState.FALSE

    def is_unknown(self) -> bool:
        return self == TriState.UNKNOWN

    def __bool__(self) -> bool:
        raise TypeError(
            "Direct boolean coercion of TriState is forbidden. "
            "Use .is_true(), .is_false(), .is_unknown(), or compare explicitly with TriState.TRUE / FALSE / UNKNOWN."
        )

    def land(self, other: "TriState") -> "TriState":
        if not isinstance(other, TriState):
            raise TypeError(f"Operand must be TriState, got {type(other).__name__}")
        if self == TriState.FALSE or other == TriState.FALSE:
            return TriState.FALSE
        if self == TriState.UNKNOWN or other == TriState.UNKNOWN:
            return TriState.UNKNOWN
        return TriState.TRUE

    def lor(self, other: "TriState") -> "TriState":
        if not isinstance(other, TriState):
            raise TypeError(f"Operand must be TriState, got {type(other).__name__}")
        if self == TriState.TRUE or other == TriState.TRUE:
            return TriState.TRUE
        if self == TriState.UNKNOWN or other == TriState.UNKNOWN:
            return TriState.UNKNOWN
        return TriState.FALSE

    def lnot(self) -> "TriState":
        if self == TriState.TRUE:
            return TriState.FALSE
        if self == TriState.FALSE:
            return TriState.TRUE
        return TriState.UNKNOWN

    def __and__(self, other: "TriState") -> "TriState":
        return self.land(other)

    def __or__(self, other: "TriState") -> "TriState":
        return self.lor(other)

    def __invert__(self) -> "TriState":
        return self.lnot()


class MissingType:
    """Sentinel representing a missing observation (distinct from explicit null/None)."""

    _instance = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<MISSING_OBSERVATION>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MissingType)

    def __hash__(self) -> int:
        return hash("<MISSING_OBSERVATION>")


MISSING = MissingType()


def is_missing(val: Any) -> bool:
    return isinstance(val, MissingType)
