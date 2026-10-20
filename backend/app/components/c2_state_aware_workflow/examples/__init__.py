"""Reference workflow examples across e-commerce, flight booking, and learning management systems for C2."""

from app.components.c2_state_aware_workflow.examples.ecommerce_workflows import (
    get_address_change_workflow_input,
    get_address_change_workflow_model,
    get_cancellation_workflow_input,
    get_cancellation_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.flight_workflows import (
    get_flight_cancellation_workflow_input,
    get_flight_cancellation_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.lms_workflows import (
    get_course_enrollment_workflow_input,
    get_course_enrollment_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
    get_refund_workflow_input,
)

__all__ = [
    "build_synthetic_refund_efsm",
    "get_address_change_workflow_input",
    "get_address_change_workflow_model",
    "get_cancellation_workflow_input",
    "get_cancellation_workflow_model",
    "get_course_enrollment_workflow_input",
    "get_course_enrollment_workflow_model",
    "get_flight_cancellation_workflow_input",
    "get_flight_cancellation_workflow_model",
    "get_refund_workflow_input",
]
