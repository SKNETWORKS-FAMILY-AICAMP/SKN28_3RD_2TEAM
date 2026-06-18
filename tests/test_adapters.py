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
            <a href="/news/file_down/id/209">Download</a>
            <a href="javascript">Broken JS</a>
            <a href="/@facebook">Facebook</a>
            <a href="https://other.example.edu/faculty">Other</a>
            """,
        )

        self.assertIn("https://grad.example.edu/faculty", links)
        self.assertIn("https://grad.example.edu/admission.html", links)
        self.assertIn("https://grad.example.edu/index.php?mid=notice", links)
        self.assertNotIn("https://grad.example.edu/files/guide.pdf", links)
        self.assertNotIn("https://grad.example.edu/news/file_down/id/209", links)
        self.assertNotIn("https://grad.example.edu/javascript", links)
        self.assertNotIn("https://grad.example.edu/@facebook", links)
        self.assertNotIn("https://other.example.edu/faculty", links)

    def test_file_links_come_from_html_attributes_only(self) -> None:
        source = SourceConfig(
            id="sample",
            name="Sample",
            base_url="https://grad.example.edu/",
            adapter="static_html",
        )
        adapter = StaticHtmlAdapter(source, client=None, store=None)  # type: ignore[arg-type]

        links = adapter._same_origin_file_links(
            "https://grad.example.edu/news/view/id/148",
            """
            <main>Attached files: test.hwp guide.pdf</main>
            <a href="/files/admission-guide.pdf">Guide</a>
            <a href="file:///C:/Users/office/local.docx">Local file</a>
            """,
        )

        self.assertEqual(links, ["https://grad.example.edu/files/admission-guide.pdf"])

    def test_download_file_applies_policy_before_network_request(self) -> None:
        source = SourceConfig(
            id="sample",
            name="Sample",
            base_url="https://grad.example.edu/",
            adapter="static_html",
            raw_options={
                "file_policy": {
                    "exclude_url_patterns": [r"(?i)/oldexam/"],
                }
            },
        )
        store = FakeStore()
        adapter = StaticHtmlAdapter(source, client=FailingClient(), store=store)  # type: ignore[arg-type]

        adapter.download_file("/resource/oldexam/Midterm.pdf")

        self.assertEqual(store.skipped[0]["reason"], "excluded_url_pattern")

    def test_download_file_skips_non_http_urls(self) -> None:
        source = SourceConfig(
            id="sample",
            name="Sample",
            base_url="https://grad.example.edu/",
            adapter="static_html",
        )
        store = FakeStore()
        adapter = StaticHtmlAdapter(source, client=FailingClient(), store=store)  # type: ignore[arg-type]

        adapter.download_file("file:///C:/Users/office/local.docx")

        self.assertEqual(store.skipped[0]["reason"], "unsupported_url_scheme")


class FailingClient:
    def head(self, url: str) -> None:
        raise AssertionError(f"network should not be called for {url}")

    def get(self, url: str) -> None:
        raise AssertionError(f"network should not be called for {url}")


class FakeStore:
    def __init__(self) -> None:
        self.skipped = []

    def record_skipped_file(
        self,
        *,
        site: str,
        adapter: str,
        source_url: str,
        final_url: str | None,
        reason: str,
        metadata: dict | None = None,
    ) -> None:
        self.skipped.append(
            {
                "site": site,
                "adapter": adapter,
                "source_url": source_url,
                "final_url": final_url,
                "reason": reason,
                "metadata": metadata or {},
            }
        )


if __name__ == "__main__":
    unittest.main()
