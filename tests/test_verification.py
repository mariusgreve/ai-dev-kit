import contextlib
import io
import json
from pathlib import Path
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
        self.project = Path(temporary.name)
        (self.project / '.ai').mkdir()
        self.script = self.project / '.ai/verify.sh'

    def run_script(self, stacks=None):
        self.script.write_text(verify_script(stacks or {'typescript'}))
        return subprocess.run(['bash', str(self.script)], cwd=self.project.parent,
                              text=True, capture_output=True)

    def package(self, scripts=None):
        package = {'name': 'verification-fixture', 'private': True}
        if scripts is not None:
            package['scripts'] = scripts
        (self.project / 'package.json').write_text(json.dumps(package))

    def test_no_build_or_supported_scripts_fails_instead_of_passing(self):
        cases = [None, {}, {'build': 'echo build'}, {'lint': '', 'test': '  '}]
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        for scripts in cases:
            with self.subTest(scripts=scripts):
                self.package(scripts)
                result = self.run_script()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('No verification checks ran', result.stderr)
                self.assertNotIn('Verification passed', result.stdout)

    @unittest.skipUnless(shutil.which('npm'), 'npm is needed to exercise actual npm scripts')
    def test_runs_and_reports_only_present_checks(self):
        self.package({'lint': 'echo lint-proof', 'test': 'echo test-proof'})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Running: npm run lint', result.stdout)
        self.assertIn('Running: npm run test', result.stdout)
        self.assertIn('lint-proof', result.stdout)
        self.assertNotIn('npm run typecheck', result.stdout)
        self.assertIn('Verification passed: 2 check(s).', result.stdout)

    @unittest.skipUnless(shutil.which('npm'), 'npm is needed to exercise actual npm scripts')
    def test_failing_check_stops_verification_and_preserves_failure(self):
        self.package({'lint': 'exit 7', 'test': 'echo should-not-run'})
        result = self.run_script()
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertNotIn('Running: npm run test', result.stdout)
        self.assertNotIn('Verification passed', result.stdout)

    def test_malformed_package_or_scripts_fails_explicitly(self):
        for raw in ('{', '[]', '{"scripts":[]}', '{"scripts":{"test":4}}'):
            with self.subTest(package=raw):
                (self.project / 'package.json').write_text(raw)
                result = self.run_script()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Invalid package.json:', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn('Verification passed', result.stdout)

    def test_reports_gradle_and_maven_checks_and_propagates_failure(self):
        for wrapper, argument in (('gradlew', 'check'), ('mvnw', 'verify')):
            path = self.project / wrapper
            for status in (0, 9):
                with self.subTest(wrapper=wrapper, status=status):
                    path.write_text(f'#!/bin/sh\ntest "$1" = "{argument}" || exit 99\nexit {status}\n')
                    path.chmod(0o755)
                    result = self.run_script({'java'})
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertIn(f'Running: ./{wrapper} {argument}', result.stdout)
                    self.assertEqual('Verification passed' in result.stdout, status == 0)
            path.unlink()

    def test_backend_check_counts_when_frontend_has_no_checks(self):
        wrapper = self.project / 'gradlew'
        wrapper.write_text('#!/bin/sh\nexit 0\n')
        wrapper.chmod(0o755)
        self.package({})
        result = self.run_script({'java', 'typescript'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Verification passed: 1 check(s).', result.stdout)

    def test_reinitializing_preserves_project_owned_verification(self):
        custom = '#!/bin/sh\necho custom-verification\n'
        self.script.write_text(custom)
        args = type('Args', (), {'project': str(self.project), 'stacks': ['typescript'], 'yes': True})()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(init(args), 0)
        self.assertEqual(self.script.read_text(), custom)


if __name__ == '__main__':
    unittest.main()
