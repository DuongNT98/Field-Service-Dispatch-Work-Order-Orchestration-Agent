"""AgentCore Platform v1.0 — SVC-C2-016"""

# Inner subgraph step 3 — dispatches the selected technician (notification)
# and emits the S-4 audit event for the dispatch decision.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class DispatchNode(FunctionNode):
    """Inner subgraph step 3 — dispatch notification to the selected technician."""

    # S-1: inner subgraph node — trust authenticated at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        technician = state.get("selected_technician") or {}
        route_plan = state.get("route_plan") or {}

        # S-4: emit before the first branch so both the reject and success paths trace.
        emit_trace_event(
            "dispatch_requested",
            {"correlation_id": state.get("correlation_id"), "technician_id": technician.get("technician_id")},
            state,
        )

        if not technician.get("technician_id"):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["DispatchNode: no technician selected to dispatch"],
            }

        notification_id = f"disp-{technician.get('technician_id')}-{state.get('correlation_id', 'na')}"
        emit_trace_event(
            "technician_dispatched",
            {
                "correlation_id": state.get("correlation_id"),
                "technician_id": technician.get("technician_id"),
                "eta_minutes": route_plan.get("eta_minutes"),
            },
            state,
        )
        return {
            "dispatch_status": "dispatched",
            "dispatch_notification_id": notification_id,
            "status": AgentStatus.SUCCESS.value,
        }
