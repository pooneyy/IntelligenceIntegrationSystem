import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from Tools.ContentHistory import _ContentHistoryManager


class TestContentHistoryManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = _ContentHistoryManager(base_dir=self.temp_dir)

    def tearDown(self):
        self.manager.shutdown()
        shutil.rmtree(self.temp_dir)

    def test_save_and_retrieve_content(self):
        url = "https://example.com/test"
        content = "Test content"
        title = "Test Title"
        category = "Test Category"

        success, filepath = self.manager.save_content(url, content, title, category)
        self.assertTrue(success)
        self.assertIsNotNone(filepath)

        self.assertTrue(self.manager.has_url(url))
        self.assertEqual(self.manager.get_filepath(url), filepath)

    def test_generate_filepath(self):
        url = "https://www.sub.example.com/path"
        content = "Test content"
        title = "Test Title!"
        category = "Test/Category"

        filepath = self.manager.generate_filepath(title, content, url, category)
        self.assertIn("example", str(filepath))
        self.assertIn("TestCategory", str(filepath))
        self.assertIn("TestTitle", str(filepath))


if __name__ == '__main__':
    unittest.main()
