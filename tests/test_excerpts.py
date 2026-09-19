import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from cli.excerpts import apply_budget


class ExcerptBudgetTest(unittest.TestCase):
    def selection(self, files=(), guidance=()):
        return {'files': [{'content': text} for text in files],
                'instructions': [], 'playbook': [], 'architecture': [], 'skills': [],
                'principles': [{'content': text} for text in guidance]}

    def test_unused_capacity_is_reused_in_both_directions(self):
        for files, guidance in ((['a' * 200], ['b' * 10]), (['a' * 10], ['b' * 200]),
                                ([], ['b' * 200]), (['a' * 200], [])):
            with self.subTest(files=files, guidance=guidance):
                selected = self.selection(files, guidance)
                budget = apply_budget(selected, 100, [None] * len(files))
                self.assertEqual(budget['used_chars'], 100)
                for item in selected['files'] + selected['principles']:
                    self.assertTrue(item['content'])

    def test_short_files_release_space_to_longer_files(self):
        selected = self.selection(['short', 'x' * 1000, 'y' * 1000], ['g' * 1000])
        budget = apply_budget(selected, 400, [None] * 3)
        self.assertEqual(selected['files'][0]['content'], 'short')
        self.assertFalse(selected['files'][0]['truncated'])
        self.assertGreaterEqual(len(selected['files'][1]['content']), 97)
        self.assertGreaterEqual(len(selected['files'][2]['content']), 97)
        self.assertEqual(budget['used_chars'], 400)

    def test_small_budgets_and_empty_inputs_remain_bounded(self):
        for limit in (1, 2, 3, 10):
            selected = self.selection(['', 'abc', 'def'], ['ghi'])
            budget = apply_budget(selected, limit, [None] * 3)
            self.assertLessEqual(budget['used_chars'], limit)
            for item in selected['files'] + selected['principles']:
                if not item['content']:
                    self.assertIsNone(item['excerpt'])
        self.assertEqual(apply_budget(self.selection(), 10, [])['used_chars'], 0)

    def test_fitting_content_is_unchanged_and_guidance_order_is_preserved(self):
        selected = self.selection(['source\n'], ['principle\n'])
        selected['instructions'] = [{'content': 'governing rules\n'}]
        selected['playbook'] = [{'content': 'research then implement\n'}]
        budget = apply_budget(selected, 1000, [2])
        for items in selected.values():
            for item in items:
                self.assertFalse(item['truncated'])
                self.assertEqual(item['excerpt']['start_offset'], 0)
                self.assertEqual(item['excerpt']['end_offset'], item['original_chars'])
        self.assertEqual(budget['used_chars'], sum(len(item['content']) for items in selected.values() for item in items))


if __name__ == '__main__':
    unittest.main()
