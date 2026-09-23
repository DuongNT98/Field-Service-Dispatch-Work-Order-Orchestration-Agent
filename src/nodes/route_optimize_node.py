"""AgentCore Platform v1.0 — SVC-C2-016"""

# Inner subgraph step 2 — picks the top-scored technician and computes a
# route/ETA estimate via the route_optimization_service Tool.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.route_optimization_service import optimize_route


class RouteOptimizeNode(FunctionNode):
    """Inner subgraph step 2 — route/ETA optimization for the top-scored technician."""

    # S-1: inner subgraph node — trust authenticated at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        scored = state.get("scored_technicians") or []
        customer_location = state.get("customer_location") or {}

        # S-4: emit before the first branch so both the reject and success paths trace.
        emit_trace_event(
            "route_optimization_requested",
            {"correlation_id": state.get("correlation_id"), "candidate_count": len(scored)},
            state,
        )

        if not scored:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RouteOptimizeNode: no scored technicians available"],
            }

        top = scored[0]
        route_plan = optimize_route(top, customer_location)
        emit_trace_event(
            "route_optimized",
            {"correlation_id": state.get("correlation_id"), "technician_id": top.get("technician_id")},
            state,
        )
        return {
            "selected_technician": top,
            "route_plan": route_plan,
            "status": AgentStatus.SUCCESS.value,
        }
