from rag import retriever


def test_search_similar_falls_back_to_full_text_when_embeddings_fail(monkeypatch):
    monkeypatch.setattr(
        retriever,
        "embed_query",
        lambda _query: (_ for _ in ()).throw(RuntimeError("missing Nomic key")),
    )
    monkeypatch.setattr(
        retriever,
        "search_by_keywords",
        lambda query, top_k=3: [
            {
                "content": f"resultado para {query}",
                "source": "iva.txt",
                "retrieval_method": "full_text",
            }
        ],
    )

    results = retriever.search_similar("vencimiento IVA")

    assert results[0]["source"] == "iva.txt"
    assert results[0]["retrieval_method"] == "full_text"
