"""AgentCore Platform v1.0 — SVC-C2-016"""

# Outer post_process node. Captures completion data for invoicing/SLA
# reporting once the inner Cat 2 subgraph has dispatched a technician and
# generated a work order (fields merged in from the GraphNode's
# merge_output()).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class CompletionCaptureNode(FunctionNode):
    """Outer post_process — capture completion data for invoicing/SLA reporting."""

    # S-1: outer boundary node — matches config/agent.yaml agent.required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-3 preservation variant: formatted_output must keep work_order_text
        when a work order was actually captured (own-dict self-consistency —
        re-checks the exact key execute() returns in formatted_output, not an
        upstream/input field). Non-raising per contract.
        """
        formatted = state.get("formatted_output")
        if (
            state.get("completion_status") == "captured"
            and isinstance(formatted, dict)
            and not formatted.get("work_order_text")
        ):
            return {
                **state,
                "status": AgentStatus.ERROR.value,
                "error_log": (state.get("error_log") or [])
                + ["CompletionCaptureNode: work_order_text missing from output — preservation check failed"],
            }
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        work_order_id = state.get("work_order_id")
        dispatch_status = state.get("dispatch_status")

        if not work_order_id or dispatch_status != "dispatched":
            emit_trace_event(
                "completion_capture_skipped",
                {"correlation_id": state.get("correlation_id")},
                state,
            )
            return {
                "completion_status": "not_dispatched",
                "formatted_output": {"status": "not_dispatched"},
                "status": state.get("status", AgentStatus.ERROR.value),
            }

        completion_record = {
            "request_id": state.get("request_id"),
            "work_order_id": work_order_id,
            "technician_id": (state.get("selected_technician") or {}).get("technician_id"),
            "dispatch_notification_id": state.get("dispatch_notification_id"),
            "eta_minutes": (state.get("route_plan") or {}).get("eta_minutes"),
            "parts_list": state.get("parts_list", []),
        }
        emit_trace_event(
            "completion_captured",
            {"correlation_id": state.get("correlation_id"), "work_order_id": work_order_id},
            state,
        )
        return {
            "completion_status": "captured",
            "completion_record": completion_record,
            "formatted_output": {
                "work_order_id": work_order_id,
                "work_order_text": state.get("work_order_text"),
                "dispatch_status": dispatch_status,
                "completion_record": completion_record,
            },
            "status": AgentStatus.SUCCESS.value,
        }
