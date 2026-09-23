"""AgentCore Platform v1.0 — SVC-C2-016 Field Service Dispatch & Work Order Orchestration Agent"""

# Cat 2 outer graph: fixed 5-node AgentBaseGraph backbone
#   START → initialize → pre_process → main(GraphNode) → post_process → finalize → END
# Domain complexity (technician scoring → route optimization → dispatch →
# work-order generation) is encapsulated inside the inner subgraph, wrapped by
# FieldServiceGraphNode at the `main` slot (per the Cat 2 architecture pattern).
#
# ⚠️ FieldServiceGraphNode is defined in THIS file (not under src/nodes/) —
# GraphNode.__call__() deliberately does not run the standard S-1..S-4 node
# lifecycle (it delegates gating to the inner subgraph), so
# tests/proof_of_boundary/test_pb_invoke_order.py (which auto-discovers every
# BaseNode subclass under src/nodes/) must not discover it.

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.graph.base_graph import BaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.nodes.completion_capture_node import CompletionCaptureNode
from src.nodes.request_validate_node import RequestValidateNode
from src.schemas.state import State


class FieldServiceGraphNode(GraphNode):
    """Wraps the inner field-service workflow subgraph; assigned to the `main` slot."""

    # S-1: outer main-slot wrapper — first node in the outer backbone receiving
    # caller input; matches config/agent.yaml agent.required_trust_level and the
    # sibling outer FunctionNodes (RequestValidateNode/CompletionCaptureNode).
    # gate-trust-level-check does not scan GraphNode subclasses, so this is not
    # CI-enforced — declared explicitly per the framework's S-1 security-layer requirement.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    # "propagate": re-raise inner graph exceptions as SubgraphError (fail fast).
    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def get_subgraph(self) -> BaseGraph:
        from src.graph.domain_workflow_graph import FieldServiceWorkflowGraph

        subgraph = FieldServiceWorkflowGraph(config={})
        subgraph.compile()
        return subgraph

    def extract_input(self, state: AgentState) -> str:
        # S-4: runs inside GraphNode.execute() — audit the dispatch into the inner subgraph.
        emit_trace_event(
            "field_service_workflow_dispatched",
            {"correlation_id": state.get("correlation_id")},
            state,
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        # S-4: runs inside GraphNode.execute() — audit the subgraph outcome merged back out.
        # HITL note: this agent has no interrupt(); merge_output always runs on completion.
        emit_trace_event(
            "field_service_workflow_completed",
            {"correlation_id": state.get("correlation_id"), "work_order_id": sub_result.get("work_order_id")},
            state,
        )
        return {
            "scored_technicians": sub_result.get("scored_technicians", []),
            "selected_technician": sub_result.get("selected_technician"),
            "route_plan": sub_result.get("route_plan"),
            "dispatch_status": sub_result.get("dispatch_status"),
            "dispatch_notification_id": sub_result.get("dispatch_notification_id"),
            "work_order_id": sub_result.get("work_order_id"),
            "work_order_text": sub_result.get("work_order_text"),
            "parts_list": sub_result.get("parts_list", []),
            "status": sub_result.get("status"),
        }


class FieldServiceDispatchGraph(AgentBaseGraph):
    """SVC-C2-016 — Field Service Dispatch & Work Order Orchestration Agent (L1 direct)."""

    @property
    def name(self) -> str:
        return "svc-c2-016"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        self._nodes["pre_process"] = RequestValidateNode()
        self._nodes["main"] = FieldServiceGraphNode()
        self._nodes["post_process"] = CompletionCaptureNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.


# Alias for config/agent.yaml `module: "src.graph"` / `class: "FieldServiceDispatchGraph"`
Graph = FieldServiceDispatchGraph
