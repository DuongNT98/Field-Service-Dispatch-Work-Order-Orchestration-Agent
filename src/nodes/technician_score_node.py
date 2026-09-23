"""AgentCore Platform v1.0 — SVC-C2-016"""

# Inner subgraph step 1 (Cat 2 domain workflow — src/graph/domain_workflow_graph.py).
# Scores each roster technician by skill x proximity x availability via the
# technician_scoring_service Tool. The inner subgraph receives ONLY the JSON
# string set by RequestValidateNode (validated_input) as user_input — it does
# NOT see the outer state (per the Cat 2 architecture pattern's data-flow contract).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.technician_scoring_service import score_technicians


class TechnicianScoreNode(FunctionNode):
    """Inner subgraph step 1 — score technicians by skill x proximity x availability."""

    # S-1: inner subgraph node — trust is authenticated once at the outer
    # backbone (RequestValidateNode); an inner node requiring INTERNAL would
    # be a privilege-escalation an external caller could never satisfy.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")

        # S-4: emit before the first branch so both reject paths and success trace.
        emit_trace_event(
            "technician_scoring_requested",
            {"correlation_id": state.get("correlation_id")},
            state,
        )

        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["TechnicianScoreNode: invalid inner input payload"],
            }

        roster = payload.get("technician_roster") or []
        required_skills = payload.get("required_skills") or []
        customer_location = payload.get("customer_location") or {}

        if not roster:
            return {"status": AgentStatus.ERROR.value, "error_log": ["TechnicianScoreNode: empty technician_roster"]}

        scored = score_technicians(required_skills, customer_location, roster)
        emit_trace_event(
            "technicians_scored",
            {"correlation_id": state.get("correlation_id"), "candidate_count": len(scored)},
            state,
        )
        return {
            "request_id": payload.get("request_id"),
            "service_type": payload.get("service_type"),
            "priority": payload.get("priority"),
            "customer_location": customer_location,
            "required_skills": required_skills,
            "technician_roster": roster,
            "scored_technicians": scored,
            "status": AgentStatus.SUCCESS.value,
        }
