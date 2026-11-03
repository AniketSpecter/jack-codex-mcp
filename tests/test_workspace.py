import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import workspace as w
from core import parse_map_text
from scripts.make_fixture import room_text


class WorkspaceTests(unittest.TestCase):
    def test_generated_fixture_is_eight_brush_room(self):
        d=parse_map_text(room_text())
        self.assertEqual(d['brush_count'],8)
        self.assertEqual(d['face_count'],48)
        self.assertEqual(d['classes']['info_player_start'],1)

    def test_import_and_checkpoint_preserve_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);original=root/'original.map';original.write_text(room_text())
            before=original.read_bytes();workspace=root/'workspace'
            with patch.object(w,'paths',return_value=(root,root,workspace)):
                copied=w.import_copy(original)
                self.assertNotEqual(copied,original)
                self.assertEqual(copied.read_bytes(),before)
                copied.write_text(room_text()+'\n// manual edit\n')
                saved=w.checkpoint(copied)
                self.assertEqual(saved.read_bytes(),copied.read_bytes())
                receipt=json.loads(saved.with_name('receipt.json').read_text())
                self.assertEqual(receipt['sha256'],w.sha(copied))
                self.assertEqual(original.read_bytes(),before)
                with self.assertRaises(ValueError):w.checkpoint(original)
                self.assertEqual(w.import_copy(copied),copied.resolve())

    def test_new_names_reject_path_escape_and_collision(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch.object(w,'paths',return_value=(root,root,root/'workspace')),patch.object(w,'load',return_value={}):
                for bad in ['../outside','bad/name','', '0name']:
                    with self.assertRaises(ValueError):w.new_map(bad)
                w.new_map('training')
                with self.assertRaises(FileExistsError):w.new_map('training')

if __name__=='__main__':unittest.main()
