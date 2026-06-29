import unittest
from unittest.mock import patch

from rag.embeddings import embed_text, embed_query, normalize_embedding


class NomicEmbeddingsTests(unittest.TestCase):
    def test_embed_text_returns_first_embedding_vector(self):
        with patch("rag.embeddings._nomic_embed_text", return_value={"embeddings": [[0.1, 0.2, 0.3]]}):
            result = embed_text("fragmento de prueba")

        self.assertEqual(result[:3], [0.1, 0.2, 0.3])
        self.assertEqual(len(result), 3072)

    def test_embed_query_uses_same_wrapper(self):
        with patch("rag.embeddings._nomic_embed_text", return_value={"embeddings": [[0.4, 0.5]]}):
            result = embed_query("consulta de prueba")

        self.assertEqual(result[:2], [0.4, 0.5])
        self.assertEqual(len(result), 3072)

    def test_normalize_embedding_adjusts_to_target_dimensions(self):
        result = normalize_embedding([0.1, 0.2, 0.3, 0.4], target_dim=5)

        self.assertEqual(result, [0.1, 0.2, 0.3, 0.4, 0.0])


if __name__ == "__main__":
    unittest.main()
