# SVC-C2-016 — Unit Tests: CompletionCaptureNode (outer post_process)

from framework.schemas.agent_status import AgentStatus
from src.nodes.completion_capture_node import CompletionCaptureNode


class TestCompletionCaptureNode:
    def setup_method(self):
        self.node = CompletionCaptureNode()

    def test_success_path_captures_completion(self):
        state = {
            "request_id": "req-1",
            "work_order_id": "wo-1",
            "work_order_text": "Do the thing",
            "dispatch_status": "dispatched",
            "dispatch_notification_id": "disp-1",
            "selected_technician": {"technician_id": "t1"},
            "route_plan": {"eta_minutes": 12.0},
            "parts_list": ["ethernet cable"],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["completion_status"] == "captured"
        assert result["completion_record"]["work_order_id"] == "wo-1"
        assert result["formatted_output"]["work_order_text"] == "Do the thing"

    def test_not_dispatched_path(self):
        state = {"error_log": []}
        result = self.node.execute(state)
        assert result["completion_status"] == "not_dispatched"

    def test_extra_security_gate_output_rejects_missing_work_order_text(self):
        """TC-10: S-3 preservation-variant check — non-raising, always returns dict."""
        state = {
            "completion_status": "captured",
            "formatted_output": {"work_order_id": "wo-1", "work_order_text": ""},
            "error_log": [],
        }
        result = self.node._extra_security_gate_output(state)
        assert isinstance(result, dict)
        assert result["status"] == AgentStatus.ERROR

    def test_extra_security_gate_output_passthrough_when_preserved(self):
        state = {
            "completion_status": "captured",
            "formatted_output": {"work_order_id": "wo-1", "work_order_text": "Do the thing"},
            "error_log": [],
        }
        result = self.node._extra_security_gate_output(state)
        assert result == state
