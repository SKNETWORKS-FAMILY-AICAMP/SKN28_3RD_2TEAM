from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

from kaist_crawler.cli import main
from kaist_crawler.pipeline import RawCrawlResult


class CliTests(unittest.TestCase):
    def test_process_passes_llm_relevance_options(self) -> None:
        captured = {}

        def fake_process_raw_data(**kwargs):
            captured.update(kwargs)
            return [], [], [], []

        with patch("kaist_crawler.cli.process_raw_data", side_effect=fake_process_raw_data):
            exit_code = main(
                [
                    "process",
                    "--config",
                    "configs/kaist_sources.yml",
                    "--output",
                    "data/kaist",
                    "--use-llm-relevance",
                    "--relevance-model",
                    "test-model",
                    "--max-llm-relevance",
                    "3",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(captured["use_llm_relevance"])
        self.assertEqual(captured["relevance_model"], "test-model")
        self.assertEqual(captured["max_llm_relevance"], 3)

    def test_raw_prints_written_reused_and_errors(self) -> None:
        result = RawCrawlResult(files_written=2, files_reused=3, errors=[])

        with patch("kaist_crawler.cli.run_raw_crawl", return_value=result), patch(
            "sys.stdout", new_callable=StringIO
        ) as stdout:
            exit_code = main(
                [
                    "raw",
                    "--config",
                    "configs/kaist_sources.yml",
                    "--output",
                    "data/kaist",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("raw_files_written=2", stdout.getvalue())
        self.assertIn("raw_files_reused=3", stdout.getvalue())
        self.assertIn("errors=0", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
