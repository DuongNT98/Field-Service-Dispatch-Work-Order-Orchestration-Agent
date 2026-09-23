# SVC-C2-016 — Integration test: full outer + inner Cat 2 pipeline

import json

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import Graph

VALID_REQUEST = {
    "request_id": "req-100",
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
            "skills": [],
            "location": {"lat": 40.0, "lng": 100.0},
            "available": False,
        },
    ],
}


class TestFieldServiceDispatchGraphIntegration:
    """No secrets are bound in this process, so WorkOrderNode's LLM resolution
    fails closed to its deterministic fallback (framework.secrets.base.NullProvider
    is the default outside a bound_secrets() context) — this suite exercises that
    path end to end. LLM-success / LLM-failure-degrade coverage for WorkOrderNode
    itself lives in tests/unit/test_work_order_node.py (constructor test-double)."""

    def test_compile_and_invoke_success(self):
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        ctx = InvocationContext(
            session_id="itest-1",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="itest",
        )
        result = agent.invoke(json.dumps(VALID_REQUEST), ctx=ctx)

        assert result.get("status") in ("success", "SUCCESS")
        node_history = result.get("node_history") or []
        assert len(node_history) >= 5

        # AgentBaseGraph.get_output() nests the node's formatted_output under "output".
        formatted = result.get("output") or {}
        assert formatted.get("dispatch_status") == "dispatched"
        assert formatted.get("work_order_text")
        assert formatted.get("completion_record", {}).get("technician_id") == "t1"

    def test_invoke_with_empty_roster_fails_gracefully(self):
        agent = Graph(config={"max_retry": 1})
        agent.compile()
        ctx = InvocationContext(
            session_id="itest-2",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="itest",
        )
        bad_request = {**VALID_REQUEST, "technician_roster": []}
        result = agent.invoke(json.dumps(bad_request), ctx=ctx)
        assert result.get("status") in ("error", "ERROR", "cancelled", "CANCELLED")
