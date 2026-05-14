import unittest

from mac_agent_runtime.__main__ import build_harness
from mac_agent_runtime.approval import ApprovalQueue
from mac_agent_runtime.context import ContextPacket, ContextSection
from mac_agent_runtime.laptop_tools import register_laptop_tools
from mac_agent_runtime.model import ModelResponse, StubModel
from mac_agent_runtime.multi_agent import AgentSpec, MultiAgentHarness
from mac_agent_runtime.overlay_state import OverlayState
from mac_agent_runtime.tools import Tool, ToolRegistry
from tempfile import TemporaryDirectory
from pathlib import Path


class HarnessTests(unittest.TestCase):
    def test_harness_runs_allowed_tool(self) -> None:
        packet = ContextPacket(task="Use context carefully.", allowed_tools=("echo_context",))
        result = build_harness().run(packet, required_terms=("context",))

        self.assertTrue(result.verification.passed)
        self.assertEqual(result.tool_outputs[0].name, "tool:echo_context")

    def test_tool_permission_blocks_unallowed_tool(self) -> None:
        tools = ToolRegistry()
        tools.register(Tool("echo_context", "Echo", lambda args: "ok"))

        with self.assertRaises(PermissionError):
            tools.run("echo_context", {}, allowed_tools=())

    def test_subagent_context_isolation_removes_hidden_and_scratchpad(self) -> None:
        packet = ContextPacket(
            task="Parent task",
            evidence=(
                ContextSection("allowed", "visible"),
                ContextSection("secret", "hidden", visibility="hidden"),
            ),
            scratchpad=(ContextSection("parent thoughts", "do not share"),),
        )

        isolated = packet.isolate_for_subagent(
            subtask="Child task",
            allowed_tools=(),
            evidence_names={"allowed", "secret"},
        )

        rendered = isolated.render_for_model()
        self.assertIn("visible", rendered)
        self.assertNotIn("hidden", rendered)
        self.assertNotIn("do not share", rendered)

    def test_enforcement_blocks_blocked_terms(self) -> None:
        class BadModel(StubModel):
            def complete(self, prompt: str) -> ModelResponse:
                return ModelResponse(answer="This contains a forbidden marker.")

        tools = ToolRegistry()
        harness = build_harness()
        harness.model = BadModel()
        harness.tools = tools

        with self.assertRaisesRegex(ValueError, "blocked term"):
            harness.run(ContextPacket(task="test"), blocked_terms=("forbidden",))

    def test_multi_agent_runs_workers_then_synthesizes(self) -> None:
        parent_packet = ContextPacket(
            task="Parent task",
            evidence=(ContextSection("brief", "Build carefully."),),
        )
        result = MultiAgentHarness(build_harness()).run(
            parent_packet=parent_packet,
            workers=(
                AgentSpec(name="planner", task="Plan the work.", evidence_names={"brief"}),
                AgentSpec(name="reviewer", task="Review risks.", evidence_names={"brief"}),
            ),
            synthesizer_task="Synthesize worker outputs.",
        )

        self.assertEqual(set(result.worker_results), {"planner", "reviewer"})
        self.assertTrue(result.final_result.verification.passed)

    def test_laptop_mutations_are_proposals(self) -> None:
        with TemporaryDirectory() as directory:
            queue = ApprovalQueue(Path(directory) / "pending.jsonl")
            tools = ToolRegistry()
            register_laptop_tools(tools, queue)

            output = tools.run(
                "propose_laptop_action",
                {
                    "kind": "create",
                    "summary": "Create a bookmark folder",
                    "command": "Create folder Jobs explored",
                    "risk": "Changes browser bookmarks",
                },
                allowed_tools=("propose_laptop_action",),
            )

            self.assertIn("Proposed action", output)
            self.assertEqual(len(queue.list_pending()), 1)

    def test_open_app_rejects_paths(self) -> None:
        with TemporaryDirectory() as directory:
            queue = ApprovalQueue(Path(directory) / "pending.jsonl")
            tools = ToolRegistry()
            register_laptop_tools(tools, queue)

            output = tools.run(
                "open_app",
                {"app_name": "/Applications/Notion.app"},
                allowed_tools=("open_app",),
            )

            self.assertIn("plain application name", output)

    def test_overlay_state_tracks_runs_and_agents(self) -> None:
        with TemporaryDirectory() as directory:
            state = OverlayState(Path(directory) / "state.json")
            run_id = state.start_run("Open Notion")
            state.set_agent(run_id, "operator", "Open the app", "running")
            state.set_final(run_id, "Opened Notion")

            snapshot = state.snapshot()
            run = snapshot["runs"][0]
            self.assertEqual(run["task"], "Open Notion")
            self.assertEqual(run["status"], "done")
            self.assertEqual(run["agents"][0]["status"], "running")


if __name__ == "__main__":
    unittest.main()
