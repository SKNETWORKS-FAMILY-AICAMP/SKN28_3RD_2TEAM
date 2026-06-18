from __future__ import annotations

import unittest

from kaist_crawler.models import SourceConfig
from kaist_crawler.processor import add_document, source_scope_metadata


class ProcessorMetadataTests(unittest.TestCase):
    def test_source_scope_metadata_is_added_to_document_metadata(self) -> None:
        source = SourceConfig(
            id="kaist_chem",
            name="KAIST Department of Chemistry",
            base_url="https://chem.kaist.ac.kr/main/",
            adapter="static_html",
            institution="kaist",
            institution_name="KAIST",
            college="natural_sciences",
            college_name="KAIST College of Natural Sciences",
            dept="chem",
            dept_name="KAIST Department of Chemistry",
        )
        documents = []

        add_document(
            documents,
            site=source.id,
            source_url=source.base_url,
            title="Faculty",
            text="Professor profiles and research interests",
            raw_path=None,
            metadata=source_scope_metadata(source, {"document_type": "html"}),
        )

        metadata = documents[0].metadata
        self.assertEqual(metadata["institution"], "kaist")
        self.assertEqual(metadata["institution_name"], "KAIST")
        self.assertEqual(metadata["college"], "natural_sciences")
        self.assertEqual(metadata["college_name"], "KAIST College of Natural Sciences")
        self.assertEqual(metadata["dept"], "chem")
        self.assertEqual(metadata["dept_name"], "KAIST Department of Chemistry")


if __name__ == "__main__":
    unittest.main()
