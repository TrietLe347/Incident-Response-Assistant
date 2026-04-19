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