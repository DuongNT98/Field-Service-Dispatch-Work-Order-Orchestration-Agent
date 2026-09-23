# SVC-C2-016 — Unit Tests: DispatchNode (inner step 3)

import src.nodes.dispatch_node as dispatch_node_module
from framework.schemas.agent_status import AgentStatus
from src.nodes.dispatch_node import DispatchNode


class TestDispatchNode:
    def setup_method(self):
        self.node = DispatchNode()

    def test_success_path(self):
        state = {
            "selected_technician": {"technician_id": "t1", "name": "Alice"},
            "route_plan": {"eta_minutes": 12.0},
            "correlation_id": "corr-1",
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["dispatch_status"] == "dispatched"
        assert "t1" in result["dispatch_notification_id"]

    def test_no_technician_is_error(self):
        state = {"selected_technician": {}, "route_plan": {}, "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_emits_trace_event_on_success_and_error_paths(self, monkeypatch):
        """S-4 regression: every execute() path must emit at least one non-sensitive event."""
        calls = []

        def fake_emit(event_type, payload, state):
            calls.append((event_type, payload))

        monkeypatch.setattr(dispatch_node_module, "emit_trace_event", fake_emit)

        node = DispatchNode()
        node.execute({"selected_technician": {}, "route_plan": {}, "error_log": []})
        assert any(event == "dispatch_requested" for event, _ in calls)

        calls.clear()
        node.execute(
            {
                "selected_technician": {"technician_id": "t1", "name": "Alice"},
                "route_plan": {"eta_minutes": 12.0},
                "correlation_id": "corr-1",
                "error_log": [],
            }
        )
        events = [event for event, _ in calls]
        assert "dispatch_requested" in events
        assert "technician_dispatched" in events
        for _, payload in calls:
            assert not any(key in payload for key in ("name",))
