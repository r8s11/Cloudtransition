"""Fixture tests for tools/arms/image_descriptions.py (standard library unittest).

    python3 -m unittest discover -s tools/arms -p 'test_image_descriptions.py'
"""
import hashlib
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("image_descriptions", Path(__file__).with_name("image_descriptions.py"))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

RESULT = {'caption': {'title': 'T', 'description': 'D', 'visible_text': [], 'uncertainty': ''},
          'models': ['claude-haiku-5-5'], 'requested': 'haiku', 'cost': 0}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / 'ws'
        self.root.mkdir()
        self.saved = (m.ROOT, m.MANIFEST, m.TEMPLATE_HASHES, m.claude_routing)
        m.ROOT, m.MANIFEST = self.root, self.root / 'resources/image-coverage.md'
        m.claude_routing = lambda: {'base_url_host': None, 'reachable': None}

    def tearDown(self):
        m.ROOT, m.MANIFEST, m.TEMPLATE_HASHES, m.claude_routing = self.saved
        self.tmp.cleanup()

    def make(self, relative, data=b'png-bytes'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def scanned(self):
        return [m.rel(p) for p in m.scan()[0]]


class ScopeBoundaries(Fixture):
    def test_template_exclusion_is_per_file_and_hash_checked(self):
        icon = self.make('projects/ReactNative/Mytvapp/assets/images/icon.png', b'template')
        m.TEMPLATE_HASHES = {'icon.png': hashlib.sha256(b'template').hexdigest()}
        self.make('projects/ReactNative/Mytvapp/assets/images/brand.png')
        self.make('projects/ReactNative/Mytvapp/assets/images/other/icon.png')
        self.assertNotIn('projects/ReactNative/Mytvapp/assets/images/icon.png', self.scanned())  # original: excluded
        icon.write_bytes(b'customised')
        self.assertIn('projects/ReactNative/Mytvapp/assets/images/icon.png', self.scanned())  # edited: in scope
        icon.write_bytes(b'template')
        self.assertFalse(m.in_scope(icon))
        self.assertIn('projects/ReactNative/Mytvapp/assets/images/brand.png', self.scanned())
        self.assertIn('projects/ReactNative/Mytvapp/assets/images/other/icon.png', self.scanned())

    def test_private_names_excluded_for_dirs_and_files_but_nested_git_is_not(self):
        self.make('IT Mgmt/Employer-IT-Playbook-Private/docs/a.png')
        self.make('art/private-notes.png')
        self.make('art/secret.PNG')
        self.make('playbook/diagram.png')
        (self.root / 'playbook/.git').mkdir()
        self.make('art/ok.png')
        self.assertEqual(self.scanned(), ['art/ok.png', 'playbook/diagram.png'])
        for blocked in ('IT Mgmt/Employer-IT-Playbook-Private/docs/a.png', 'art/private-notes.png', 'art/secret.PNG'):
            self.assertFalse(m.in_scope(self.root / blocked), blocked)
        self.assertTrue(m.in_scope(self.root / 'playbook/diagram.png'))

    def test_symlinks_rejected_including_parent_directories(self):
        real = self.make('real/pic.png')
        (self.root / 'alias').symlink_to(self.root / 'real', target_is_directory=True)
        (self.root / 'real/link.png').symlink_to(real)
        self.assertTrue(m.in_scope(real))
        self.assertFalse(m.in_scope(self.root / 'alias/pic.png'))
        self.assertFalse(m.in_scope(self.root / 'real/link.png'))
        self.assertEqual(self.scanned(), ['real/pic.png'])
        outside = Path(self.tmp.name).resolve() / 'outside.png'
        outside.write_bytes(b'x')
        self.assertFalse(m.in_scope(outside))

    def test_dot_vendor_and_saved_page_dirs_excluded(self):
        for blocked in ('.tool/a.png', 'node_modules/a.png', 'page_files/a.png', 'College Planning/a.png'):
            self.make(blocked)
        self.make('keep.png')
        self.assertEqual(self.scanned(), ['keep.png'])


class PromptExactness(Fixture):
    def render_and_read(self, prompt_text):
        image = self.make('gen/cover.png')
        sidecar = image.with_name('cover.png.md')
        m.write_new(sidecar, m.render(image, RESULT, {'text': prompt_text, 'model': 'gen-model', 'tool': None}))
        content = sidecar.read_bytes().decode('utf-8')
        block = content.split('## Original prompt\n\n', 1)[1]
        opening, rest = block.split('\n', 1)
        ticks = opening[:-len('text')]
        self.assertTrue(set(ticks) == {'`'} and len(ticks) >= 3)
        recovered = rest[: rest.rindex('\n' + ticks)]  # drop the single separator newline
        return content, recovered

    def test_prompt_preserved_byte_for_byte(self):
        for text in ('plain', 'ends with newline\n', 'two\n\n', 'crlf\r\nline\r\n', '  lead and trail  ',
                     'has ``` fence\nand ```` longer\n', 'unicode \u00e9\u4e2d'):
            content, recovered = self.render_and_read(text)
            self.assertEqual(recovered, text)
            self.assertIn(f'Prompt SHA-256: {hashlib.sha256(text.encode("utf-8")).hexdigest()}', content)
            os.remove(self.root / 'gen/cover.png.md')

    def test_write_new_never_overwrites(self):
        sidecar = self.root / 'x.png.md'
        m.write_new(sidecar, 'one')
        with self.assertRaises(FileExistsError):
            m.write_new(sidecar, 'two')
        self.assertEqual(sidecar.read_text(), 'one')



if __name__ == '__main__':
    unittest.main()
