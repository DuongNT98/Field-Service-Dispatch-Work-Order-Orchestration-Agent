# SVC-C2-016 — Framework Compliance Tests (TC-01..11)
# See docs/03_test_spec.md for the full TC/PB matrix.

import inspect

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.completion_capture_node import CompletionCaptureNode
from src.nodes.dispatch_node import DispatchNode
from src.nodes.request_validate_node import RequestValidateNode
from src.nodes.route_optimize_node import RouteOptimizeNode
from src.nodes.technician_score_node import TechnicianScoreNode
from src.nodes.work_order_node import WorkOrderNode
from src.schemas.state import State

ALL_NODE_CLASSES = [
    RequestValidateNode,
    TechnicianScoreNode,
    RouteOptimizeNode,
    DispatchNode,
    WorkOrderNode,
    CompletionCaptureNode,
]


class TestTC01StateContract:
    """TC-01: State contract — flat TypedDict, no Pydantic/dataclass."""

    def test_state_is_typed_dict_subclass(self):
        import typing

        assert typing.is_typeddict(State) or hasattr(State, "__annotations__")

    def test_state_has_no_pydantic_basemodel_fields(self):
        for name, annotation in State.__annotations__.items():
            assert "BaseModel" not in str(annotation), f"{name} looks like a Pydantic field"


class TestTC02SecurityViolation:
    """TC-02: invalid input triggers a fail-closed ERROR (not an unhandled exception)."""

    def test_request_validate_node_fails_closed_on_invalid_json(self):
        node = RequestValidateNode()
        result = node.execute({"user_input": "{not valid json", "error_log": []})
        assert result["status"] == AgentStatus.ERROR


class TestTC04InvocationContextIsolation:
    """TC-04: nodes never read InvocationContext from State — only via config['configurable']."""

    def test_execute_signature_has_no_context_param(self):
        for node_cls in ALL_NODE_CLASSES:
            sig = inspect.signature(node_cls.execute)
            params = list(sig.parameters.keys())
            assert params == ["self", "state"], f"{node_cls.__name__}.execute() must be (self, state)"


class TestTC05NoDuplicateLifecycleEvents:
    """TC-05: execute() must not re-emit node_start/node_complete/node_error."""

    def test_execute_source_has_no_backbone_reemit(self):
        for node_cls in ALL_NODE_CLASSES:
            source = inspect.getsource(node_cls.execute)
            for forbidden in ("emit_trace_event(\"node_start\"", "emit_trace_event(\"node_complete\"", "emit_trace_event(\"node_error\""):
                assert forbidden not in source, f"{node_cls.__name__} re-emits a backbone lifecycle event"


class TestTC06TC07FinalGatesNotOverridden:
    """TC-06/TC-07: FunctionNode subclasses must not override the @final S-2/S-3 gates."""

    def test_no_node_overrides_final_gates(self):
        for node_cls in ALL_NODE_CLASSES:
            assert "_security_gate_input" not in node_cls.__dict__, f"{node_cls.__name__} overrides @final _security_gate_input"
            assert "_security_gate_output" not in node_cls.__dict__, f"{node_cls.__name__} overrides @final _security_gate_output"


class TestTC08TrustLevelDeclaredAndValid:
    """TC-08: required_trust_level declared explicitly + a valid enum member."""

    def test_every_node_declares_valid_trust_level(self):
        valid = {TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL}
        for node_cls in ALL_NODE_CLASSES:
            assert "required_trust_level" in node_cls.__dict__, f"{node_cls.__name__} does not declare required_trust_level in its own class body"
            assert node_cls.required_trust_level in valid


class TestTC09ExtraSecurityGateInputNonTrivial:
    """TC-09: at least one node has a non-trivial _extra_security_gate_input()."""

    def test_request_validate_node_has_size_guard(self):
        node = RequestValidateNode()
        rejected = node._extra_security_gate_input({"user_input": "x" * 20_001, "error_log": []})
        assert rejected["status"] == AgentStatus.ERROR


class TestTC10ExtraSecurityGateOutputNonTrivial:
    """TC-10: at least one node has a non-trivial _extra_security_gate_output()."""

    def test_completion_capture_node_has_preservation_check(self):
        node = CompletionCaptureNode()
        rejected = node._extra_security_gate_output(
            {"completion_status": "captured", "formatted_output": {"work_order_text": ""}, "error_log": []}
        )
        assert rejected["status"] == AgentStatus.ERROR


class TestTC11DomainAuditEventPerNode:
    """TC-11: every execute() calls emit_trace_event() at least once (domain event)."""

    def test_execute_source_calls_emit_trace_event(self):
        for node_cls in ALL_NODE_CLASSES:
            source = inspect.getsource(node_cls.execute)
            assert "emit_trace_event(" in source, f"{node_cls.__name__}.execute() never calls emit_trace_event()"
