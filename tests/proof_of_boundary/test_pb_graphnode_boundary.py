# PB — GraphNode outer-boundary coverage (SVC-C2-016).
#
# PB-6 (test_pb_invoke_order.py) only auto-discovers BaseNode subclasses under
# src/nodes/. FieldServiceGraphNode lives in src/graph/graph.py (correct scaffold
# placement for a Cat 2 outer main-slot wrapper — avoids probing the whole inner
# subgraph through a single-node discovery loop), which puts it outside PB-6's
# scope. This file closes that gap: FieldServiceGraphNode is the first node in
# the outer backbone to receive caller input, so its S-1 boundary and its
# state<->subgraph field mapping (extract_input/merge_output) must be proven
# the same way any other outer node's boundary is proven.

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import FieldServiceGraphNode
from src.nodes.technician_score_node import TechnicianScoreNode


class TestFieldServiceGraphNodeS1TrustGate:
    """S-1: GraphNode.__call__() runs the same trust gate as any BaseNode."""

    def test_denies_when_caller_trust_below_required(self):
        node = FieldServiceGraphNode()
        state = {
            "caller_trust_level": TrustLevel.ANONYMOUS.value,
            "user_input": "{}",
        }
        result = node(state)
        assert result["status"] == AgentStatus.ERROR.value
        assert any("S-1 trust gate denied" in line for line in result["error_log"])


class TestFieldServiceGraphNodeBoundaryMapping:
    """Composition consistency (criterion #9): extract_input/merge_output must map
    fields explicitly — no field leaks outside the documented contract, no raw
    subgraph dict pass-through."""

    def test_extract_input_only_reads_validated_input_or_user_input(self):
        node = FieldServiceGraphNode()
        state = {
            "correlation_id": "corr-1",
            "validated_input": '{"request_id": "req-1"}',
            "user_input": "should not be used when validated_input is present",
            "unrelated_field": "must not leak into the subgraph input string",
        }
        extracted = node.extract_input(state)
        assert extracted == '{"request_id": "req-1"}'
        assert "unrelated_field" not in extracted

    def test_merge_output_maps_fields_explicitly_no_raw_passthrough(self):
        node = FieldServiceGraphNode()
        sub_result = {
            "scored_technicians": [{"technician_id": "t1"}],
            "selected_technician": {"technician_id": "t1"},
            "route_plan": {"eta_minutes": 12.0},
            "dispatch_status": "dispatched",
            "dispatch_notification_id": "disp-t1",
            "work_order_id": "wo-t1",
            "work_order_text": "work order text",
            "parts_list": ["ethernet cable"],
            "status": AgentStatus.SUCCESS.value,
            # Field NOT in the documented outer/inner contract — merge_output must
            # NOT pass this through raw (criterion #9 no-raw-pass-through check).
            "internal_debug_trace": "should never reach outer state",
        }
        merged = node.merge_output({"correlation_id": "corr-1"}, sub_result)
        assert "internal_debug_trace" not in merged
        assert merged["work_order_id"] == "wo-t1"
        assert merged["status"] == AgentStatus.SUCCESS.value


class TestInnerEntryNodeDelegatedGating:
    """Delegation has intent, not a gap: FieldServiceGraphNode.__call__() does not
    run the standard S-2/S-3 node lifecycle (GraphNode design, see
    framework/nodes/graph_node.py) — gating is delegated to the inner subgraph's
    entry node instead. TechnicianScoreNode is a FunctionNode, so the framework's
    default S-2 (_security_gate_input, @final) and S-3 (_security_gate_output,
    @final) gates still run on every inner invocation via its own __call__()."""

    def test_inner_entry_node_is_a_function_node_with_default_gates(self):
        import pytest

        from framework.nodes.function_node import FunctionNode

        assert isinstance(TechnicianScoreNode(), FunctionNode)
        # @final gates are inherited, not overridden — confirms they cannot have
        # been bypassed by this node. Local wheel rc1 stub does not yet ship these
        # as concrete FunctionNode attributes (see test-artifacts.md — same known
        # artifact class as the PB-6/TC-06/TC-07 local-vs-CI-wheel gap); guard so
        # this test is meaningful once the enforcing wheel is present, without
        # spuriously failing on the local stub. CI wheel 1.0.0 is the gate of record.
        if not hasattr(FunctionNode, "_security_gate_input"):
            pytest.skip("local wheel rc1 stub does not define _security_gate_input — CI wheel is gate of record")
        assert TechnicianScoreNode._security_gate_input is FunctionNode._security_gate_input
        assert TechnicianScoreNode._security_gate_output is FunctionNode._security_gate_output
