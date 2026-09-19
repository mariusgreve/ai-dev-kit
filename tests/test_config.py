import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from cli.config import load_config
from cli.project import init


class ConfigTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='aidev config ')
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.initialize(['java'])
        self.path = self.project / '.ai/config.json'

    def initialize(self, stacks):
        args = type('Args', (), {'project': str(self.project), 'stacks': stacks, 'yes': True})()
        with contextlib.redirect_stdout(io.StringIO()):
            return init(args)

    def command(self, name):
        args = [name, str(self.project)]
        if name == 'init':
            args += ['--stacks', 'java']
        return subprocess.run([sys.executable, str(REPO / 'aidev'), *args], text=True, capture_output=True)

    def test_init_and_validate_reject_invalid_config_before_writing(self):
        for raw in ('[]', '{', '{"stacks":[{}]}', '{"stacks":["missing"]}', '{"stacks":"java"}'):
            self.path.write_text(raw)
            (self.project / 'AGENTS.md').unlink(missing_ok=True)
            for command in ('init', 'validate'):
                with self.subTest(config=raw, command=command):
                    result = self.command(command)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn('.ai/config.json', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_existing_project_files_and_legacy_metadata_are_preserved(self):
        config = {'stacks': ['java'], 'context': {'max_chars': 100},
                  'verification': './custom-checks', 'custom_metadata': {'owner': 'team'}}
        raw = json.dumps(config)
        self.path.write_text(raw)
        contents = {'AGENTS.md': '# Custom instructions', '.ai/verify.sh': '#!/bin/sh\nexit 0\n',
                    '.ai/skills/java/SKILL.md': 'Custom Java guidance'}
        for name, content in contents.items():
            (self.project / name).write_text(content)
        self.assertEqual(self.initialize(['java']), 0)
        self.assertEqual(self.path.read_text(), raw)
        self.assertEqual(self.initialize(['react']), 0)
        updated = json.loads(self.path.read_text())
        self.assertEqual(updated, {**config, 'stacks': ['java', 'react']})
        for name, content in contents.items():
            self.assertEqual((self.project / name).read_text(), content)
        self.assertTrue((self.project / '.agents/skills/react/SKILL.md').is_file())

    def test_missing_config_is_allowed_for_init_only(self):
        self.path.unlink()
        self.assertEqual(load_config(self.project), {})
        self.assertEqual(self.command('validate').returncode, 1)
        self.assertEqual(self.command('init').returncode, 0)

    def test_external_config_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory) / 'config.json'
            external.write_text('{}')
            self.path.unlink()
            self.path.symlink_to(external)
            result = self.command('init')
            self.assertEqual(result.returncode, 1)
            self.assertIn('must stay inside', result.stderr)
            self.assertEqual(external.read_text(), '{}')

    def test_init_does_not_create_task_or_architecture_documents(self):
        for name in ('architecture', 'specs', '.ai/tasks', '.ai/context', '.ai/playbooks', '.ai/principles', '.ai/templates'):
            self.assertFalse((self.project / name).exists(), name)

    def test_discovery_conflicts_are_reported_before_new_files_are_written(self):
        (self.project / 'AGENTS.md').unlink()
        conflict = self.project / '.claude/skills/react'
        conflict.mkdir()
        (conflict / 'SKILL.md').write_text('unrelated skill')
        with self.assertRaises(ValueError):
            self.initialize(['react'])
        self.assertFalse((self.project / 'AGENTS.md').exists())
        self.assertFalse((self.project / '.ai/skills/react').exists())
        self.assertEqual(json.loads(self.path.read_text())['stacks'], ['java'])

    def test_validate_rejects_nonexecutable_verification(self):
        (self.project / '.ai/verify.sh').chmod(0o644)
        result = self.command('validate')
        self.assertEqual(result.returncode, 1)
        self.assertIn('not executable', result.stderr)


if __name__ == '__main__':
    unittest.main()
