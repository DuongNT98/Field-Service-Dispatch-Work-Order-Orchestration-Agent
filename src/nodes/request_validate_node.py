"""AgentCore Platform v1.0 — SVC-C2-016"""

# Outer pre_process node. Validates + normalizes the inbound field-service
# request JSON, then serializes it into validated_input for the inner
# Cat 2 subgraph (GraphNode.extract_input() reads validated_input; the inner
# subgraph receives ONLY that string, per the Cat 2 architecture pattern).

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

MAX_INPUT_LENGTH = 20_000


class RequestValidateNode(FunctionNode):
    """Outer pre_process — validate + normalize the field-service request."""

    # S-1: outer boundary node — receives input directly from the caller;
    # trust level matches config/agent.yaml agent.required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2: domain input-size guard on the raw payload before parsing.

        Non-raising per contract — returns state unchanged on success, or an
        ERROR delta on violation. Runs after the framework's default PII scan.
        """
        raw = state.get("user_input", "") or ""
        if len(raw) > MAX_INPUT_LENGTH:
            return {
                **state,
                "status": AgentStatus.ERROR.value,
                "error_log": (state.get("error_log") or []) + ["RequestValidateNode: input payload exceeds size limit"],
            }
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        emit_trace_event(
            "field_service_request_received",
            {"correlation_id": state.get("correlation_id"), "raw_length": len(raw or "")},
            state,
        )

        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RequestValidateNode: user_input is not a valid JSON object"],
            }

        request_id = payload.get("request_id")
        required_skills = payload.get("required_skills") or []
        technician_roster = payload.get("technician_roster") or []
        customer_location = payload.get("customer_location") or {}

        if not request_id or not isinstance(required_skills, list) or not technician_roster:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RequestValidateNode: missing request_id, required_skills, or technician_roster"],
            }

        normalized = {
            "request_id": request_id,
            "service_type": payload.get("service_type", "general"),
            "priority": payload.get("priority", "normal"),
            "customer_location": customer_location,
            "required_skills": required_skills,
            "technician_roster": technician_roster,
        }
        return {
            "request_id": request_id,
            "service_type": normalized["service_type"],
            "priority": normalized["priority"],
            "customer_location": customer_location,
            "required_skills": required_skills,
            "technician_roster": technician_roster,
            "validated_input": json.dumps(normalized, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
