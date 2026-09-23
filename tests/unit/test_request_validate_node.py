# SVC-C2-016 — Unit Tests: RequestValidateNode (outer pre_process)

import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.request_validate_node import RequestValidateNode

VALID_PAYLOAD = {
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
        }
    ],
}


class TestRequestValidateNode:
    def setup_method(self):
        self.node = RequestValidateNode()

    def test_success_path(self):
        state = {"user_input": json.dumps(VALID_PAYLOAD), "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["request_id"] == "req-1"
        assert json.loads(result["validated_input"])["technician_roster"]

    def test_missing_roster_is_error(self):
        payload = {**VALID_PAYLOAD, "technician_roster": []}
        state = {"user_input": json.dumps(payload), "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR
        assert result["error_log"]

    def test_invalid_json_is_error(self):
        state = {"user_input": "not json", "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_extra_security_gate_input_rejects_oversized_payload(self):
        """TC-09: _extra_security_gate_input() must be non-trivial and non-raising."""
        oversized_state = {"user_input": "x" * 20_001, "error_log": []}
        result = self.node._extra_security_gate_input(oversized_state)
        assert isinstance(result, dict)
        assert result["status"] == AgentStatus.ERROR

    def test_extra_security_gate_input_passthrough_on_valid_size(self):
        state = {"user_input": json.dumps(VALID_PAYLOAD), "error_log": []}
        result = self.node._extra_security_gate_input(state)
        assert result == state
