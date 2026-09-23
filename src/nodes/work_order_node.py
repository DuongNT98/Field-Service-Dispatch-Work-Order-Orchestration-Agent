"""AgentCore Platform v1.0 — SVC-C2-016"""

# Inner subgraph step 4 — LLM-essential node. Generates the work-order text
# (parts-list narrative) for the dispatched technician. This is the one node
# in the pipeline where an LLM call adds value beyond deterministic logic
# (see docs/02_design.md "Node-vs-Tool / LLM split").
#
# LLM wiring (Azure OpenAI): the client is built fresh per invocation, inside
# execute(), from three declared secrets (config/agent.yaml requires.secrets) —
# never cached on self, never built at __init__/register_nodes() time, since
# node instances are constructed once and reused across invocations. Any
# failure (missing secret, API error, malformed response) degrades to the
# pre-existing deterministic work-order narrative below — this node never
# raises and never sets status=error for an LLM problem.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


def _resolve_llm(constructor_llm: Any, state: dict[str, Any]) -> Any:
    """Test-double seam (constructor_llm) wins first; production always resolves here.

    Never raises — any failure (missing secret, malformed InvocationContext)
    means "no LLM available this call", handled by the deterministic fallback.
    """
    if constructor_llm is not None:
        return constructor_llm
    try:
        from shared.services.llm.azure_openai_client import AzureOpenAIClient

        ctx = InvocationContext.from_state(state)
        return AzureOpenAIClient(
            {
                "api_key": ctx.secrets.require("AZURE_OPENAI_API_KEY"),
                "azure_endpoint": ctx.secrets.require("AZURE_OPENAI_ENDPOINT"),
                "azure_deployment": ctx.secrets.require("AZURE_OPENAI_DEPLOYMENT"),
            }
        )
    except Exception:
        return None


# Minimal deterministic skill -> common-parts lookup (fallback / augmentation,
# not the primary work-order content — that comes from the LLM narrative).
_SKILL_PARTS_HINTS: dict[str, list[str]] = {
    "networking": ["ethernet cable", "patch panel", "SFP module"],
    "electrical": ["circuit breaker", "wire nuts", "voltage tester"],
    "hvac": ["refrigerant", "air filter", "thermostat"],
    "plumbing": ["pipe fitting", "sealant", "valve"],
}


def _infer_parts_list(required_skills: list[str]) -> list[str]:
    parts: list[str] = []
    for skill in required_skills or []:
        parts.extend(_SKILL_PARTS_HINTS.get(skill.lower(), []))
    return sorted(set(parts))


class WorkOrderNode(FunctionNode):
    """Inner subgraph step 4 — generate the work order text + parts list (LLM-essential)."""

    # S-1: inner subgraph node — trust authenticated at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None):
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        technician = state.get("selected_technician") or {}
        route_plan = state.get("route_plan") or {}
        required_skills = state.get("required_skills") or []
        service_type = state.get("service_type") or "general"

        # S-4: emit before the first branch so both the reject and success paths trace.
        emit_trace_event(
            "work_order_requested",
            {"correlation_id": state.get("correlation_id"), "technician_id": technician.get("technician_id")},
            state,
        )

        if not technician.get("technician_id"):
            return {"status": AgentStatus.ERROR.value, "error_log": ["WorkOrderNode: no technician selected"]}

        work_order_text = None
        llm = _resolve_llm(self._llm, state)
        if llm is not None:
            try:
                prompt = (
                    "Generate a concise field-service work order.\n"
                    f"Service type: {service_type}\n"
                    f"Required skills: {', '.join(required_skills)}\n"
                    f"Assigned technician: {technician.get('name')} (ID {technician.get('technician_id')})\n"
                    f"Route: {route_plan.get('route_summary', '')}\n"
                )
                # BaseLLM.complete() takes a messages list and returns the canonical
                # dict {content, tool_calls, model, usage} (shared/services/llm/base_llm.py).
                # Anything else (wrong shape, empty content) is treated as a
                # malformed response and falls back to the deterministic narrative.
                llm_response = llm.complete([{"role": "user", "content": prompt}])
                content = llm_response.get("content") if isinstance(llm_response, dict) else None
                work_order_text = content.strip() if isinstance(content, str) and content.strip() else None
            except Exception:
                # Any LLM failure (API error, malformed response) degrades to the
                # deterministic narrative below — never raises, never status=error.
                work_order_text = None

        if work_order_text is None:
            work_order_text = (
                f"Work order for {service_type}: technician {technician.get('name')} "
                f"(ID {technician.get('technician_id')}) dispatched."
            )

        parts_list = _infer_parts_list(required_skills)
        work_order_id = f"wo-{technician.get('technician_id')}-{state.get('correlation_id', 'na')}"
        emit_trace_event(
            "work_order_generated",
            {"correlation_id": state.get("correlation_id"), "work_order_id": work_order_id},
            state,
        )
        return {
            "work_order_id": work_order_id,
            "work_order_text": work_order_text,
            "parts_list": parts_list,
            "status": AgentStatus.SUCCESS.value,
        }
