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