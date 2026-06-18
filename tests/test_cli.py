from __future__ import annotations

import unittest
from unittest.mock import patch

from kaist_crawler.cli import main


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


if __name__ == "__main__":
    unittest.main()
