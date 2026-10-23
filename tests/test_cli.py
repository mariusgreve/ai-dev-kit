"""Exercise entry points and command routing across module boundaries."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class CliTest(unittest.TestCase):
    def run_cli(self, entry, *args, cwd):
        return subprocess.run([sys.executable, str(entry), *args], cwd=cwd,
                              text=True, capture_output=True)

    def test_launchers_work_outside_checkout_and_match_module_entrypoint(self):
        expected = subprocess.run([sys.executable, "-m", "cli.aidev", "list"],
                                  cwd=REPO, text=True, capture_output=True)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertIn("Stacks: java, spring, postgres, react, typescript", expected.stdout)
        self.assertIn("Task skills: bootstrap-from-reference, git-commit", expected.stdout)
        self.assertNotIn("git-commit-message", expected.stdout)
        with tempfile.TemporaryDirectory() as directory:
            for entry in (REPO / "aidev", REPO / "cli/aidev.py"):
                with self.subTest(entry=entry):
                    result = self.run_cli(entry, "list", cwd=directory)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected.stdout)
                    help_result = self.run_cli(entry, "--help", cwd=directory)
                    self.assertEqual(help_result.returncode, 0, help_result.stderr)
                    self.assertIn("install-skills", help_result.stdout)
                    self.assertNotIn("explain", help_result.stdout)


    def test_assess_existing_project_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "AGENTS.md").write_text("Local rules\\n")
            (project / "README.md").write_text("Project docs\\n")
            (project / "Jenkinsfile").write_text("pipeline {}\\n")
            (project / "pom.xml").write_text("<project/>\\n")
            before = sorted(str(p.relative_to(project)) for p in project.rglob("*"))
            result = self.run_cli(REPO / "aidev", "init", str(project),
                                  "--assess", cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("AGENTS.md already exists", result.stdout)
            self.assertIn("Jenkinsfile", result.stdout)
            self.assertIn("Review existing CI commands", result.stdout)
            self.assertIn("java", result.stdout)
            self.assertEqual(before, sorted(str(p.relative_to(project))
                                            for p in project.rglob("*")))
            self.assertEqual((project / "AGENTS.md").read_text(), "Local rules\\n")

    def test_assess_missing_project_fails_without_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            result = self.run_cli(REPO / "aidev", "init", str(missing),
                                  "--assess", cwd=directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(missing.exists())

    def test_project_commands_route_correctly_and_report_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project with spaces"
            initialized = self.run_cli(REPO / "aidev", "init", str(project),
                                       "--stacks", "java", cwd=directory)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            validated = self.run_cli(REPO / "cli/aidev.py", "validate", str(project), cwd=directory)
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertIn("Setup files and skill links are valid:", validated.stdout)
            self.assertIn("Builds and tests were not run", validated.stdout)
            invalid = self.run_cli(REPO / "cli/aidev.py", "task", "--project", str(project), cwd=directory)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("workflow has been removed", invalid.stderr)
            self.assertNotIn("Traceback", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
