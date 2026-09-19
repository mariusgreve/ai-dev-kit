import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "cli"))
from context_compiler import compile_context, save_task


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aidev context ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.write("src/ResetService.java", "class ResetService { /* password reset token */ }")
        self.write("src/Unrelated.java", "class Invoice { /* bookkeeping */ }")
        self.write("AGENTS.md", "Project instructions")
        self.write("src/AGENTS.md", "Service instructions")
        self.write("elsewhere/AGENTS.md", "Unrelated instructions")
        self.write("architecture/overview.md", "Project architecture")
        self.write("architecture/auth.md", "Password reset uses events")

    def write(self, name, content):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def compile(self, description="Implement password reset", spec=None, **kwargs):
        return compile_context(self.project, REPO, description, spec,
                               {"java": ["pom.xml"], "spring": ["pom.xml"]}, **kwargs)

    def config(self, value):
        self.write(".ai/config.json", json.dumps(value))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(REPO / "aidev"), *args,
                               "--project", str(self.project)], text=True, capture_output=True)

    def paths(self, context, kind):
        return [item["path"] for item in context["selected"][kind]]

    def test_selection_is_relevant_deterministic_and_explained(self):
        context = self.compile()
        self.assertEqual(context, self.compile())
        self.assertIn("src/ResetService.java", self.paths(context, "files"))
        self.assertNotIn("src/Unrelated.java", self.paths(context, "files"))
        self.assertEqual(["AGENTS.md", "src/AGENTS.md"], self.paths(context, "instructions"))
        self.assertIn("architecture/auth.md", self.paths(context, "architecture"))
        self.assertIn("skills/spring/SKILL.md", self.paths(context, "skills"))
        self.assertTrue(all(item["reasons"] for items in context["selected"].values() for item in items))
        self.assertFalse((self.project / ".ai").exists())

    def test_local_overrides_and_custom_rules_work_for_arbitrary_stacks(self):
        self.write(".ai/skills/rust/SKILL.md", "Local rust conventions")
        self.write(".ai/principles/testing.md", "Project test conventions")
        self.write(".ai/playbooks/migrate.md", "Project migration workflow")
        self.config({"context": {"rules": [{"terms": ["password"],
                     "files": ["src/Unrelated.java"], "skills": ["rust"],
                     "architecture": ["architecture/overview.md"], "playbook": "migrate"}]}})
        context = self.compile()
        self.assertEqual(context["playbook"], "migrate")
        self.assertIn("src/Unrelated.java", self.paths(context, "files"))
        self.assertIn(".ai/skills/rust/SKILL.md", self.paths(context, "skills"))
        testing = next(item for item in context["selected"]["principles"] if "testing" in item["path"])
        self.assertEqual(testing["content"], "Project test conventions")
        self.assertEqual(testing["source"], "project")

    def test_custom_skill_description_is_selectable(self):
        self.write(".ai/skills/messaging/SKILL.md", "---\nname: messaging\ndescription: Handle queue retries and deadletters.\n---")
        self.assertIn(".ai/skills/messaging/SKILL.md", self.paths(self.compile("Queue retries"), "skills"))

    def test_sdd_preserves_spec_ids_and_line_references_in_handoff(self):
        spec = "# Reset\n\n- REQ-1: Reset token expires\n- [ ] Send password email\n"
        self.write("specs/reset.md", spec)
        context = self.compile("", "specs/reset.md")
        self.assertEqual(context["mode"], "sdd")
        self.assertEqual(context["workflow"], "rpi")
        self.assertEqual(context["spec"]["content"], spec)
        self.assertEqual([r["id"] for r in context["spec"]["requirements"]], ["REQ-1", "SPEC-L4"])
        directory = save_task(context, self.project)
        self.assertIn("REQ-1: pending", (directory / "plan.md").read_text())
        self.assertIn("Research", (directory / "task.md").read_text())
        self.assertIn("Status: pending", (directory / "implementation.md").read_text())
        self.assertNotEqual(directory, save_task(context, self.project))

    def test_inventory_respects_git_ignores_binaries_and_external_symlinks(self):
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.write(".gitignore", "ignored.txt\n")
        self.write("ignored.txt", "password reset")
        self.write("node_modules/example.js", "password reset")
        self.write(".env", "PASSWORD=reset")
        (self.project / "binary.dat").write_bytes(b"password\0reset")
        (self.project / "outside.txt").symlink_to(REPO / "README.md")
        context = self.compile()
        names = {item["path"] for item in context["project_model"]["files"]}
        self.assertIn("src/ResetService.java", names)
        self.assertFalse(names & {"ignored.txt", "node_modules/example.js", ".env", "binary.dat", "outside.txt"})

    def test_budget_is_bounded_and_truncation_explicit(self):
        self.config({"context": {"max_chars": 50, "max_files": 1}})
        context = self.compile()
        items = [item for group in context["selected"].values() for item in group]
        self.assertLessEqual(sum(len(item["content"]) for item in items), 50)
        self.assertLessEqual(len(context["selected"]["files"]), 1)
        self.assertTrue(any(item["truncated"] for item in items))
        self.assertTrue(context["warnings"])

    def test_changes_refresh_model_without_reusing_stale_context(self):
        first = self.compile()
        save_task(first, self.project)
        self.write("src/ResetService.java", "class SomethingElse {}")
        second = self.compile()
        self.assertNotEqual(first["project_model"], second["project_model"])
        self.assertFalse(any(".ai/tasks/" in item["path"] for item in second["project_model"]["files"]))

    def test_playbook_intent_and_explicit_override(self):
        self.assertEqual(self.compile("Fix password bug")["playbook"], "fix-bug")
        self.assertEqual(self.compile("Review password reset")["playbook"], "review-change")
        self.assertEqual(self.compile(playbook_override="fix-bug")["playbook"], "fix-bug")
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.compile(playbook_override="missing")

    def test_invalid_config_and_missing_or_outside_spec_fail_clearly(self):
        for config in ([], {"context": []}, {"context": {"rules": [1]}},
                       {"context": {"max_files": True}}, {"stacks": "java"},
                       {"context": {"rules": [{"terms": ["password"], "files": ["../*"]}]}}):
            with self.subTest(config=config):
                self.config(config)
                with self.assertRaises(ValueError):
                    self.compile()
        self.config({})
        for spec in ("missing.md", "../outside.md"):
            with self.assertRaises(ValueError):
                self.compile(spec=spec)
        with self.assertRaises(ValueError):
            self.compile("")

    def test_symlinked_output_directory_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as external:
            (self.project / ".ai").mkdir()
            (self.project / ".ai/tasks").symlink_to(external)
            with self.assertRaises(ValueError):
                save_task(self.compile(), self.project)
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_inspect_and_explain_are_read_only_with_same_json(self):
        before = sorted(str(path) for path in self.project.rglob("*"))
        inspected = self.cli("inspect", "password reset", "--json")
        explained = self.cli("explain", "password reset", "--json")
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(inspected.stdout, explained.stdout)
        self.assertEqual(before, sorted(str(path) for path in self.project.rglob("*")))
        self.assertTrue(json.loads(inspected.stdout)["selected"]["files"])

    def test_task_can_launch_generic_agent_in_project_with_stdin_and_exit_status(self):
        agent = self.write("fake agent.py", "import pathlib, sys\npathlib.Path('received.txt').write_text(sys.stdin.read())\nsys.exit(7)\n")
        result = subprocess.run([sys.executable, str(REPO / "aidev"), "task", "password reset",
                                 "--project", str(self.project), "--agent", sys.executable, str(agent)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("RPI handoff", (self.project / "received.txt").read_text())
        self.assertEqual(len(list((self.project / ".ai/tasks").glob("*/context.json"))), 1)

    def test_conflicting_rules_and_disabled_playbooks_require_explicit_resolution(self):
        self.config({"context": {"rules": [
            {"terms": ["password"], "playbook": "fix-bug"},
            {"terms": ["reset"], "playbook": "implement-feature"}]}})
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.compile()
        self.assertEqual(self.compile(playbook_override="review-change")["playbook"], "review-change")
        self.config({"playbooks": ["fix-bug"]})
        with self.assertRaisesRegex(ValueError, "not enabled"):
            self.compile()

    def test_rule_file_limit_and_verification_command(self):
        self.config({"verification": "python3 -m unittest", "context": {"max_files": 1,
                     "rules": [{"terms": ["password"], "files": ["src/*.java"]}]}})
        with self.assertRaisesRegex(ValueError, "exceed"):
            self.compile()
        self.config({"verification": "python3 -m unittest"})
        self.assertEqual(self.compile()["verification"], "python3 -m unittest")

    def test_cli_invalid_input_is_an_error_without_traceback(self):
        for args in (("task",), ("inspect", "--spec", "missing.md"),
                     ("explain", "password", "--playbook", "missing")):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
