# SVC-C2-016 — Unit Tests: TechnicianScoreNode (inner step 1)

import json

import src.nodes.technician_score_node as technician_score_node_module
from framework.schemas.agent_status import AgentStatus
from src.nodes.technician_score_node import TechnicianScoreNode

INNER_PAYLOAD = {
    "request_id": "req-1",
    "service_type": "network_repair",
    "priority": "high",
    "customer_location": {"lat": 35.68, "lng": 139.76},
    "required_skills": ["networking"],
    "technician_roster": [
        {
            "technician_id": "t1",
            "name": "Alice",
            "skills": ["networking"],
            "location": {"lat": 35.69, "lng": 139.70},
            "available": True,
        },
        {
            "technician_id": "t2",
            "name": "Bob",
            "skills": ["plumbing"],
            "location": {"lat": 40.0, "lng": 100.0},
            "available": False,
        },
    ],
}


class TestTechnicianScoreNode:
    def setup_method(self):
        self.node = TechnicianScoreNode()

    def test_success_path_ranks_best_technician_first(self):
        state = {"user_input": json.dumps(INNER_PAYLOAD), "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        scored = result["scored_technicians"]
        assert len(scored) == 2
        assert scored[0]["technician_id"] == "t1"  # matching skill + closer + available
        assert scored[0]["score"] >= scored[1]["score"]

    def test_empty_roster_is_error(self):
        payload = {**INNER_PAYLOAD, "technician_roster": []}
        state = {"user_input": json.dumps(payload), "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_invalid_inner_input_is_error(self):
        state = {"user_input": "", "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_emits_trace_event_on_success_and_error_paths(self, monkeypatch):
        """S-4 regression: every execute() path must emit at least one non-sensitive event."""
        calls = []

        def fake_emit(event_type, payload, state):
            calls.append((event_type, payload))

        monkeypatch.setattr(technician_score_node_module, "emit_trace_event", fake_emit)

        node = TechnicianScoreNode()
        node.execute({"user_input": "", "error_log": []})
        assert any(event == "technician_scoring_requested" for event, _ in calls)

        calls.clear()
        node.execute({"user_input": json.dumps(INNER_PAYLOAD), "error_log": []})
        events = [event for event, _ in calls]
        assert "technician_scoring_requested" in events
        assert "technicians_scored" in events
        for _, payload in calls:
            assert not any(key in payload for key in ("technician_roster", "required_skills", "customer_location"))
