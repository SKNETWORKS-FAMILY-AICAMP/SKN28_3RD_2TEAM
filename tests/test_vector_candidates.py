from __future__ import annotations

import unittest

from kaist_crawler.models import Chunk
from kaist_crawler.pipeline import vector_candidate_chunks


class VectorCandidateTests(unittest.TestCase):
    def test_uses_only_vector_candidates_by_default(self) -> None:
        chunks = [
            chunk("keep", True),
            chunk("drop", False),
        ]

        selected = vector_candidate_chunks(chunks)

        self.assertEqual([item.chunk_id for item in selected], ["keep"])

    def test_can_include_non_candidates(self) -> None:
        chunks = [
            chunk("keep", True),
            chunk("drop", False),
        ]

        selected = vector_candidate_chunks(chunks, include_non_candidates=True)

        self.assertEqual([item.chunk_id for item in selected], ["keep", "drop"])

    def test_missing_candidate_metadata_is_kept_for_backwards_compatibility(self) -> None:
        chunks = [
            Chunk(
                chunk_id="legacy",
                doc_id="doc:legacy",
                site="sample",
                source_url="https://example.edu/legacy",
                text="legacy chunk",
                chunk_index=0,
                metadata={},
            )
        ]

        selected = vector_candidate_chunks(chunks)

        self.assertEqual([item.chunk_id for item in selected], ["legacy"])


def chunk(chunk_id: str, candidate: bool) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=f"doc:{chunk_id}",
        site="sample",
        source_url=f"https://example.edu/{chunk_id}",
        text=f"{chunk_id} graduate admission text",
        chunk_index=0,
        metadata={"vector_candidate": candidate, "content_type": "admission"},
    )


if __name__ == "__main__":
    unittest.main()
