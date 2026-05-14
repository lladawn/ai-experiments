from mac_agent_runtime.__main__ import build_harness
from mac_agent_runtime.context import ContextPacket, ContextSection


packet = ContextPacket(
    task="Describe the context isolation strategy.",
    system_rules=("Use only isolated evidence.",),
    evidence=(
        ContextSection("public brief", "Subagents receive selected evidence only."),
        ContextSection("hidden parent note", "This must not leak.", visibility="hidden"),
    ),
    allowed_tools=("echo_context",),
)

result = build_harness().delegate(
    parent_packet=packet,
    subtask="Explain what context you can see.",
    allowed_tools=(),
    evidence_names={"public brief"},
)

print(result.answer)
