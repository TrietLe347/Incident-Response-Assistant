# Incident Response Assistant (RAG System)

This project implements a serverless Retrieval-Augmented Generation (RAG) system on Google Cloud to help campus housing staff retrieve policy-based incident guidance.

## Current Progress

- Event-driven ingestion pipeline using Cloud Storage + Cloud Run
- PDF text extraction and chunking
- Processed chunk storage layer implemented

## Architecture (Current)

raw documents → ingestion function → processed chunks

Next steps:
- Embedding generation using Vertex AI
- Vector Search index
- Query API and grounded response generation