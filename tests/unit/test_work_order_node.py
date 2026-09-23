# SVC-C2-016 — Unit Tests: WorkOrderNode (inner step 4, LLM-essential)

import src.nodes.work_order_node as work_order_node_module
from framework.schemas.agent_status import AgentStatus
from src.nodes.work_order_node import WorkOrderNode


class FakeLLM:
    """Matches the real BaseLLM contract (shared/services/llm/base_llm.py):
    complete(messages: list) -> dict{content, tool_calls, model, usage}."""

    def complete(self, messages: list) -> dict:
        prompt = messages[0]["content"] if messages else ""
        return {
            "content": f"WORK ORDER (mock LLM): {prompt[:20]}...",
            "tool_calls": [],
            "model": "fake-model",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "model": "fake-model"},
        }


class TestWorkOrderNode:
    def test_success_path_with_llm(self):
        node = WorkOrderNode(llm=FakeLLM())
        state = {
            "selected_technician": {"technician_id": "t1", "name": "Alice"},
            "route_plan": {"route_summary": "10km, ETA 20min"},
            "required_skills": ["networking"],
            "service_type": "network_repair",
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["work_order_text"].startswith("WORK ORDER (mock LLM)")
        assert isinstance(result["work_order_text"], str)
        assert isinstance(result["parts_list"], list)

    def test_success_path_without_llm_fallback(self):
        node = WorkOrderNode(llm=None)
        state = {
            "selected_technician": {"technician_id": "t1", "name": "Alice"},
            "route_plan": {},
            "required_skills": ["networking"],
            "service_type": "network_repair",
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert "Alice" in result["work_order_text"]
        assert "ethernet cable" in result["parts_list"]

    def test_no_technician_is_error(self):
        node = WorkOrderNode()
        state = {"selected_technician": {}, "route_plan": {}, "required_skills": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_default_constructor_no_args(self):
        """PB-6 discovers this node under src/nodes/ and instantiates it with no args."""
        node = WorkOrderNode()
        assert node._llm is None

    def test_llm_raising_falls_back_to_heuristic(self):
        """Simulated API error — never raises, never status=error."""

        class RaisingLLM:
            def complete(self, messages: list) -> dict:
                raise RuntimeError("simulated Azure OpenAI API error")

        node = WorkOrderNode(llm=RaisingLLM())
        state = {
            "selected_technician": {"technician_id": "t1", "name": "Alice"},
            "route_plan": {},
            "required_skills": ["networking"],
            "service_type": "network_repair",
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert "Alice" in result["work_order_text"]
        assert "ethernet cable" in result["parts_list"]

    def test_llm_malformed_response_falls_back_to_heuristic(self):
        """Wrong-shape / empty-content response — treated as no usable LLM output."""

        class MalformedLLM:
            def complete(self, messages: list) -> dict:
                return {"tool_calls": [], "model": "fake-model"}  # no "content" key

        node = WorkOrderNode(llm=MalformedLLM())
        state = {
            "selected_technician": {"technician_id": "t1", "name": "Alice"},
            "route_plan": {},
            "required_skills": ["networking"],
            "service_type": "network_repair",
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert "Alice" in result["work_order_text"]

    def test_no_secret_bound_falls_back_to_heuristic(self):
        """Production shape: no constructor llm injected, no secret bound anywhere
        (the real state of any env without AZURE_OPENAI_* configured) —
        _resolve_llm must degrade silently, never raise."""
        node = WorkOrderNode()  # no llm= — production wiring never passes one
        state = {
            "selected_technician": {"technician_id": "t1", "name": "Alice"},
            "route_plan": {},
            "required_skills": ["networking"],
            "service_type": "network_repair",
            "error_log": [],
            # Deliberately no correlation_id/session_id/thread_id/trace_id —
            # InvocationContext.from_state() indexes these; a KeyError here
            # must be swallowed by _resolve_llm, not propagate.
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert "Alice" in result["work_order_text"]

    def test_emits_trace_event_on_success_and_error_paths(self, monkeypatch):
        """S-4 regression: every execute() path must emit at least one non-sensitive event."""
        calls = []

        def fake_emit(event_type, payload, state):
            calls.append((event_type, payload))

        monkeypatch.setattr(work_order_node_module, "emit_trace_event", fake_emit)

        node = WorkOrderNode()
        node.execute({"selected_technician": {}, "route_plan": {}, "required_skills": [], "error_log": []})
        assert any(event == "work_order_requested" for event, _ in calls)

        calls.clear()
        node.execute(
            {
                "selected_technician": {"technician_id": "t1", "name": "Alice"},
                "route_plan": {},
                "required_skills": ["networking"],
                "service_type": "network_repair",
                "error_log": [],
            }
        )
        events = [event for event, _ in calls]
        assert "work_order_requested" in events
        assert "work_order_generated" in events
        for _, payload in calls:
            assert not any(key in payload for key in ("name", "route_plan"))
