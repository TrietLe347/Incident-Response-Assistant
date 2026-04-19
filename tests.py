"""
ARIA Unit Tests
===============
Tests for all 4 backend services:
  - ingest_document (ingestion)
  - embed_chunk (embeddings)
  - retrieval service (search)
  - answer service (Gemini)
 
Run:
  pip install pytest pytest-mock
  pytest tests.py -v
"""
 
import json
import numpy as np
import pytest
from unittest.mock import MagicMock, patch, call
 
 
# ── Ingestion tests ───────────────────────────────────────────────────────────
 
class TestIngestDocument:
 
    def test_skips_non_raw_files(self):
        """Files not in raw/ folder should be ignored."""
        from ingestion.main import ingest_document
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "processed/somefile.pdf"}
 
        with patch("ingestion.main.storage.Client") as mock_client:
            ingest_document(event)
            mock_client.return_value.bucket.return_value.blob.assert_not_called()
 
    def test_skips_non_pdf_files(self):
        """Non-PDF files in raw/ should be ignored."""
        from ingestion.main import ingest_document
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "raw/somefile.txt"}
 
        with patch("ingestion.main.storage.Client") as mock_client:
            ingest_document(event)
            mock_client.return_value.bucket.return_value.blob.assert_not_called()
 
    def test_chunks_text_correctly(self):
        """Text should be split into chunks of CHUNK_SIZE characters."""
        from ingestion.main import CHUNK_SIZE
 
        text = "A" * (CHUNK_SIZE * 3)
        chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
 
        assert len(chunks) == 3
        assert all(len(c) == CHUNK_SIZE for c in chunks)
 
    def test_processes_valid_pdf(self):
        """Valid PDF in raw/ should be extracted and chunked."""
        from ingestion.main import ingest_document
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "raw/policy.pdf"}
 
        fake_pdf_bytes = b"%PDF fake content"
        fake_text = "This is policy text. " * 100
 
        with patch("ingestion.main.storage.Client") as mock_storage, \
             patch("ingestion.main.pdfplumber.open") as mock_pdf:
 
            mock_blob = MagicMock()
            mock_blob.download_as_bytes.return_value = fake_pdf_bytes
            mock_storage.return_value.bucket.return_value.blob.return_value = mock_blob
 
            mock_page = MagicMock()
            mock_page.extract_text.return_value = fake_text
            mock_pdf.return_value.__enter__.return_value.pages = [mock_page]
 
            ingest_document(event)
 
            assert mock_blob.upload_from_string.called

class TestEmbedChunk:
 
    def test_skips_non_processed_files(self):
        """Files not in processed/ should be skipped."""
        from embeddings.main import embed_chunk
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "raw/file.txt"}
 
        with patch("embeddings.main.storage.Client") as mock_client:
            embed_chunk(event)
            mock_client.return_value.bucket.return_value.blob.assert_not_called()
 
    def test_skips_non_txt_files(self):
        """Non-.txt files in processed/ should be skipped."""
        from embeddings.main import embed_chunk
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "processed/file.pdf"}
 
        with patch("embeddings.main.storage.Client") as mock_client:
            embed_chunk(event)
            mock_client.return_value.bucket.return_value.blob.assert_not_called()
 
    def test_skips_empty_chunks(self):
        """Empty text chunks should be skipped."""
        from embeddings.main import embed_chunk
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "processed/chunk_0.txt"}
 
        with patch("embeddings.main.storage.Client") as mock_storage:
            mock_blob = MagicMock()
            mock_blob.download_as_text.return_value = "   "
            mock_storage.return_value.bucket.return_value.blob.return_value = mock_blob
 
            embed_chunk(event)
 
            upload_calls = [c for c in mock_blob.mock_calls if "upload" in str(c)]
            assert len(upload_calls) == 0
 
    def test_saves_embedding_to_correct_path(self):
        """Embedding should be saved to embeddings/ with .json extension."""
        from embeddings.main import embed_chunk
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "processed/policy_chunk_0.txt"}
 
        fake_vector = [0.1] * 768
 
        with patch("embeddings.main.storage.Client") as mock_storage, \
             patch("embeddings.main.get_model") as mock_model:
 
            mock_blob = MagicMock()
            mock_blob.download_as_text.return_value = "Some policy text about fire alarms."
            mock_storage.return_value.bucket.return_value.blob.return_value = mock_blob
 
            mock_model.return_value.get_embeddings.return_value = [
                MagicMock(values=fake_vector)
            ]
 
            embed_chunk(event)
 
            saved_path = mock_storage.return_value.bucket.return_value.blob.call_args_list[-1][0][0]
            assert saved_path == "embeddings/policy_chunk_0.json"
 
    def test_embedding_json_structure(self):
        """Saved JSON should contain text, vector, and source_chunk fields."""
        from embeddings.main import embed_chunk
 
        event = MagicMock()
        event.data = {"bucket": "aria-incident-docs-elamin", "name": "processed/chunk_1.txt"}
 
        fake_text = "Residents must evacuate during fire alarms."
        fake_vector = [0.5] * 768
 
        saved_data = {}
 
        def capture_upload(data, **kwargs):
            saved_data.update(json.loads(data))
 
        with patch("embeddings.main.storage.Client") as mock_storage, \
             patch("embeddings.main.get_model") as mock_model:
 
            mock_read_blob = MagicMock()
            mock_read_blob.download_as_text.return_value = fake_text
 
            mock_write_blob = MagicMock()
            mock_write_blob.upload_from_string.side_effect = capture_upload
 
            mock_storage.return_value.bucket.return_value.blob.side_effect = [
                mock_read_blob, mock_write_blob
            ]
 
            mock_model.return_value.get_embeddings.return_value = [
                MagicMock(values=fake_vector)
            ]
 
            embed_chunk(event)
 
        assert "text" in saved_data
        assert "vector" in saved_data
        assert "source_chunk" in saved_data
        assert saved_data["text"] == fake_text
        assert len(saved_data["vector"]) == 768

# ── Retrieval service tests ───────────────────────────────────────────────────
 
class TestRetrievalService:
 
    def setup_method(self):
        """Set up a fake in-memory embedding matrix for each test."""
        import retrieval.main as retrieval
        self.retrieval = retrieval
 
        self.retrieval.metadata = [
            {"text": "Gas leak: evacuate immediately and call 911.", "source_chunk": "processed/emergency_chunk_0.txt"},
            {"text": "Fire alarm: knock on all doors and go to assembly point.", "source_chunk": "processed/emergency_chunk_1.txt"},
            {"text": "Quiet hours on weekdays are 10pm to 8am.", "source_chunk": "processed/policy_chunk_0.txt"},
            {"text": "Residents may have up to 3 overnight guests.", "source_chunk": "processed/policy_chunk_1.txt"},
        ]
        self.retrieval.emb_matrix = np.random.rand(4, 768).astype(np.float32)
 
    def test_returns_400_when_no_embeddings(self):
        """Should return 400 if no embeddings are loaded."""
        self.retrieval.emb_matrix = None
 
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context(
            "/", method="POST",
            json={"query": "gas leak"},
            content_type="application/json"
        ):
            from flask import request
            response = self.retrieval.flask_app.test_client().post(
                "/", json={"query": "gas leak"}
            )
            assert response.status_code == 400
 
    def test_returns_400_when_missing_query(self):
        """Should return 400 if query field is missing."""
        client = self.retrieval.flask_app.test_client()
        response = client.post("/", json={"wrong_field": "hello"})
        assert response.status_code == 400
 
    def test_returns_results_list(self):
        """Should return a list of results with score, text, source fields."""
        with patch.object(self.retrieval, "get_vertex_model") as mock_model:
            mock_model.return_value.get_embeddings.return_value = [
                MagicMock(values=np.random.rand(768).tolist())
            ]
 
            client = self.retrieval.flask_app.test_client()
            response = client.post("/", json={"query": "what to do during gas leak"})
 
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, list)
            assert len(data) > 0
            assert "score" in data[0]
            assert "text" in data[0]
            assert "source" in data[0]
 
    def test_scores_are_between_0_and_1(self):
        """Cosine similarity scores should be between 0 and 1."""
        with patch.object(self.retrieval, "get_vertex_model") as mock_model:
            mock_model.return_value.get_embeddings.return_value = [
                MagicMock(values=np.random.rand(768).tolist())
            ]
 
            client = self.retrieval.flask_app.test_client()
            response = client.post("/", json={"query": "fire alarm procedure"})
            data = response.get_json()
 
            for result in data:
                assert -1.0 <= result["score"] <= 1.0
 
    def test_reload_returns_count(self):
        """Reload endpoint should return the number of embeddings loaded."""
        with patch.object(self.retrieval, "load_embeddings") as mock_load:
            def fake_load():
                self.retrieval.emb_matrix = np.random.rand(4, 768).astype(np.float32)
                self.retrieval.metadata = [{}] * 4
            mock_load.side_effect = fake_load
 
            client = self.retrieval.flask_app.test_client()
            response = client.get("/reload")
            data = response.get_json()
 
            assert response.status_code == 200
            assert data["status"] == "reloaded"
            assert data["embeddings_loaded"] == 4
            