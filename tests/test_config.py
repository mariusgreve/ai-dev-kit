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
        args = type('Args', (), {'project': str(self.project), 'stacks': ['java'], 'yes': True})()
        with contextlib.redirect_stdout(io.StringIO()):
            init(args)
        self.path = self.project / '.ai/config.json'

    def command(self, name):
        args = [name, str(self.project)] if name in {'validate', 'init'} else [
            name, 'password reset', '--project', str(self.project)]
        if name == 'init':
            args += ['--stacks', 'java']
        return subprocess.run([sys.executable, str(REPO / 'aidev'), *args],
                              text=True, capture_output=True)

    def test_all_project_commands_reject_invalid_config_without_tracebacks(self):
        invalid = [
            ('[]', 'must be an object'),
            ('{', 'invalid .ai/config.json'),
            ('{"context":{"max_files":-1}}', 'context.max_files must be a positive integer'),
            ('{"stacks":[{}]}', 'stacks must be a list of names'),
            ('{"context":{"rules":[{"terms":["reset"],"skills":5}]}}',
             'Rule skills must be a list'),
        ]
        for raw, message in invalid:
            self.path.write_text(raw, encoding='utf-8')
            for command in ('validate', 'init', 'task', 'inspect', 'explain'):
                with self.subTest(config=raw, command=command):
                    result = self.command(command)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(message, result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.project / '.ai/tasks').exists())

    def test_init_validates_before_creating_files(self):
        (self.project / 'AGENTS.md').unlink()
        self.path.write_text('[]')
        result = self.command('init')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.project / 'AGENTS.md').exists())

    def test_legacy_config_gets_defaults_without_rewriting_it(self):
        raw = '{"stacks":["java"],"custom_metadata":{"owner":"team"}}'
        self.path.write_text(raw)
        config = load_config(self.project)
        self.assertEqual(config['context']['max_files'], 20)
        self.assertEqual(config['context']['max_chars'], 32000)
        self.assertEqual(config['custom_metadata'], {'owner': 'team'})
        self.assertEqual(self.command('validate').returncode, 0)
        self.assertEqual(self.path.read_text(), raw)

    def test_missing_config_is_optional_for_preview_but_required_for_validate(self):
        self.path.unlink()
        self.assertEqual(load_config(self.project)['context']['max_files'], 20)
        self.assertEqual(self.command('inspect').returncode, 0)
        self.assertEqual(self.command('validate').returncode, 1)

    def test_wrong_types_empty_names_and_escaping_patterns_are_rejected(self):
        configs = [
            {'context': {'max_chars': True}}, {'context': {'max_files': 1.5}},
            {'principles': [' ']}, {'verification': []},
            {'context': {'rules': [{'terms': [' ']}]}},
            {'context': {'rules': [{'terms': ['reset'], 'playbook': ''}]}},
            {'context': {'rules': [{'terms': ['reset'], 'files': ['../*']}]}},
        ]
        for value in configs:
            with self.subTest(config=value):
                self.path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    load_config(self.project)

    def test_external_config_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory) / 'config.json'
            external.write_text('{}')
            self.path.unlink()
            self.path.symlink_to(external)
            result = self.command('validate')
            self.assertEqual(result.returncode, 1)
            self.assertIn('must stay inside', result.stderr)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
