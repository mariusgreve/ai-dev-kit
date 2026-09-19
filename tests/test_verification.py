"""Exercise the generated, project-local runner with actual subprocesses."""

import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from cli.project import init, verify_script


class VerificationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='aidev verification ')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / 'project'
        (self.project / '.ai').mkdir(parents=True)
        self.script = self.project / '.ai/verify.sh'
        self.script.write_text(verify_script())
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.log = self.base / 'commands.jsonl'
        # Stand-in tools make working directory, command selection and failure
        # propagation observable without downloading project dependencies.
        for name in ('npm', 'pnpm', 'yarn', 'bun'):
            tool = self.bin / name
            tool.write_text('#!' + sys.executable + '\n'
                'import json, os, pathlib, sys\n'
                'with open(os.environ["VERIFY_TEST_LOG"], "a") as log:\n'
                ' log.write(json.dumps([pathlib.Path(sys.argv[0]).name, os.getcwd(), sys.argv[1:]]) + "\\n")\n'
                'sys.exit(int(os.environ.get("VERIFY_TEST_EXIT", 0)))\n')
            tool.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'VERIFY_TEST_LOG': str(self.log)}

    def write(self, path, content):
        target = self.project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    def package(self, directory='.', **fields):
        return self.write(str(Path(directory) / 'package.json'), json.dumps(fields))

    def run_script(self, env=None):
        return subprocess.run(['bash', str(self.script)], cwd=self.base,
                              text=True, capture_output=True, env=env or self.env)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_empty_or_uncheckable_project_fails(self):
        self.assertEqual(self.run_script().returncode, 2)
        self.package(scripts={'test': ' ', 'lint': ''})
        self.assertEqual(self.run_script().returncode, 2)
        self.assertEqual(self.commands(), [])

    def test_frontend_and_backend_both_run_from_their_directory(self):
        self.package('frontend', scripts={'lint': 'eslint', 'test': 'vitest', 'build': 'vite build'})
        self.write('backend/pom.xml', '<project/>')
        marker = self.project / 'backend/verified.txt'
        self.write('backend/mvnw', '#!/bin/sh\ntest "$1" = verify || exit 8\npwd > verified.txt\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(marker.read_text().strip(), str(self.project / 'backend'))
        self.assertEqual([row[2] for row in self.commands()], [['run', 'lint'], ['run', 'test'], ['run', 'build']])
        self.assertTrue(all(row[1] == str(self.project / 'frontend') for row in self.commands()))

    def test_detects_new_module_without_regenerating_script(self):
        self.write('backend/gradlew', '#!/bin/sh\nexit 0\n')
        self.assertEqual(self.run_script().returncode, 0)
        self.package('frontend', scripts={'build': 'vite build'})
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.commands()[0][2], ['run', 'build'])

    def test_checkless_frontend_cannot_hide_behind_passing_backend(self):
        self.write('backend/gradlew', '#!/bin/sh\nexit 0\n')
        self.package('frontend', scripts={})
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn('frontend', result.stderr)
        self.assertNotIn('Verification passed', result.stdout)

    def test_failing_check_stops_and_preserves_exit_status(self):
        self.package(scripts={'lint': 'eslint', 'test': 'vitest'})
        result = self.run_script({**self.env, 'VERIFY_TEST_EXIT': '7'})
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.commands()), 1)

    def test_java_failure_and_missing_wrapper_are_reported(self):
        self.write('backend/pom.xml', '<project/>')
        self.assertEqual(self.run_script().returncode, 2)
        self.write('backend/mvnw', '#!/bin/sh\nexit 9\n')
        self.assertEqual(self.run_script().returncode, 9)

    def test_invalid_package_metadata_fails(self):
        for raw in ('{', '[]', '{"scripts":[]}', '{"scripts":{"test":4}}', '{"scripts":{"test:ci":0}}'):
            with self.subTest(raw=raw):
                self.write('package.json', raw)
                result = self.run_script()
                self.assertEqual(result.returncode, 1)
                self.assertNotIn('Traceback', result.stderr)

    def test_package_manager_and_ci_test_selection(self):
        for manager in ('npm', 'pnpm', 'yarn', 'bun'):
            with self.subTest(manager=manager):
                self.package(packageManager=f'{manager}@1.0.0', scripts={'test': 'watch', 'test:ci': 'run', 'build': 'build'})
                result = self.run_script()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.commands()[-2][0], manager)
                self.assertEqual(self.commands()[-2][2], ['run', 'test:ci'])

    def test_empty_ci_script_falls_back_to_test(self):
        self.package(scripts={'test:ci': ' ', 'test': 'run'})
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.commands()[0][2], ['run', 'test'])

    def test_nested_package_inherits_declared_package_manager(self):
        self.package(packageManager='pnpm@1', scripts={'build': 'root-build'})
        self.write('package-lock.json', '')
        self.package('frontend', scripts={'test': 'run'})
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual([row[0] for row in self.commands()], ['pnpm', 'pnpm'])

    def test_lockfile_selects_package_manager(self):
        for lock, manager in (('package-lock.json', 'npm'), ('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'), ('bun.lock', 'bun')):
            with self.subTest(lock=lock):
                self.package(scripts={'build': 'build'})
                path = self.write(lock, '')
                self.assertEqual(self.run_script().returncode, 0)
                self.assertEqual(self.commands()[-1][0], manager)
                path.unlink()

    def test_conflicting_or_unsupported_package_manager_fails(self):
        self.package(scripts={'test': 'run'})
        self.write('pnpm-lock.yaml', '')
        self.write('yarn.lock', '')
        self.assertEqual(self.run_script().returncode, 1)
        self.package(packageManager='custom@1', scripts={'test': 'run'})
        self.assertEqual(self.run_script().returncode, 1)

    def test_workspaces_and_java_multimodule_builds_use_root_checks_once(self):
        self.package(workspaces=['packages/*'], scripts={'test': 'workspace-tests'})
        self.package('packages/app', scripts={'test': 'package-tests'})
        self.write('pom.xml', '<project/>')
        self.write('mvnw', '#!/bin/sh\nexit 0\n')
        self.write('modules/service/pom.xml', '<project/>')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.commands()), 1)

    def test_generated_and_symlinked_directories_are_ignored(self):
        self.package(scripts={'build': 'build'})
        for directory in ('node_modules/pkg', 'dist', '.cache', 'target'):
            self.package(directory, scripts={'test': 'should-not-run'})
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'package.json').write_text('{"scripts":{"test":"should-not-run"}}')
        (self.project / 'linked').symlink_to(outside)
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(len(self.commands()), 1)

    def test_reinitializing_preserves_project_owned_verification(self):
        custom = '#!/bin/sh\necho custom-verification\n'
        self.script.write_text(custom)
        self.script.chmod(0o755)
        args = type('Args', (), {'project': str(self.project), 'stacks': ['typescript'], 'yes': True})()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(init(args), 0)
        self.assertEqual(self.script.read_text(), custom)

    @unittest.skipUnless(shutil.which('npm'), 'npm required for real script execution')
    def test_real_npm_runs_build_and_nonwatch_tests_with_ci_set(self):
        code = 'import os,pathlib; assert os.environ["CI"] == "true"; pathlib.Path("proof").touch()'
        command = shlex.join([sys.executable, '-c', code])
        self.package(scripts={'test:ci': command, 'build': command})
        result = self.run_script(os.environ.copy())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / 'proof').exists())


if __name__ == '__main__':
    unittest.main()
