import os
from pathlib import Path
import unittest
from unittest.mock import patch

from core import parse_map_text, allowed_path, list_maps, map_summary, find_entities, validate_map, diagnose_log

ROOT = Path(__file__).resolve().parents[1] / 'examples'


class MapTests(unittest.TestCase):
    def test_parser(self):
        result = parse_map_text((ROOT / 'simple.map').read_text())
        self.assertEqual(result['entity_count'], 4)
        self.assertEqual(result['brush_count'], 3)
        self.assertEqual(result['face_count'], 4)
        self.assertEqual(result['classes']['func_door'], 1)
        self.assertEqual(result['bounds']['max'], [128.0, 128.0, 0.0])

    def test_integration(self):
        with patch.dict(os.environ, {'JACK_PROJECT_ROOT': str(ROOT)}):
            self.assertEqual(list_maps()['total'], 1)
            self.assertEqual(map_summary('simple.map')['entity_count'], 4)
            self.assertEqual(find_entities('simple.map', classname='func_door')['matched'], 1)
            self.assertEqual(validate_map('simple.map')['issues'], [])
            self.assertEqual(diagnose_log('compile.log')['matches'], 2)

    def test_path_traversal_rejected(self):
        with patch.dict(os.environ, {'JACK_PROJECT_ROOT': str(ROOT)}):
            with self.assertRaises(ValueError):
                allowed_path('../core.py', {'.py'})


if __name__ == '__main__':
    unittest.main()
