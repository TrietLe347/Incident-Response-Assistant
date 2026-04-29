# Incident Response Assistant (RAG System)

This project implements a serverless Retrieval-Augmented Generation (RAG) system on Google Cloud to help campus housing staff quickly retrieve policy-based incident guidance.

---

## Current Progress

- Event-driven ingestion pipeline using Cloud Storage + Cloud Functions  
- PDF text extraction and chunking (500 character chunks)  
- Processed chunks stored in Cloud Storage  
- Embeddings generated for each chunk  
- Retrieval service using cosine similarity (NumPy, embeddings stored in GCS)  
- Answer service using Vertex AI (Gemini) for response generation  
- Streaming responses (SSE) for real-time answers  
- Firestore database integration:
  - `queries` collection for logging user queries and responses  
  - `documents` collection for storing uploaded document metadata  
- CI/CD pipeline using GitHub Actions (testing + deployment)  
- Unit tests with mocks for:
  - ingestion  
  - embeddings  
  - retrieval  
  - answer service  
  - Firestore logging  
- ~90%+ test coverage across the backend  

---

## Architecture (Current)
```
raw documents (GCS)
↓
ingestion function (PDF → chunks)
↓
processed chunks (GCS)
↓
embedding function (Vertex AI)
↓
embeddings stored (GCS)
↓
retrieval service (Cloud Run, NumPy cosine similarity)
↓
answer service (Cloud Function + Gemini)
↓
frontend (Firebase Hosting)
↓
Firestore (query + document logging)

```
---

## Notes / Design Choices

- Uses a **serverless architecture** (Cloud Functions + Cloud Run) for scalability and simplicity  
- Uses **NumPy cosine similarity instead of Vertex AI Vector Search** since dataset is small  
- Firestore is a **NoSQL database**, so no foreign keys (we keep it simple)  
- Queries and responses are logged for **debugging and performance tracking**

---

## Next Steps

- Link queries to documents (store document IDs used during retrieval)  
- Improve retrieval ranking / scoring  
- Add admin upload UI for documents  
- Add analytics/dashboard for query logs  
- Improve frontend UX

## Authors
- Minh Triet Le
- Tariq Elamin
