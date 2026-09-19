import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from cli import installation, project as project_harness


class SkillInstallationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ai dev kit ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.kit = self.base / 'kit'
        self.installed = self.base / 'installed'
        self.home = self.base / 'home'
        self.home.mkdir()
        shutil.copytree(REPO / 'skills', self.kit / 'skills')
        self.git('init', '-b', 'main')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'initial')
        self.git('remote', 'add', 'origin', str(self.kit))
        self.root_patch = patch.object(installation, 'ROOT', self.kit)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        project_root_patch = patch.object(project_harness, 'ROOT', self.kit)
        project_root_patch.start()
        self.addCleanup(project_root_patch.stop)
        self.env_patch = patch.dict(os.environ, {'HOME': str(self.home), 'AIDEV_HOME': str(self.installed), 'CLAUDE_CONFIG_DIR': str(self.home / '.claude')})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def git(self, *args):
        return installation.git(self.kit, *args)

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'change')

    def test_github_ssh_and_https_identify_same_repository(self):
        self.assertEqual(installation.remote_identity('git@github.com:mariusgreve/ai-dev-kit.git'),
                         installation.remote_identity('https://github.com/mariusgreve/ai-dev-kit.git'))
        self.assertNotEqual(installation.remote_identity('git@github.com:other/ai-dev-kit.git'),
                            installation.remote_identity('https://github.com/mariusgreve/ai-dev-kit.git'))

    def test_global_discovery_resources_and_idempotency(self):
        self.assertEqual(installation.install_skills(), 0)
        before = installation.skill_manifest().read_text()
        self.assertEqual(installation.install_skills(), 0)
        self.assertEqual(before, installation.skill_manifest().read_text())
        for directory in installation.global_skill_roots():
            for source in (self.kit / 'skills').iterdir():
                if not (source / 'SKILL.md').is_file():
                    continue
                link = directory / source.name
                self.assertTrue(link.is_symlink())
                self.assertTrue((link / 'SKILL.md').samefile(self.installed / 'skills' / source.name / 'SKILL.md'))
                self.assertFalse((link / 'SKILL.md').samefile(source / 'SKILL.md'))
            self.assertTrue((directory / 'bootstrap-from-reference/references/integration-boundaries.md').is_file())
        self.assertFalse((self.home / '.codex/skills').exists())
        self.assertFalse((self.home / '.copilot/skills').exists())

    def test_conflicts_are_preflighted_including_broken_links(self):
        for broken in (False, True):
            with self.subTest(broken=broken):
                path = self.home / '.claude/skills/java'
                path.parent.mkdir(parents=True, exist_ok=True)
                if broken:
                    path.symlink_to(self.base / 'missing')
                else:
                    path.write_text('user content')
                with self.assertRaises(ValueError):
                    installation.install_skills()
                self.assertFalse((self.home / '.agents/skills').exists())
                self.assertTrue(path.is_symlink() if broken else path.read_text() == 'user content')
                path.unlink()

    def test_update_prunes_only_owned_links_and_adds_skills(self):
        installation.install_skills()
        replacement = self.home / '.claude/skills/java'
        replacement.unlink()
        replacement.mkdir()
        (replacement / 'SKILL.md').write_text('custom')
        shutil.rmtree(self.kit / 'skills/java')
        new = self.kit / 'skills/new-skill'
        new.mkdir()
        (new / 'SKILL.md').write_text('---\nname: new-skill\ndescription: Test\n---\n')
        self.commit()
        installation.install_skills()
        self.assertFalse((self.home / '.agents/skills/java').is_symlink())
        self.assertEqual((replacement / 'SKILL.md').read_text(), 'custom')
        self.assertTrue((self.home / '.agents/skills/new-skill').is_symlink())

    def test_uninstall_preserves_replaced_links_and_unrelated_skills(self):
        installation.install_skills()
        custom = self.home / '.agents/skills/custom'
        custom.mkdir()
        link = self.home / '.claude/skills/react'
        link.unlink()
        link.symlink_to(custom)
        with patch.object(installation, 'ROOT', self.installed):
            self.assertEqual(installation.uninstall_kit(True), 0)
        self.assertTrue(custom.is_dir())
        self.assertEqual(link.resolve(), custom.resolve())
        self.assertFalse((self.home / '.agents/skills/react').is_symlink())
        self.assertFalse(self.installed.exists())
        self.assertTrue(self.kit.exists())

    def test_highest_stable_tag_wins_over_main_and_prereleases(self):
        self.git('tag', 'v1.9.0')
        skill = self.kit / 'skills/java/SKILL.md'
        skill.write_text('version 1.10')
        self.commit()
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'tag', '-a', 'v1.10.0', '-m', 'release')
        expected = self.git('rev-parse', 'HEAD')
        skill.write_text('unreleased main')
        self.commit()
        self.git('tag', 'v2.0.0-rc.1')
        self.git('tag', 'unrelated-tag')
        skill.write_text('dirty development')
        installation.install_skills()
        self.assertEqual((self.home / '.agents/skills/java/SKILL.md').read_text(), 'version 1.10')
        metadata = json.loads((self.installed / '.aidev-release.json').read_text())
        self.assertEqual(metadata['commit'], expected)
        self.assertEqual(metadata['ref'], 'refs/tags/v1.10.0')
        self.assertEqual(skill.read_text(), 'dirty development')
        self.assertEqual(installation.git(self.installed, 'status', '--porcelain'), '')
        self.assertEqual(installation.git(self.installed, 'rev-parse', '--abbrev-ref', 'HEAD'), 'HEAD')

    def test_update_follows_new_release_but_not_main_after_release(self):
        installation.install_skills()
        skill = self.kit / 'skills/java/SKILL.md'
        skill.write_text('release')
        self.commit()
        self.git('tag', 'v1.0.0')
        installation.update_kit()
        skill.write_text('future main')
        self.commit()
        installation.update_kit()
        self.assertEqual((self.home / '.agents/skills/java/SKILL.md').read_text(), 'release')
        self.git('tag', 'v1.1.0')
        installation.update_kit()
        self.assertEqual((self.home / '.agents/skills/java/SKILL.md').read_text(), 'future main')

    def test_main_fallback_ignores_dirty_worktree_and_feature_branch(self):
        expected = (self.kit / 'skills/java/SKILL.md').read_text()
        self.git('checkout', '-b', 'feature')
        skill = self.kit / 'skills/java/SKILL.md'
        skill.write_text('feature')
        self.commit()
        skill.write_text('dirty')
        installation.install_skills()
        self.assertEqual((self.home / '.agents/skills/java/SKILL.md').read_text(), expected)
        self.assertEqual(json.loads((self.installed / '.aidev-release.json').read_text())['ref'],
                         'refs/remotes/origin/main')

    def test_failed_fetch_and_dirty_install_leave_active_skills_untouched(self):
        installation.install_skills()
        skill = self.installed / 'skills/java/SKILL.md'
        expected = skill.read_text()
        self.git('remote', 'set-url', 'origin', str(self.base / 'missing'))
        with self.assertRaises(ValueError):
            installation.update_kit()
        self.assertEqual(skill.read_text(), expected)
        self.git('remote', 'set-url', 'origin', str(self.kit))
        skill.write_text('local install edits')
        with self.assertRaises(ValueError):
            installation.update_kit()
        self.assertEqual(skill.read_text(), 'local install edits')

    def test_migrates_owned_development_links(self):
        directory = self.home / '.agents/skills'
        directory.mkdir(parents=True)
        path = directory / 'java'
        target = self.kit / 'skills/java'
        path.symlink_to(target)
        installation.skill_manifest(self.kit).write_text(json.dumps({str(path): str(target)}))
        installation.install_skills()
        self.assertEqual(path.resolve(), (self.installed / 'skills/java').resolve())
        self.assertFalse(installation.skill_manifest(self.kit).exists())

    def test_no_main_or_stable_tag_fails_without_installing(self):
        self.git('branch', '-m', 'feature-only')
        with self.assertRaises(ValueError):
            installation.install_skills()
        self.assertFalse(self.installed.exists())
        self.assertFalse((self.home / '.agents/skills').exists())

    def test_local_only_tag_is_not_a_release(self):
        upstream = self.base / 'upstream'
        subprocess.run(['git', 'clone', str(self.kit), str(upstream)], check=True, capture_output=True)
        self.git('remote', 'set-url', 'origin', str(upstream))
        expected = (upstream / 'skills/java/SKILL.md').read_text()
        (self.kit / 'skills/java/SKILL.md').write_text('local release only')
        self.commit()
        self.git('tag', 'v99.0.0')
        installation.install_skills()
        self.assertEqual((self.installed / 'skills/java/SKILL.md').read_text(), expected)

    def test_project_migration_preserves_edits_and_uses_relative_links(self):
        project = self.base / 'project'
        legacy = project / '.ai/skills/java'
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text('project override')
        project_harness.install_project_skill(project, 'java')
        project_harness.install_project_skill(project, 'bootstrap-from-reference')
        project_harness.install_project_skill(project, 'java')
        self.assertEqual((legacy / 'SKILL.md').read_text(), 'project override')
        moved = self.base / 'moved'
        shutil.move(str(project), moved)
        for directory in ('.agents/skills', '.claude/skills'):
            link = moved / directory / 'java'
            self.assertFalse(os.path.isabs(os.readlink(link)))
            self.assertEqual((link / 'SKILL.md').read_text(), 'project override')
            self.assertTrue((moved / directory / 'bootstrap-from-reference/references/integration-boundaries.md').is_file())

    def test_validate_rejects_undiscoverable_legacy_project(self):
        with patch.object(project_harness, 'ROOT', REPO):
            args = type('Args', (), {'project': str(self.base / 'project'), 'stacks': ['java'], 'yes': True})()
            self.assertEqual(project_harness.init(args), 0)
            (Path(args.project) / '.agents/skills/java').unlink()
            self.assertEqual(project_harness.validate_project(Path(args.project)), 1)
            self.assertEqual(project_harness.init(args), 0)


class InstallerLifecycleTest(unittest.TestCase):
    def test_shell_install_update_uninstall(self):
        with tempfile.TemporaryDirectory(prefix='installer space ') as temporary:
            base = Path(temporary)
            source = base / 'source'
            shutil.copytree(REPO, source, ignore=shutil.ignore_patterns('__pycache__', '.git'))
            def git(*args):
                subprocess.run(['git', '-C', str(source), *args], check=True, capture_output=True)
            git('init', '-b', 'main')
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'fixture')
            git('remote', 'add', 'origin', str(source))
            home = base / 'home'
            home.mkdir()
            installed = base / 'installed'
            bin_dir = base / 'bin'
            env = dict(os.environ, HOME=str(home), AIDEV_HOME=str(installed), AIDEV_BIN_DIR=str(bin_dir),
                       CLAUDE_CONFIG_DIR=str(home / 'custom-claude'), PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
            def run(*args):
                result = subprocess.run(args, env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # Simulate curl | bash from outside a checkout. Only the small
            # Python bootstrap is downloaded; Git supplies the stable content.
            bin_dir.mkdir()
            fake_curl = bin_dir / 'curl'
            fake_curl.write_text(
                '#!' + sys.executable + '\nimport os, shutil, sys\n'
                'assert sys.argv[sys.argv.index("--location") + 1].endswith("/cli/installation.py")\n'
                'shutil.copyfile(os.environ["AIDEV_TEST_BOOTSTRAP"], sys.argv[sys.argv.index("-o") + 1])\n')
            fake_curl.chmod(0o755)
            env['AIDEV_REPOSITORY_URL'] = str(source)
            env['AIDEV_TEST_BOOTSTRAP'] = str(source / 'cli/installation.py')
            result = subprocess.run(['bash'], input=(source / 'install.sh').read_text(),
                                    env=env, cwd=home, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            run('bash', str(source / 'install.sh'))
            run(str(bin_dir / 'aidev'), 'list')
            run(str(bin_dir / 'aidev'), 'init', str(base / 'project'), '--yes')
            run(str(bin_dir / 'aidev'), 'validate', str(base / 'project'))
            self.assertTrue((home / '.agents/skills/java/SKILL.md').samefile(installed / 'skills/java/SKILL.md'))
            self.assertTrue((home / 'custom-claude/skills/java').is_symlink())
            extra = source / 'skills/extra'
            extra.mkdir()
            (extra / 'SKILL.md').write_text('---\nname: extra\ndescription: Test\n---\n')
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'new skill')
            run(str(bin_dir / 'aidev'), 'update')
            self.assertTrue((home / '.agents/skills/extra/SKILL.md').is_file())
            run(str(bin_dir / 'aidev'), 'uninstall', '--yes')
            self.assertFalse(installed.exists())
            self.assertFalse((bin_dir / 'aidev').is_symlink())
            self.assertFalse((home / '.agents/skills/extra').is_symlink())


if __name__ == '__main__':
    unittest.main()
