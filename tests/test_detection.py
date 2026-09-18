import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "aidev.py"
SPEC = importlib.util.spec_from_file_location("aidev_cli", CLI_PATH)
aidev = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(aidev)


class StackDetectionTest(unittest.TestCase):
    def test_detects_supported_stacks_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "pom.xml").write_text(
                "org.springframework.boot spring-boot org.postgresql", encoding="utf-8"
            )
            (project / "package.json").write_text(
                json.dumps({"dependencies": {"react": "latest", "typescript": "latest"}}),
                encoding="utf-8",
            )
            detected = aidev.detect_stacks(project)
            self.assertEqual(
                set(detected), {"java", "spring", "postgres", "react", "typescript"}
            )
            self.assertEqual(detected["spring"], ["pom.xml"])

    def test_ignores_dependency_and_build_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            generated = project / "node_modules" / "example"
            generated.mkdir(parents=True)
            (generated / "package.json").write_text('{"dependencies":{"react":"latest"}}')
            self.assertEqual(aidev.detect_stacks(project), {})

    def test_init_accepts_detected_stacks_non_interactively(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "tsconfig.json").write_text("{}", encoding="utf-8")
            args = type("Args", (), {"project": str(project), "stacks": None, "yes": True})()
            self.assertEqual(aidev.init(args), 0)
            config = json.loads((project / ".ai/config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["stacks"], ["typescript"])


if __name__ == "__main__":
    unittest.main()
