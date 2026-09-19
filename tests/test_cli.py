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
