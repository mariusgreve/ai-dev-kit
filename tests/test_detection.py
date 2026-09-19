import sys
import json
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from cli.detection import detect_stacks
from cli.project import init


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
            detected = detect_stacks(project)
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
            self.assertEqual(detect_stacks(project), {})

    def test_init_accepts_detected_stacks_non_interactively(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "tsconfig.json").write_text("{}", encoding="utf-8")
            args = type("Args", (), {"project": str(project), "stacks": None, "yes": True})()
            self.assertEqual(init(args), 0)
            config = json.loads((project / ".ai/config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["stacks"], ["typescript"])


if __name__ == "__main__":
    unittest.main()
