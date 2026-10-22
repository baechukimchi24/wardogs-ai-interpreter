import unittest
from subtitle_layout import pages_for_text, wrap_measured

class CaptionPaginationTests(unittest.TestCase):
    def test_short_line_unmodified(self):
        pages = pages_for_text('옥상에 적 두 명 있어!', 500, len, 2)
        self.assertEqual(pages, ['옥상에 적 두 명 있어!'])

    def test_long_korean_is_never_dropped(self):
        ko = '북쪽 입구에 적이 있습니다 지금 빠르게 진입하고 있어서 당장 지원이 필요합니다 '*8
        pages = pages_for_text(ko, 28, len, 2)
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(page.splitlines()) <= 2 for page in pages))
        self.assertEqual(' '.join(' '.join(page.splitlines()) for page in pages).split(), ko.split())

    def test_wide_unbroken_word_is_paginated(self):
        source = '초강력화력지원반복' * 15
        pages = pages_for_text(source, 8, len, 2)
        self.assertEqual(''.join(page.replace('\n','') for page in pages), source)
        self.assertTrue(all(len(line) <= 8 for page in pages for line in page.splitlines()))

    def test_empty_is_one_blank_page(self):
        self.assertEqual(pages_for_text('', 20, len), [''])

    def test_break_at_original_newlines(self):
        self.assertEqual(wrap_measured('방어 중\n왼쪽 지원', 80, len), ['방어 중', '왼쪽 지원'])

if __name__ == '__main__': unittest.main()
