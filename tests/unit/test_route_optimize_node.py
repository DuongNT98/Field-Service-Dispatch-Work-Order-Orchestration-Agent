# SVC-C2-016 — Unit Tests: RouteOptimizeNode (inner step 2)

import src.nodes.route_optimize_node as route_optimize_node_module
from framework.schemas.agent_status import AgentStatus
from src.nodes.route_optimize_node import RouteOptimizeNode


class TestRouteOptimizeNode:
    def setup_method(self):
        self.node = RouteOptimizeNode()

    def test_success_path(self):
        state = {
            "scored_technicians": [{"technician_id": "t1", "distance_km": 10.0, "score": 0.9}],
            "customer_location": {"lat": 35.68, "lng": 139.76},
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["selected_technician"]["technician_id"] == "t1"
        assert result["route_plan"]["eta_minutes"] is not None

    def test_no_scored_technicians_is_error(self):
        state = {"scored_technicians": [], "customer_location": {}, "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_emits_trace_event_on_success_and_error_paths(self, monkeypatch):
        """S-4 regression: every execute() path must emit at least one non-sensitive event."""
        calls = []

        def fake_emit(event_type, payload, state):
            calls.append((event_type, payload))

        monkeypatch.setattr(route_optimize_node_module, "emit_trace_event", fake_emit)

        node = RouteOptimizeNode()
        node.execute({"scored_technicians": [], "customer_location": {}, "error_log": []})
        assert any(event == "route_optimization_requested" for event, _ in calls)

        calls.clear()
        node.execute(
            {
                "scored_technicians": [{"technician_id": "t1", "distance_km": 10.0, "score": 0.9}],
                "customer_location": {"lat": 35.68, "lng": 139.76},
                "error_log": [],
            }
        )
        events = [event for event, _ in calls]
        assert "route_optimization_requested" in events
        assert "route_optimized" in events
        for _, payload in calls:
            assert not any(key in payload for key in ("distance_km", "score", "lat", "lng"))
