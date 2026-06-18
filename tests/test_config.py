from __future__ import annotations

import unittest

from kaist_crawler.config import build_crawler_config


class ConfigTests(unittest.TestCase):
    def test_load_crawler_config_merges_defaults_and_runtime_settings(self) -> None:
        config = build_crawler_config(
            {
                "version": 1,
                "defaults": {
                    "request_timeout_seconds": 12,
                    "polite_delay_seconds": 0.5,
                    "raw": {"file_policy": {"max_file_size_mb": 10}},
                    "processing": {"filter_policy": {"min_text_chars": 50}},
                },
                "sources": [
                    {
                        "id": "sample",
                        "name": "Sample Graduate School",
                        "base_url": "https://example.edu/",
                        "adapter": "static_html",
                        "routes": ["/"],
                        "raw": {"follow_html_links": False},
                    }
                ],
            }
        )

        self.assertEqual(config.request_timeout_seconds, 12)
        self.assertEqual(config.polite_delay_seconds, 0.5)
        self.assertEqual(len(config.sources), 1)
        self.assertEqual(config.sources[0].raw_options["file_policy"]["max_file_size_mb"], 10)
        self.assertFalse(config.sources[0].raw_options["follow_html_links"])
        self.assertEqual(config.sources[0].processing_options["filter_policy"]["min_text_chars"], 50)

    def test_unknown_selected_source_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown source id"):
            build_crawler_config(
                {
                    "version": 1,
                    "sources": [
                        {
                            "id": "sample",
                            "name": "Sample Graduate School",
                            "base_url": "https://example.edu/",
                            "adapter": "static_html",
                        }
                    ],
                },
                only={"missing"},
            )

    def test_invalid_source_key_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown key"):
            build_crawler_config(
                {
                    "version": 1,
                    "sources": [
                        {
                            "id": "sample",
                            "name": "Sample Graduate School",
                            "base_url": "https://example.edu/",
                            "adapter": "static_html",
                            "rouets": ["/"],
                        }
                    ],
                }
            )

    def test_invalid_adapter_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported adapter"):
            build_crawler_config(
                {
                    "version": 1,
                    "sources": [
                        {
                            "id": "sample",
                            "name": "Sample Graduate School",
                            "base_url": "https://example.edu/",
                            "adapter": "unknown_adapter",
                        }
                    ],
                }
            )

    def test_source_scope_metadata_is_loaded(self) -> None:
        config = build_crawler_config(
            {
                "version": 1,
                "sources": [
                    {
                        "id": "sample",
                        "name": "Sample Graduate School",
                        "base_url": "https://example.edu/",
                        "adapter": "static_html",
                        "institution": "kaist",
                        "institution_name": "KAIST",
                        "college": "natural_sciences",
                        "college_name": "KAIST College of Natural Sciences",
                        "dept": "physics",
                        "dept_name": "KAIST Department of Physics",
                    }
                ],
            }
        )

        source = config.sources[0]
        self.assertEqual(source.institution, "kaist")
        self.assertEqual(source.institution_name, "KAIST")
        self.assertEqual(source.college, "natural_sciences")
        self.assertEqual(source.college_name, "KAIST College of Natural Sciences")
        self.assertEqual(source.dept, "physics")
        self.assertEqual(source.dept_name, "KAIST Department of Physics")


if __name__ == "__main__":
    unittest.main()
