"""Tests for context/retrieval.py - Document retriever."""

import pytest
from sharp.harness.context.retrieval import DocumentRetriever, RetrievedDocument


class TestRetrievedDocument:
    def test_token_count(self):
        doc = RetrievedDocument(name="test", content="Hello world test content")
        assert doc.token_count > 0


class TestDocumentRetriever:
    @pytest.fixture
    def retriever(self):
        return DocumentRetriever(max_tokens=4000)

    def test_add_document(self, retriever):
        retriever.add_document("doc1", "Content about Python programming", score=0.9)
        assert len(retriever._documents) == 1

    def test_add_documents(self, retriever):
        docs = [
            {"name": "d1", "content": "Content 1", "score": 0.8},
            {"name": "d2", "content": "Content 2", "score": 0.6},
        ]
        retriever.add_documents(docs)
        assert len(retriever._documents) == 2

    def test_retrieve_empty(self, retriever):
        results = retriever.retrieve("query")
        assert results == []

    def test_retrieve_by_relevance(self, retriever):
        retriever.add_document("python", "Python is a programming language", score=0.9)
        retriever.add_document("java", "Java is another language", score=0.5)
        retriever.add_document("cooking", "How to cook pasta", score=0.1)

        results = retriever.retrieve("programming language", top_k=2)
        assert len(results) <= 2
        assert results[0].name == "python"

    def test_retrieve_keyword_boost(self, retriever):
        retriever.add_document("doc1", "Python programming tutorial", score=0.5)
        retriever.add_document("doc2", "Java programming tutorial", score=0.5)

        results = retriever.retrieve(
            "Python tutorial",
            keywords=["python"],
        )
        assert len(results) >= 1
        assert results[0].name == "doc1"

    def test_retrieve_top_k_limit(self, retriever):
        for i in range(10):
            retriever.add_document(f"doc{i}", f"Content {i}", score=1.0 - i * 0.1)

        results = retriever.retrieve("content", top_k=3)
        assert len(results) == 3

    def test_retrieve_token_budget(self):
        retriever = DocumentRetriever(max_tokens=50)
        retriever.add_document("long", "x " * 100, score=1.0)  # ~100 tokens
        retriever.add_document("short", "short content", score=0.9)

        results = retriever.retrieve("content", top_k=10)
        assert len(results) <= 2
        total = sum(d.token_count for d in results)
        assert total <= 50 or len(results) == 1

    def test_clear(self, retriever):
        retriever.add_document("d1", "content", score=1.0)
        retriever.clear()
        assert len(retriever._documents) == 0
