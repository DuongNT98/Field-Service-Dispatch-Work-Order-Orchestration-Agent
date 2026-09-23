# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `FieldServiceDispatchGraph` (outer) — `AgentBaseGraph` (L1 direct)
- **L1 Base**: AgentBaseGraph (outer backbone) + inner `BaseGraph` domain workflow
  wrapped by `GraphNode` at the `main` slot (Cat 2 pattern)
- **Three-Layer Separation**:
  - State: flat TypedDict composition (`src/schemas/state.py`, all agent-specific
    fields wrapped `NotRequired[...]`)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution; outer does NOT
    override `add_edges()`)

## Architecture Overview

Cat 2 — outer `AgentBaseGraph` backbone (fixed) + inner `BaseGraph` domain
workflow (custom topology), per the Cat 2 architecture pattern:

```
OUTER (AgentBaseGraph — src/graph/graph.py):
  initialize -> pre_process(RequestValidateNode) -> main(FieldServiceGraphNode) -> post_process(CompletionCaptureNode) -> finalize
                                                          |
                                                          v  extract_input() / merge_output()
INNER (BaseGraph — src/graph/domain_workflow_graph.py):
  START -> technician_score -> route_optimize -> dispatch -> work_order -> END
```

### Node Configuration

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process (RequestValidateNode, outer) | Parse+validate request JSON; size-guard S-2 | `user_input` | `request_id`, `service_type`, `priority`, `customer_location`, `required_skills`, `technician_roster`, `validated_input` | FunctionNode |
| main (FieldServiceGraphNode, outer) | Wrap inner Cat 2 subgraph | `validated_input` | scored/route/dispatch/work-order fields (merged) | GraphNode |
| inner: technician_score (TechnicianScoreNode) | Score roster by skill x proximity x availability (Tool: technician_scoring_service) | inner `user_input` (JSON) | `scored_technicians` | FunctionNode |
| inner: route_optimize (RouteOptimizeNode) | Route/ETA for top-scored technician (Tool: route_optimization_service) | `scored_technicians` | `selected_technician`, `route_plan` | FunctionNode |
| inner: dispatch (DispatchNode) | Dispatch notification; S-4 audit | `selected_technician`, `route_plan` | `dispatch_status`, `dispatch_notification_id` | FunctionNode |
| inner: work_order (WorkOrderNode) | LLM-essential: generate work-order text + parts list | `selected_technician`, `route_plan`, `required_skills` | `work_order_id`, `work_order_text`, `parts_list` | FunctionNode |
| post_process (CompletionCaptureNode, outer) | Capture completion record for invoicing/SLA; S-3 preservation check | merged fields from `main` | `completion_status`, `completion_record`, `formatted_output` | FunctionNode |
| finalize | response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Data Flow

```
START -> initialize -> pre_process -> main -> {route} -> post_process -> finalize -> END
                                          | (retry, max 3)
                                       pre_process
```

The inner subgraph does NOT receive the outer state directly — only the JSON
string set as `validated_input` by `RequestValidateNode`
(`FieldServiceGraphNode.extract_input()`), parsed by `TechnicianScoreNode`
(inner step 1) via `json.loads`. Config (the `llm` client) is forwarded to
the inner graph via `FieldServiceGraphNode._parent_config()`, not via state.

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `request_id` | `NotRequired[str]` | Service-request identifier | Yes (validated) |
| `service_type` | `NotRequired[str]` | Type of field-service job | No (default "general") |
| `priority` | `NotRequired[str]` | SLA priority tier | No (default "normal") |
| `customer_location` | `NotRequired[dict]` | `{lat, lng}` of the customer site | Yes |
| `required_skills` | `NotRequired[list[str]]` | Skills the job requires | Yes |
| `technician_roster` | `NotRequired[list[dict]]` | Candidate technicians (id/name/skills/location/available) | Yes |
| `scored_technicians` | `NotRequired[list[dict]]` | Roster ranked by score | Set by inner step 1 |
| `selected_technician` | `NotRequired[dict]` | Top-scored technician | Set by inner step 2 |
| `route_plan` | `NotRequired[dict]` | Route/ETA estimate | Set by inner step 2 |
| `dispatch_status` | `NotRequired[str]` | `"dispatched"` on success | Set by inner step 3 |
| `dispatch_notification_id` | `NotRequired[str]` | Dispatch notification reference | Set by inner step 3 |
| `work_order_id` | `NotRequired[str]` | Work-order identifier | Set by inner step 4 |
| `work_order_text` | `NotRequired[str]` | LLM-generated work-order narrative | Set by inner step 4 |
| `parts_list` | `NotRequired[list[str]]` | Inferred parts list | Set by inner step 4 |
| `completion_status` | `NotRequired[str]` | `"captured"` / `"not_dispatched"` | Set by post_process |
| `completion_record` | `NotRequired[dict]` | Completion data for invoicing/SLA reporting | Set by post_process |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, caller_trust_level)
- [ ] ConnectionPolicy (retry/timeout strategy) — default `max_retry: 3` in `config/agent.yaml`
- [ ] SecurityViolationError
- [x] S-2: `_extra_security_gate_input()` — `RequestValidateNode` guards raw
      payload size (domain input-size guard) before parsing
- [x] S-3: `_extra_security_gate_output()` — `CompletionCaptureNode` runs a
      **preservation-variant** check: `formatted_output` must retain
      `work_order_text` whenever `completion_status == "captured"`
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside
      every `execute()` (`field_service_request_received`,
      `technicians_scored`, `route_optimized`, `technician_dispatched`,
      `work_order_generated`, `completion_captured` / `completion_capture_skipped`,
      plus the `GraphNode` wrapper's `field_service_workflow_dispatched` /
      `field_service_workflow_completed` inside `extract_input()`/`merge_output()`)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass (all 6 domain nodes here) → framework `@final` gate
>   always runs automatically; extended via `_extra_security_gate_input()` /
>   `_extra_security_gate_output()` only
> - `GraphNode` (`FieldServiceGraphNode`) → deliberate no-op passthrough for
>   the standard S-1..S-4 node lifecycle (it delegates gating to the inner
>   subgraph's own nodes); S-4 audit is instead emitted from
>   `extract_input()`/`merge_output()`, which run inside `GraphNode.execute()`

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — outer `main` slot wraps the inner
  `FieldServiceWorkflowGraph` (`BaseGraph`, custom 4-node topology)
- **Composition target**: `src/graph/domain_workflow_graph.py::FieldServiceWorkflowGraph`
- **Error propagation strategy**: `propagate` (fail fast — inner errors surface
  as `SubgraphError`; no graceful-degradation requirement for this pipeline)

## Node-vs-Tool / LLM split

- **LLM-essential node**: `WorkOrderNode` (generates the work-order text /
  parts narrative — the one step where an LLM adds value beyond deterministic
  logic). Wired to Azure OpenAI (`shared.services.llm.azure_openai_client.AzureOpenAIClient`):
  the client is built fresh per invocation inside `execute()` from three
  declared secrets (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`,
  `AZURE_OPENAI_DEPLOYMENT` — `config/agent.yaml requires.secrets`), never
  cached on the node instance. Any failure (missing secret, API error,
  malformed response) degrades to the pre-existing deterministic narrative
  below — this node never raises and never sets `status=error` for an LLM
  problem. See `docs/07_operation_guide.md` for the secret provisioning
  requirement and the bare-endpoint format.
- **Deterministic nodes (Tool-backed)**: `RequestValidateNode`,
  `TechnicianScoreNode` + `RouteOptimizeNode` (wrap
  `src/services/technician_scoring_service.py` and
  `src/services/route_optimization_service.py` — pure functions, no State, no
  side effects: the Tool half of the Agent-vs-Tool split), `DispatchNode`,
  `CompletionCaptureNode`.

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | AgentBaseGraph | Fixed multi-step pipeline (Cat 2 job-to-be-done), not a self-directed reasoning loop |
| Composition pattern | Flat 3-slot (Cat 1 style) | GraphNode + inner BaseGraph | GraphNode + inner BaseGraph | Cat 2 requires outer/inner split (`gate-composition`); 4 inner business steps live in the domain workflow subgraph |
| Scoring/routing implementation | Node-embedded logic | `src/services/` Tool wrappers | `src/services/` Tool wrappers | Keeps deterministic optimization logic reusable/testable and honors the Agent-vs-Tool boundary (§2 of the proposal) |
