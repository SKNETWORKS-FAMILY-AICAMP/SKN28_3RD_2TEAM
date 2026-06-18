from __future__ import annotations

import unittest

from kaist_crawler.link_discovery import same_origin_file_link_refs, same_origin_html_links


class LinkDiscoveryTests(unittest.TestCase):
    def test_discovers_same_origin_file_links_with_context(self) -> None:
        refs = same_origin_file_link_refs(
            base_url="https://grad.example.edu/admission/",
            source_base_url="https://grad.example.edu/",
            content="""
            <p>Graduate admission guide <a href="/files/guide.pdf">Download</a></p>
            <a href="https://other.example.edu/files/other.pdf">Other</a>
            """,
        )

        self.assertEqual([ref.url for ref in refs], ["https://grad.example.edu/files/guide.pdf"])
        self.assertIn("Graduate admission guide", refs[0].context)

    def test_discovers_html_pages_and_skips_low_value_routes(self) -> None:
        links = same_origin_html_links(
            base_url="https://grad.example.edu/",
            source_base_url="https://grad.example.edu/",
            content="""
            <a href="/faculty">Faculty</a>
            <a href="/202605">Archive</a>
            <a href="/~oldhome">Old personal home</a>
            <a href="/download/file.pdf">Download</a>
            """,
        )

        self.assertEqual(links, ["https://grad.example.edu/faculty"])


if __name__ == "__main__":
    unittest.main()
