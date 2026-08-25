"""Unit tests for the agent-loop helpers and prompt/tool plumbing.

Run with:  python -m unittest discover -s tests
"""

import unittest
import asyncio

import worker.host_registry as host_registry  # type: ignore

from backend.agent.loop import (
    CORE_PROMPT,
    build_system_prompt,
    extract_goal,
    _missing_bin,
    truncate,
    _to_int,
    AgentLoop,
    _resolve_remote_path,
    _protected_write_message,
)
from backend.agent.llm import _sanitize_messages
from worker.sandbox import SandboxManager


class _FakeWSManager:
    async def broadcast_to_challenge(self, challenge_id, message):
        pass


class _FakeSandbox(SandboxManager):
    """Sync fake that records execute_command calls (no real SSH)."""

    def __init__(self):
        super().__init__()
        self.commands = []

    def execute_command(self, container_id, cmd):
        self.commands.append(cmd)
        return {"exit_code": 0, "output": "", "stderr": ""}


async def _noop(*args, **kwargs):
    return None


class TestHelpers(unittest.TestCase):
    def test_truncate_short_passthrough(self):
        self.assertEqual(truncate("short", 100), "short")

    def test_truncate_long_keeps_head_and_tail(self):
        text = "A" * 1000
        out = truncate(text, 100)
        self.assertIn("TRUNCATED", out)
        self.assertIn("A", out)

    def test_to_int_fallback(self):
        self.assertEqual(_to_int("12", 0), 12)
        self.assertEqual(_to_int(None, 0), 0)
        self.assertEqual(_to_int("garbage", 7), 7)


class TestSystemPrompt(unittest.TestCase):
    def test_forensics_category_injects_playbook(self):
        prompt = build_system_prompt("t", "d", "Forensics", challenge_id=16)
        self.assertIn("FORENSICS", prompt)
        self.assertIn("file", prompt)
        self.assertIn("binwalk", prompt)

    def test_unknown_category_has_core_only(self):
        prompt = build_system_prompt("t", "d", "Weird", challenge_id=16)
        self.assertIn("Challenge: t", prompt)
        self.assertNotIn("binwalk", prompt)


class TestSanitizeMessages(unittest.TestCase):
    def test_strips_reasoning_content(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "hi", "reasoning_content": "secret", "tool_calls": [{"id": "1"}]},
            {"role": "tool", "tool_call_id": "1", "content": "result", "extra": "x"},
        ]
        cleaned = _sanitize_messages(messages)
        self.assertNotIn("reasoning_content", cleaned[1])
        self.assertIn("tool_calls", cleaned[1])
        self.assertNotIn("extra", cleaned[2])


class TestCommandResultFormatting(unittest.TestCase):
    def _loop(self):
        return AgentLoop(1, _FakeWSManager(), "t", "d", "Forensics")

    def test_includes_exit_code_and_stderr(self):
        loop = self._loop()
        out = loop._format_command_result({"exit_code": 2, "output": "o", "stderr": "boom"})
        self.assertIn("exit code 2", out)
        self.assertIn("boom", out)

    def test_success_with_no_output(self):
        loop = self._loop()
        out = loop._format_command_result({"exit_code": 0, "output": "", "stderr": ""})
        self.assertEqual(out, "[No output]")


class TestGoalExtraction(unittest.TestCase):
    def test_extracts_flag_format(self):
        self.assertEqual(extract_goal("... The flag format is: firstname_lastname"), "firstname_lastname")

    def test_no_goal_when_absent(self):
        self.assertIsNone(extract_goal("just a description"))


class TestPromptWithGoal(unittest.TestCase):
    def test_prompt_includes_goal(self):
        goal = extract_goal("flag format is: firstname_lastname")
        prompt = build_system_prompt("t", "flag format is: firstname_lastname", "Forensics", goal, challenge_id=16)
        self.assertIn("firstname_lastname", prompt)
        self.assertIn("PROMPT GOAL", prompt)


class TestMissingBin(unittest.TestCase):
    def test_finds_missing_binary(self):
        self.assertEqual(_missing_bin("bash: line 1: binwalk: command not found"), "binwalk")

    def test_none_when_no_missing(self):
        self.assertIsNone(_missing_bin("hello world"))


class TestAssessNudge(unittest.TestCase):
    def _loop(self):
        return AgentLoop(1, _FakeWSManager(), "t", "d", "Forensics")

    def test_missing_tool_nudge(self):
        loop = self._loop()
        nudge = loop._assess_and_nudge(
            "binwalk -e x", {"exit_code": 127, "output": "", "stderr": "bash: line 1: binwalk: command not found"}
        )
        self.assertIsNotNone(nudge)
        assert nudge is not None
        self.assertIn("binwalk", nudge)

    def test_dead_end_mount_nudge(self):
        loop = self._loop()
        nudge = loop._assess_and_nudge(
            "mount -o loop x /mnt", {"exit_code": 32, "output": "", "stderr": "failed to set up loop device"}
        )
        self.assertIsNotNone(nudge)
        assert nudge is not None
        self.assertIn("7z", nudge)

    def test_repeated_command_nudge(self):
        loop = self._loop()
        loop._last_cmd = None
        loop._assess_and_nudge("ls /nope", {"exit_code": 2, "output": "", "stderr": "No such file"})
        loop._assess_and_nudge("ls /nope", {"exit_code": 2, "output": "", "stderr": "No such file"})
        nudge = loop._assess_and_nudge("ls /nope", {"exit_code": 2, "output": "", "stderr": "No such file"})
        self.assertIsNotNone(nudge)
        assert nudge is not None
        self.assertIn("STOP", nudge)

    def test_no_nudge_on_success(self):
        loop = self._loop()
        nudge = loop._assess_and_nudge("ls", {"exit_code": 0, "output": "ok", "stderr": ""})
        self.assertIsNone(nudge)

    def test_repeat_nudge_any_exit_code(self):
        """Repeat detection fires regardless of exit code (REQ-003)."""
        loop = self._loop()
        loop._last_cmd = None
        # Same command, exit code 0 every time — should still trigger the nudge.
        loop._assess_and_nudge("cat /workspace/1/work/file.txt", {"exit_code": 0, "output": "", "stderr": ""})
        loop._assess_and_nudge("cat /workspace/1/work/file.txt", {"exit_code": 0, "output": "", "stderr": ""})
        nudge = loop._assess_and_nudge("cat /workspace/1/work/file.txt", {"exit_code": 0, "output": "", "stderr": ""})
        self.assertIsNotNone(nudge)
        assert nudge is not None
        self.assertIn("STOP", nudge)

    def test_restore_on_missing(self):
        """A 'No such file or directory' error triggers restore guidance (REQ-003)."""
        loop = self._loop()
        loop._last_cmd = None
        nudge = loop._assess_and_nudge(
            "cat /workspace/1/work/missing.dat",
            {"exit_code": 1, "output": "", "stderr": "cat: /workspace/1/work/missing.dat: No such file or directory"}
        )
        self.assertIsNotNone(nudge)
        assert nudge is not None
        self.assertIn("cp", nudge)
        self.assertIn("originals", nudge)
        self.assertIn("work", nudge)


class TestPathContainment(unittest.TestCase):
    """Tests for _resolve_remote_path path containment (REQ-003)."""

    def test_read_allowed_within_challenge_root(self):
        """Read access is allowed under /workspace/{id}/."""
        resolved = _resolve_remote_path("/workspace/42/originals/evidence.img", 42, write=False)
        self.assertEqual(resolved, "/workspace/42/originals/evidence.img")

    def test_read_allowed_in_work_dir(self):
        """Read access is allowed under /workspace/{id}/work/."""
        resolved = _resolve_remote_path("/workspace/42/work/file.txt", 42, write=False)
        self.assertEqual(resolved, "/workspace/42/work/file.txt")

    def test_read_rejected_outside_challenge(self):
        """Read access outside /workspace/{id}/ is rejected."""
        resolved = _resolve_remote_path("/workspace/99/evidence.img", 42, write=False)
        self.assertIsNone(resolved)

    def test_read_rejected_at_root(self):
        """Read access at /workspace (no id) is rejected."""
        resolved = _resolve_remote_path("/workspace/evidence.img", 42, write=False)
        self.assertIsNone(resolved)

    def test_write_allowed_under_work_dir(self):
        """Write access is allowed under /workspace/{id}/work/."""
        resolved = _resolve_remote_path("/workspace/42/work/script.py", 42, write=True)
        self.assertEqual(resolved, "/workspace/42/work/script.py")

    def test_write_rejected_in_originals(self):
        """Write access to originals/ is rejected."""
        resolved = _resolve_remote_path("/workspace/42/originals/evidence.img", 42, write=True)
        self.assertIsNone(resolved)

    def test_write_rejected_outside_work(self):
        """Write access outside work/ is rejected."""
        resolved = _resolve_remote_path("/workspace/42/tools/analyze.py", 42, write=True)
        self.assertIsNone(resolved)

    def test_relative_path_anchored_to_work(self):
        """Relative paths are anchored to work/."""
        resolved = _resolve_remote_path("../originals/img.zip", 42, write=True)
        # normpath resolves ../ to a parent; should be outside work/
        self.assertIsNone(resolved)


class TestProtectedWriteMessage(unittest.TestCase):
    def test_message_contains_copy_hint(self):
        msg = _protected_write_message("/workspace/42/originals/img", 42)
        self.assertIn("cp", msg)
        self.assertIn("originals", msg)
        self.assertIn("work", msg)
        self.assertIn("protected", msg.lower())


class TestLayeredPrompt(unittest.TestCase):
    """Tests for the layered system prompt structure (REQ-003)."""

    def test_core_prompt_contains_workspace_contract(self):
        prompt = build_system_prompt("t", "d", "Forensics", challenge_id=16)
        self.assertIn("WORKSPACE CONTRACT", prompt)
        self.assertIn("originals", prompt)
        self.assertIn("work", prompt)

    def test_core_prompt_contains_loop_discipline(self):
        prompt = build_system_prompt("t", "d", "Forensics")
        self.assertIn("LOOP DISCIPLINE", prompt)
        self.assertIn("PLAN", prompt)

    def test_core_prompt_contains_role_scope(self):
        prompt = build_system_prompt("t", "d", "Forensics")
        self.assertIn("CTF-solving agent", prompt)
        self.assertIn("authorized", prompt)

    def test_layered_prompt_includes_file_info(self):
        file_info = "/workspace/42/work/evidence.img (1234 bytes) — type: gzip compressed"
        prompt = build_system_prompt("t", "d", "Forensics", "name", file_info, challenge_id=16)
        self.assertIn("Challenge files (staged in your workspace):", prompt)
        self.assertIn("evidence.img", prompt)
        self.assertIn("PROMPT GOAL", prompt)

    def test_forensics_category_includes_extraction_guidance(self):
        prompt = build_system_prompt("t", "d", "Forensics", challenge_id=16)
        self.assertIn("7z x", prompt)
        self.assertIn("binwalk -e", prompt)
        self.assertIn("mmls", prompt)
        self.assertIn("icat", prompt)

    def test_category_playbook_present_for_known_category(self):
        for cat in ["Forensics", "Cryptography", "Pwn", "Web", "Reverse Engineering", "OSINT", "Steganography", "Misc"]:
            prompt = build_system_prompt("t", "d", cat)
            # Should not raise and should contain something relevant
            self.assertIsInstance(prompt, str)
            self.assertGreater(len(prompt), 50)

    def test_regression_no_literal_id_in_core_prompt(self):
        """CORE_PROMPT must not contain any literal '{id}' template placeholders."""
        self.assertEqual(CORE_PROMPT.count('{id}'), 0)

    def test_regression_dynamic_workspace_contract_paths(self):
        """When challenge_id is provided, build_system_prompt must produce real paths and no '{id}'."""
        prompt = build_system_prompt("t", "d", "Forensics", challenge_id=16)
        # The generated prompt must not contain literal '{id}'
        self.assertNotIn('{id}', prompt)
        # It must contain the real workspace paths for challenge 16
        self.assertIn('/workspace/16/work', prompt)
        self.assertIn('/workspace/16/originals', prompt)
        # And the workspace contract block must be present
        self.assertIn("WORKSPACE CONTRACT", prompt)


class TestExecuteCommandCwd(unittest.TestCase):
    """REQ-004: execute_command runs inside the challenge work dir."""

    def test_commands_run_in_work_dir(self):
        fs = _FakeSandbox()
        loop = AgentLoop(42, _FakeWSManager(), "t", "d", "Forensics")
        loop.sandbox = fs
        loop._persist_event = _noop
        loop._sync_originals = _noop  # avoid host/SSH calls
        asyncio.run(loop._handle_tool_call("tc1", "execute_command", {"command": "tar -xvf ch39.gz"}))
        self.assertTrue(fs.commands)
        self.assertIn("cd /workspace/42/work &&", fs.commands[-1])
        self.assertTrue(fs.commands[-1].endswith("( tar -xvf ch39.gz )"))


class TestWriteFileEmptyContent(unittest.TestCase):
    """REQ-004: write_file with empty content is rejected and never hits the sandbox."""

    def test_empty_content_rejected(self):
        fs = _FakeSandbox()
        loop = AgentLoop(42, _FakeWSManager(), "t", "d", "Forensics")
        loop.sandbox = fs
        loop._persist_event = _noop
        loop._sync_originals = _noop
        msg = asyncio.run(
            loop._handle_tool_call("tc2", "write_file", {"path": "/workspace/42/work/foo.txt", "content": "   "})
        )
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("0-byte", msg)
        self.assertEqual(fs.commands, [])  # no sandbox call for a rejected write


class TestPromptDestructiveGuidance(unittest.TestCase):
    """REQ-004: the prompt warns about destructive decompression and real cwd paths."""

    def test_prompt_warns_about_destructive_decompress(self):
        prompt = build_system_prompt("t", "d", "Forensics", challenge_id=16)
        self.assertIn("gzip -d", prompt)          # warns against deleting the source
        self.assertIn("--run-as=root", prompt)     # binwalk extraction hint
        self.assertIn("/workspace/16/work", prompt)
        self.assertIn("/workspace/16/originals", prompt)


class TestModelRegistry(unittest.TestCase):
    """REQ-006: the model registry exposes providers + models and resolves defaults."""

    def test_default_model_is_configured(self):
        from backend.agent import llm
        self.assertIsInstance(llm.default_model(), str)
        self.assertTrue(llm.default_model())

    def test_model_list_shape(self):
        from backend.agent import llm
        rows = llm.model_list()
        self.assertTrue(rows)
        self.assertIn("id", rows[0])
        self.assertIn("display_name", rows[0])
        self.assertIn("provider", rows[0])
        self.assertIn("base_url", rows[0])

    def test_provider_for_model_resolves(self):
        from backend.agent import llm
        mid = llm.default_model()
        provider = llm._provider_for_model(mid)
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertTrue(provider["base_url"].startswith("http"))
        self.assertIn(mid, llm.known_model_ids())


class TestHostRegistry(unittest.TestCase):
    """Tests for the multi-host container registry + load balancer."""

    def setUp(self):
        self._orig_config = host_registry.HOSTS_CONFIG
        self._orig_health = host_registry._health_check_func
        self._orig_active = dict(host_registry._active_counts)
        self._orig_rr = host_registry._round_robin_index
        # Bypass real network calls during unit tests.
        host_registry._health_check_func = lambda host, port: True

    def tearDown(self):
        host_registry.HOSTS_CONFIG = self._orig_config
        host_registry._health_check_func = self._orig_health
        host_registry._active_counts.clear()
        host_registry._active_counts.update(self._orig_active)
        host_registry._round_robin_index = self._orig_rr

    def _set_hosts(self, hosts):
        host_registry.HOSTS_CONFIG = {"hosts": hosts}
        host_registry._active_counts.clear()
        host_registry._round_robin_index = 0

    def test_list_hosts_contains_argus_kali(self):
        hosts = host_registry.list_hosts()
        self.assertTrue(hosts)
        self.assertEqual(hosts[0]["name"], "argus-kali")

    def test_select_host_returns_default(self):
        host = host_registry.select_host()
        self.assertEqual(host["name"], "argus-kali")

    def test_select_host_skips_unhealthy(self):
        self._set_hosts([
            {"name": "bad", "host": "10.0.0.1", "port": 22, "healthy": False, "concurrency": 1, "max_challenges": 8},
            {"name": "good", "host": "10.0.0.2", "port": 22, "healthy": True, "concurrency": 1, "max_challenges": 8},
        ])
        host = host_registry.select_host()
        self.assertEqual(host["name"], "good")

    def test_select_host_round_robin(self):
        self._set_hosts([
            {"name": "a", "host": "10.0.0.1", "port": 22, "healthy": True, "concurrency": 1, "max_challenges": 8},
            {"name": "b", "host": "10.0.0.2", "port": 22, "healthy": True, "concurrency": 1, "max_challenges": 8},
        ])
        first = host_registry.select_host()
        second = host_registry.select_host()
        self.assertNotEqual(first["name"], second["name"])

    def test_select_host_falls_back_when_all_at_capacity(self):
        self._set_hosts([
            {"name": "a", "host": "10.0.0.1", "port": 22, "healthy": True, "concurrency": 1, "max_challenges": 1},
            {"name": "b", "host": "10.0.0.2", "port": 22, "healthy": True, "concurrency": 1, "max_challenges": 1},
        ])
        host = host_registry.select_host(active={"a": 1, "b": 1})
        # Fallback ignores capacity and returns the first healthy host.
        self.assertEqual(host["name"], "a")

    def test_acquire_release_count(self):
        host_registry._active_counts.clear()
        host_registry.acquire_host("a")
        host_registry.acquire_host("a")
        host_registry.release_host("a")
        self.assertEqual(host_registry.active_count("a"), 1)
        host_registry.release_host("a")
        self.assertEqual(host_registry.active_count("a"), 0)


if __name__ == "__main__":
    unittest.main()
