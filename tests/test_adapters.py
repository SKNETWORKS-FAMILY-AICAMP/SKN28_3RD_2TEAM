from __future__ import annotations

import unittest

from kaist_crawler.adapters import StaticHtmlAdapter
from kaist_crawler.models import SourceConfig


class StaticHtmlAdapterTests(unittest.TestCase):
    def test_same_origin_links_include_extensionless_pages(self) -> None:
        source = SourceConfig(
            id="sample",
            name="Sample",
            base_url="https://grad.example.edu/",
            adapter="static_html",
        )
        adapter = StaticHtmlAdapter(source, client=None, store=None)  # type: ignore[arg-type]

        links = adapter._same_origin_html_links(
            "https://grad.example.edu/",
            """
            <a href="/faculty">Faculty</a>
            <a href="/admission.html">Admission</a>
            <a href="/index.php?mid=notice">Notice</a>
            <a href="/files/guide.pdf">Guide</a>
            <a href="javascript">Broken JS</a>
            <a href="/@facebook">Facebook</a>
            <a href="https://other.example.edu/faculty">Other</a>
            """,
        )

        self.assertIn("https://grad.example.edu/faculty", links)
        self.assertIn("https://grad.example.edu/admission.html", links)
        self.assertIn("https://grad.example.edu/index.php?mid=notice", links)
        self.assertNotIn("https://grad.example.edu/files/guide.pdf", links)
        self.assertNotIn("https://grad.example.edu/javascript", links)
        self.assertNotIn("https://grad.example.edu/@facebook", links)
        self.assertNotIn("https://other.example.edu/faculty", links)


if __name__ == "__main__":
    unittest.main()
