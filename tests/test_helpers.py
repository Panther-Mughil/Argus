"""Unit tests for the agent-loop helpers and prompt/tool plumbing.

Run with:  python -m unittest discover -s tests
"""

import unittest

from backend.agent.loop import (
    build_system_prompt,
    extract_goal,
    _missing_bin,
    truncate,
    _to_int,
    AgentLoop,
)
from backend.agent.llm import _sanitize_messages


class _FakeWSManager:
    async def broadcast_to_challenge(self, challenge_id, message):
        pass


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
        prompt = build_system_prompt("t", "d", "Forensics")
        self.assertIn("FORENSICS", prompt)
        self.assertIn("file", prompt)
        self.assertIn("binwalk", prompt)

    def test_unknown_category_has_core_only(self):
        prompt = build_system_prompt("t", "d", "Weird")
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
        prompt = build_system_prompt("t", "flag format is: firstname_lastname", "Forensics", goal)
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


if __name__ == "__main__":
    unittest.main()
