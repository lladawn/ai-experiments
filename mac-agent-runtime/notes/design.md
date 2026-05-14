# Harness Design Notes

## Runtime Surfaces

- Context: structured packet with task, rules, constraints, evidence, scratchpad,
  tool allowlist, and metadata.
- Tools: registered capabilities. A context packet must explicitly allow a tool
  before the harness can invoke it.
- Verification: checks the produced answer against task-specific expectations.
- Enforcement: validates context before a model call and validates output before
  returning it.
- Isolation: delegated subagents receive a new packet with selected evidence and
  no inherited scratchpad.
- Approval: laptop-changing actions are represented as pending proposals before
  any executor is allowed to mutate state.

## Laptop Operator Safety

- Read tools are available to agents when a task requires local inspection.
- Sensitive paths such as SSH keys, keychains, cloud credentials, and obvious
  password/secret folders are denied by local policy.
- Write tools are not part of the default operator profile.
- App-control and bookmark-editing steps must be recorded with
  `propose_laptop_action` and reviewed by the user before a separate executor
  runs them.

## Near-Term Questions

- Should verification be deterministic, model-based, or layered?
- Should tools advertise schemas, side effects, and required verification?
- Should context isolation happen by whitelist only, or should there be named
  isolation profiles?
- How much of the run trace should be visible to downstream agents?

## Candidate Context Packet Fields

```text
task
system_rules
developer_constraints
user_preferences
evidence
memory
scratchpad
tool_allowlist
verification_contract
output_contract
metadata
```
