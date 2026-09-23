"""AgentCore Platform v1.0 — SVC-C2-016 (inner Cat 2 domain workflow)"""

# Inner graph for the Cat 2 field-service dispatch pipeline. Instantiated by
# FieldServiceGraphNode.get_subgraph() in src/graph/graph.py.
#
# Topology: START → technician_score → route_optimize → dispatch → work_order → END
#
# Inherits BaseGraph directly (fully custom node topology, no pre/main/post
# slots). Receives ONLY user_input (a JSON string set by the outer
# RequestValidateNode) + ctx — NOT the outer state (cat2-pattern.md).

from typing import Any

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from src.nodes.dispatch_node import DispatchNode
from src.nodes.route_optimize_node import RouteOptimizeNode
from src.nodes.technician_score_node import TechnicianScoreNode
from src.nodes.work_order_node import WorkOrderNode
from src.schemas.state import State


class FieldServiceWorkflowGraph(BaseGraph):
    """Inner graph: technician scoring → route optimization → dispatch → work order."""

    @property
    def name(self) -> str:
        return "field_service_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        # No mandatory config keys for this inner workflow.
        pass

    def register_nodes(self) -> None:
        # No super() call — BaseGraph.register_nodes() is abstract. Do NOT
        # register initialize/finalize here (outer backbone concern).
        # WorkOrderNode resolves its own LLM client per invocation from
        # ctx.secrets (see src/nodes/work_order_node.py) — it is never
        # constructor-injected in production, only by unit tests.
        self._nodes["technician_score"] = TechnicianScoreNode()
        self._nodes["route_optimize"] = RouteOptimizeNode()
        self._nodes["dispatch"] = DispatchNode()
        self._nodes["work_order"] = WorkOrderNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "technician_score")
        self._sg.add_edge("technician_score", "route_optimize")
        self._sg.add_edge("route_optimize", "dispatch")
        self._sg.add_edge("dispatch", "work_order")
        self._sg.add_edge("work_order", END)

    def route(self, state: AgentState) -> str:
        # Required by BaseGraph ABC; this topology is linear (never called
        # unless add_conditional_edges() references it).
        return END if state.get("status") == AgentStatus.ERROR.value else "work_order"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        """Shape sub_result for the outer FieldServiceGraphNode.merge_output()."""
        return {
            "scored_technicians": state.get("scored_technicians", []),
            "selected_technician": state.get("selected_technician"),
            "route_plan": state.get("route_plan"),
            "dispatch_status": state.get("dispatch_status"),
            "dispatch_notification_id": state.get("dispatch_notification_id"),
            "work_order_id": state.get("work_order_id"),
            "work_order_text": state.get("work_order_text"),
            "parts_list": state.get("parts_list", []),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
