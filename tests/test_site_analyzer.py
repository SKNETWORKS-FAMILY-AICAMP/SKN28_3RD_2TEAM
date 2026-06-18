from __future__ import annotations

import unittest

from kaist_crawler.config import build_crawler_config
from kaist_crawler.http_client import FetchResult
from kaist_crawler.site_analyzer import analyze_site, known_file_refs, recommend_routes


class FakeClient:
    def __init__(self, responses: dict[str, FetchResult]) -> None:
        self.responses = responses

    def get(self, url: str) -> FetchResult:
        if url not in self.responses:
            raise RuntimeError(f"unexpected URL: {url}")
        return self.responses[url]


def response(url: str, text: str, content_type: str = "text/html; charset=utf-8") -> FetchResult:
    return FetchResult(
        url=url,
        final_url=url,
        content=text.encode("utf-8"),
        content_type=content_type,
        status_code=200,
    )


class SiteAnalyzerTests(unittest.TestCase):
    def test_known_file_refs_ignore_javascript_document_fragments(self) -> None:
        refs = known_file_refs(
            "https://grad.example.edu/",
            [
                "a.document&&11!==a.doc; window.document",
                "left=ui.offset.left-that.doc",
                '<a href="/files/admission-guide.pdf">guide</a>',
            ],
        )

        self.assertEqual(refs, ["https://grad.example.edu/files/admission-guide.pdf"])

    def test_recommended_routes_keep_base_path_root(self) -> None:
        routes = recommend_routes(
            base_url="https://grad.example.edu/home/",
            links=["https://grad.example.edu/home/faculty/"],
            js_routes=[],
            adapter="static_html",
            max_routes=5,
        )

        self.assertEqual(routes[0], "./")
        self.assertIn("faculty/", routes)

    def test_static_html_site_recommends_static_adapter_and_routes(self) -> None:
        root = "https://grad.example.edu/"
        long_text = "Graduate admission faculty curriculum scholarship. " * 80
        html = f"""
        <html>
          <head><title>Example Graduate School</title></head>
          <body>
            <nav>
              <a href="/admission.html">Admission</a>
              <a href="/faculty.html">Faculty</a>
              <a href="/files/admission-guide.pdf">PDF</a>
            </nav>
            <main>{long_text}</main>
          </body>
        </html>
        """
        client = FakeClient(
            {
                root: response(root, html),
                "https://grad.example.edu/robots.txt": response(
                    "https://grad.example.edu/robots.txt",
                    "User-agent: *\nAllow: /\n",
                    "text/plain",
                ),
                "https://grad.example.edu/sitemap.xml": response(
                    "https://grad.example.edu/sitemap.xml",
                    '<?xml version="1.0"?><urlset></urlset>',
                    "application/xml",
                ),
            }
        )

        analysis = analyze_site(root, client=client)
        source = analysis.recommended_source()

        self.assertEqual(analysis.adapter, "static_html")
        self.assertIn("/admission.html", analysis.routes)
        self.assertIn("/faculty.html", analysis.routes)
        self.assertNotIn("/files/admission-guide.pdf", analysis.routes)
        self.assertIn("https://grad.example.edu/files/admission-guide.pdf", analysis.known_files)
        self.assertIsNotNone(analysis.site_profile)
        self.assertIsNotNone(analysis.crawl_plan)
        self.assertEqual(analysis.site_profile.cms_type, "generic")
        self.assertIn("file_policy", source["raw"])
        build_crawler_config({"version": 1, "sources": [source]})

    def test_query_board_routes_are_preserved_in_crawl_plan(self) -> None:
        root = "https://physics.example.edu/"
        html = """
        <html>
          <head><title>Physics</title></head>
          <body>
            <a href="/index.php?mid=Account&act=dispMemberLoginForm">LOGIN</a>
            <a href="/index.php?mid=p_academic4">Graduate admission</a>
            <a href="/index.php?document_srl=123">Notice detail</a>
            <main>Physics graduate admission faculty seminar curriculum.</main>
          </body>
        </html>
        """
        client = FakeClient(
            {
                root: response(root, html),
                "https://physics.example.edu/robots.txt": response(root + "robots.txt", "User-agent: *\n", "text/plain"),
                "https://physics.example.edu/sitemap.xml": response(root + "sitemap.xml", "<html></html>", "text/html"),
            }
        )

        analysis = analyze_site(root, client=client)

        self.assertIn("/index.php?mid=p_academic4", analysis.routes)
        self.assertNotIn("/index.php?mid=Account&act=dispMemberLoginForm", analysis.routes)
        self.assertIn("query_routes", analysis.site_profile.url_patterns)
        self.assertIn("mid", analysis.crawl_plan.route_policy["preserve_query_for"])

    def test_spa_with_google_sheets_recommends_spa_sheet_adapter(self) -> None:
        root = "https://ai.example.edu/"
        html = """
        <html>
          <head>
            <title>AI Graduate School</title>
            <script type="module" src="/assets/index.js"></script>
          </head>
          <body><div id="root"></div></body>
        </html>
        """
        asset = """
        import React from "react";
        const routes = ["/faculty", "/admission", "/curriculum", "/notice"];
        const sheet = "https://docs.google.com/spreadsheets/d/abcDEF_12345/gviz/tq";
        """
        client = FakeClient(
            {
                root: response(root, html),
                "https://ai.example.edu/assets/index.js": response(
                    "https://ai.example.edu/assets/index.js",
                    asset,
                    "application/javascript",
                ),
                "https://ai.example.edu/robots.txt": response(
                    "https://ai.example.edu/robots.txt",
                    "User-agent: *\nSitemap: https://ai.example.edu/sitemap.xml\n",
                    "text/plain",
                ),
                "https://ai.example.edu/sitemap.xml": response(
                    "https://ai.example.edu/sitemap.xml",
                    "<html>spa fallback</html>",
                    "text/html",
                ),
            }
        )

        analysis = analyze_site(root, client=client)
        source = analysis.recommended_source()

        self.assertEqual(analysis.adapter, "vite_react_spa_with_google_sheets")
        self.assertEqual(source["google_sheets"]["spreadsheet_id"], "abcDEF_12345")
        self.assertTrue(source["raw"]["render_routes"])
        self.assertIn("/faculty", source["routes"])
        self.assertIn("Google Sheets", " ".join(analysis.crawl_notes))
        build_crawler_config({"version": 1, "sources": [source]})


if __name__ == "__main__":
    unittest.main()
