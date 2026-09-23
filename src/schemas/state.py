"""AgentCore Platform v1.0 — SVC-C2-016 Field Service Dispatch & Work Order Orchestration Agent"""

# ADR-005: State must be a flat TypedDict. LangGraph checkpoints use msgpack
# serialization, so only plain serializable fields are allowed. No credentials,
# no Pydantic/dataclass, no InvocationContext in State.
#
# Every agent-specific field is wrapped in NotRequired[...] (CoE standard C8):
# a bare field is flagged because (a) it may be absent from a checkpoint →
# msgpack failure on resume; (b) a non-NotRequired scalar/dict raises KeyError
# when a downstream node runs before the field is written.

from typing import Any, NotRequired

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state for the field-service dispatch + work-order orchestration pipeline."""

    # mypy can't see that AgentState is a runtime TypedDict without SDK stubs, so it
    # rejects every NotRequired[...] field as used outside a TypedDict definition.
    # Stub-visibility limitation, not a code error — each field really is optional/
    # JSON-safe at runtime (ADR-005).

    # ── Request intake (outer pre_process: RequestValidateNode) ────────────
    request_id: NotRequired[str]  # type: ignore[valid-type]
    service_type: NotRequired[str]  # type: ignore[valid-type]
    priority: NotRequired[str]  # type: ignore[valid-type]
    customer_location: NotRequired[dict[str, Any]]  # type: ignore[valid-type]
    required_skills: NotRequired[list[str]]  # type: ignore[valid-type]
    technician_roster: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]

    # ── Score + route (inner: TechnicianScoreNode / RouteOptimizeNode) ──────
    scored_technicians: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    selected_technician: NotRequired[dict[str, Any]]  # type: ignore[valid-type]
    route_plan: NotRequired[dict[str, Any]]  # type: ignore[valid-type]

    # ── Dispatch + work order (inner: DispatchNode / WorkOrderNode) ────────
    dispatch_status: NotRequired[str]  # type: ignore[valid-type]
    dispatch_notification_id: NotRequired[str]  # type: ignore[valid-type]
    work_order_id: NotRequired[str]  # type: ignore[valid-type]
    work_order_text: NotRequired[str]  # type: ignore[valid-type]
    parts_list: NotRequired[list[str]]  # type: ignore[valid-type]

    # ── Completion capture (outer post_process: CompletionCaptureNode) ─────
    completion_status: NotRequired[str]  # type: ignore[valid-type]
    completion_record: NotRequired[dict[str, Any]]  # type: ignore[valid-type]
