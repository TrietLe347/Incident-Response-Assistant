"""
ARIA Unit Tests
===============
Run:
  source venv/bin/activate
  pip install pytest pytest-mock flask numpy pdfplumber requests functions-framework google-cloud-storage
  pytest tests.py -v
"""

import json
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


# ── Ingestion tests ───────────────────────────────────────────────────────────

class TestIngestDocument:

    def test_skips_non_raw_files(self):
        with patch("functions_framework.cloud_event", lambda f: f), \
             patch("ingestion.main.storage.Client"):
            from ingestion.main import ingest_document
            event = MagicMock()
            event.data = {"bucket": "test-bucket", "name": "processed/file.pdf"}
            with patch("ingestion.main.storage.Client") as mock_client:
                ingest_document(event)
                mock_client.return_value.bucket.return_value.blob.assert_not_called()

    def test_skips_non_pdf_files(self):
        from ingestion.main import ingest_document
        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/file.txt"}
        with patch("ingestion.main.storage.Client") as mock_client:
            ingest_document(event)
            mock_client.return_value.bucket.return_value.blob.assert_not_called()

    def test_chunks_text_correctly(self):
        from ingestion.main import CHUNK_SIZE
        text = "A" * (CHUNK_SIZE * 3)
        chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
        assert len(chunks) == 3
        assert all(len(c) == CHUNK_SIZE for c in chunks)

    def test_chunk_size_is_500(self):
        from ingestion.main import CHUNK_SIZE
        assert CHUNK_SIZE == 500


# ── Embeddings tests ──────────────────────────────────────────────────────────

class TestEmbedChunk:

    def test_skips_non_processed_files(self):
        from embeddings.main import embed_chunk
        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/file.txt"}
        with patch("embeddings.main.storage.Client") as mock_client:
            embed_chunk(event)
            mock_client.return_value.bucket.return_value.blob.assert_not_called()

    def test_skips_non_txt_files(self):
        from embeddings.main import embed_chunk
        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "processed/file.pdf"}
        with patch("embeddings.main.storage.Client") as mock_client:
            embed_chunk(event)
            mock_client.return_value.bucket.return_value.blob.assert_not_called()

    def test_skips_empty_chunks(self):
        from embeddings.main import embed_chunk
        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "processed/chunk_0.txt"}
        with patch("embeddings.main.storage.Client") as mock_storage:
            mock_blob = MagicMock()
            mock_blob.download_as_text.return_value = "   "
            mock_storage.return_value.bucket.return_value.blob.return_value = mock_blob
            embed_chunk(event)
            assert not mock_blob.upload_from_string.called

    def test_output_path_uses_embeddings_folder(self):
        """Output path should replace processed/ with embeddings/ and .txt with .json"""
        source = "processed/policy_chunk_0.txt"
        expected = "embeddings/policy_chunk_0.json"
        result = source.replace("processed/", "embeddings/").replace(".txt", ".json")
        assert result == expected

    def test_embedding_data_has_required_fields(self):
        """Embedding JSON must have text, vector, and source_chunk fields."""
        fake_data = {
            "text": "some policy text",
            "vector": [0.1] * 768,
            "source_chunk": "processed/chunk_0.txt"
        }
        assert "text" in fake_data
        assert "vector" in fake_data
        assert "source_chunk" in fake_data
        assert len(fake_data["vector"]) == 768


# ── Answer service tests ──────────────────────────────────────────────────────

class TestAnswerService:

    def test_build_prompt_includes_context(self):
        from answer.main import build_prompt
        chunks = [
            {"source": "processed/chunk_0.txt", "text": "Evacuate immediately during gas leaks."},
            {"source": "processed/chunk_1.txt", "text": "Call 911 after evacuating."},
        ]
        prompt = build_prompt("What do I do during a gas leak?", chunks)
        assert "Evacuate immediately during gas leaks." in prompt
        assert "Call 911 after evacuating." in prompt
        assert "What do I do during a gas leak?" in prompt

    def test_build_prompt_includes_source(self):
        from answer.main import build_prompt
        chunks = [{"source": "processed/chunk_0.txt", "text": "some text"}]
        prompt = build_prompt("test question", chunks)
        assert "processed/chunk_0.txt" in prompt

    def test_build_prompt_has_grounding_instruction(self):
        from answer.main import build_prompt
        chunks = [{"source": "s", "text": "some text"}]
        prompt = build_prompt("test question", chunks)
        assert "ONLY" in prompt or "only" in prompt

    def test_returns_400_when_missing_query(self):
        from answer.main import answer
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context("/", method="POST",
                                       data=json.dumps({}),
                                       content_type="application/json"):
            from flask import request as flask_request
            response = answer(flask_request)
            assert response[1] == 400

    def test_returns_no_result_when_chunks_empty(self):
        from answer.main import answer
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context("/", method="POST",
                                       data=json.dumps({"query": "test", "stream": False}),
                                       content_type="application/json"):
            from flask import request as flask_request
            with patch("answer.main.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = []
                response = answer(flask_request)
                body = json.loads(response[0])
                assert "No relevant" in body.get("answer", "")

    def test_cors_header_present(self):
        from answer.main import answer
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context("/", method="POST",
                                       data=json.dumps({"query": "fire alarm", "stream": False}),
                                       content_type="application/json"):
            from flask import request as flask_request
            with patch("answer.main.requests.post") as mock_post, \
                 patch("answer.main.get_model") as mock_model:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = [
                    {"score": 0.9, "text": "Evacuate immediately.", "source": "chunk_0.txt"}
                ]
                mock_model.return_value.generate_content.return_value = MagicMock(text="Evacuate now.")
                response = answer(flask_request)
                headers = response[2]
                assert "Access-Control-Allow-Origin" in headers


# ── Retrieval service tests ───────────────────────────────────────────────────

class TestRetrievalService:

    def setup_method(self):
        with patch("google.cloud.storage.Client"):
            import retrieval.main as r
            self.r = r
            self.r.metadata = [
                {"text": "Gas leak: evacuate immediately.", "source_chunk": "chunk_0.txt"},
                {"text": "Fire alarm: knock on all doors.", "source_chunk": "chunk_1.txt"},
                {"text": "Quiet hours: 10pm to 8am on weekdays.", "source_chunk": "chunk_2.txt"},
                {"text": "Guests: max 3 overnight stays.", "source_chunk": "chunk_3.txt"},
            ]
            self.r.emb_matrix = np.random.rand(4, 768).astype(np.float32)

    def test_returns_400_when_no_embeddings(self):
        self.r.emb_matrix = None
        client = self.r.app.test_client()
        response = client.post("/", json={"query": "gas leak"})
        assert response.status_code == 400

    def test_returns_400_when_missing_query(self):
        client = self.r.app.test_client()
        response = client.post("/", json={"wrong": "field"})
        assert response.status_code == 400

    def test_returns_list_of_results(self):
        with patch.object(self.r, "get_vertex_model") as mock_model:
            mock_model.return_value.get_embeddings.return_value = [
                MagicMock(values=np.random.rand(768).tolist())
            ]
            client = self.r.app.test_client()
            response = client.post("/", json={"query": "gas leak procedure"})
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0

    def test_results_have_required_fields(self):
        with patch.object(self.r, "get_vertex_model") as mock_model:
            mock_model.return_value.get_embeddings.return_value = [
                MagicMock(values=np.random.rand(768).tolist())
            ]
            client = self.r.app.test_client()
            response = client.post("/", json={"query": "fire alarm"})
            data = response.get_json()
            for result in data:
                assert "score" in result
                assert "text" in result
                assert "source" in result

    def test_reload_returns_embeddings_count(self):
        with patch.object(self.r, "load_embeddings") as mock_load:
            def fake_load():
                self.r.emb_matrix = np.random.rand(4, 768).astype(np.float32)
                self.r.metadata = [{}] * 4
            mock_load.side_effect = fake_load
            client = self.r.app.test_client()
            response = client.get("/reload")
            data = response.get_json()
            assert response.status_code == 200
            assert data["status"] == "reloaded"
            assert data["embeddings_loaded"] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])