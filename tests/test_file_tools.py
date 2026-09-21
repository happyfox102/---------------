import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from friday.storage import Store
from friday.file_tools import FileTools

class FileToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)); self.store.config['search_roots']=[self.tmp.name]
        self.tool=FileTools(self.store,Mock(),__import__('threading').Event())

    def test_create_rename_info_and_delete(self):
        p=Path(self.tmp.name)/'a.txt'
        self.assertTrue(self.tool.create(str(p),'file','hello')['verified'])
        self.assertEqual(self.tool.info(str(p))['type'],'text/plain')
        self.assertTrue(self.tool.rename(str(p),'b.txt')['verified'])
        self.assertTrue(self.tool.delete(str(Path(self.tmp.name)/'b.txt'))['verified'])

    def test_copy_and_move_never_overwrite(self):
        source=Path(self.tmp.name)/'source.txt'; source.write_text('x')
        dest=Path(self.tmp.name)/'dest.txt'; dest.write_text('old')
        with self.assertRaises(FileExistsError): self.tool.copy(str(source),str(dest))
        dest.unlink(); self.assertTrue(self.tool.copy(str(source),str(dest))['verified'])
        moved=Path(self.tmp.name)/'moved.txt'; self.assertTrue(self.tool.move(str(dest),str(moved))['verified'])

    def test_paths_outside_configured_roots_are_rejected(self):
        with self.assertRaises(ValueError): self.tool.info(str(Path(self.tmp.name).parent/'outside.txt'))
        with self.assertRaises(ValueError): self.tool.create(str(Path(self.tmp.name)/'..'/'escape.txt'),'file','x')

    def test_delete_data_root_is_forbidden(self):
        with self.assertRaises(ValueError): self.tool.delete(str(self.store.data))

    def test_descendant_copy_move_and_root_delete_are_rejected(self):
        folder = Path(self.tmp.name)/'folder'; folder.mkdir()
        for method in (self.tool.copy, self.tool.move):
            with self.assertRaises(ValueError): method(str(folder), str(folder/'child'))
        with self.assertRaises(ValueError): self.tool.delete(self.tmp.name)
        with self.assertRaises(ValueError): self.tool.move(str(self.store.data), str(folder/'data'))

    def test_delete_is_recoverable(self):
        target = Path(self.tmp.name)/'important.txt'; target.write_text('keep')
        result = self.tool.delete(str(target))
        self.assertFalse(target.exists())
        self.assertEqual(Path(result['recovery']).read_text(), 'keep')
        self.assertIn(str(target.resolve()), (Path(result['recovery']).parent/'restore.txt').read_text(encoding='utf-8'))

    def test_invalid_create_leaves_no_directories(self):
        target = Path(self.tmp.name)/'new'/'invalid.txt'
        with self.assertRaises(ValueError): self.tool.create(str(target), 'invalid', '')
        self.assertFalse(target.parent.exists())

    def test_search_roots_are_refreshed_after_settings_change(self):
        self.store.config['search_roots'] = []
        with self.assertRaises(ValueError): self.tool.info(self.tmp.name)

if __name__=='__main__': unittest.main()
