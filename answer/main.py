import functions_framework
from flask import request, Response, stream_with_context
import requests
import vertexai
from vertexai.generative_models import GenerativeModel
import json
import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = "us-central1"
RETRIEVAL_URL = "https://retrieval-service-430373032909.us-central1.run.app"

_model = None

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept",
}


def get_model():
    global _model
    if _model is None:
        print("Initializing Vertex AI Gemini model")
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        _model = GenerativeModel("gemini-2.5-flash")
    return _model


def build_prompt(question, chunks):
    context = "\n\n".join(
        [f"Source: {c['source']}\n{c['text']}" for c in chunks]
    )
    return f"""You are an incident response assistant for university housing.

Use ONLY the context below to answer the question.
If the answer is not present, say you do not know.

When possible:
- Answer clearly and concisely
- Use bullet points for multi-step procedures
- Mention relevant policy names or section references
- Keep your response focused on actionable guidance

Context:
{context}

Question:
{question}

Answer:"""


def sse_event(data: dict) -> str:
    """Format a dict as a Server-Sent Event."""
    return f"data: {json.dumps(data)}\n\n"


@functions_framework.http
def answer(request):
    # Preflight
    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)

    req_json = request.get_json(silent=True)
    if not req_json or "query" not in req_json:
        return (json.dumps({"error": "Missing query"}), 400, {**CORS_HEADERS, "Content-Type": "application/json"})

    question = req_json["query"].strip()
    use_stream = req_json.get("stream", True)

    print(f"Query: {question} | stream={use_stream}")

    # Retrieve relevant chunks
    try:
        r = requests.post(RETRIEVAL_URL, json={"query": question}, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Retrieval failed: {e}")
        return (json.dumps({"error": "Retrieval service failed"}), 502, {**CORS_HEADERS, "Content-Type": "application/json"})

    chunks = [c for c in r.json() if c["score"] > 0.55][:8]
    print(f"Chunks after filter: {len(chunks)}")

    if not chunks:
        payload = {"answer": "No relevant policy information found for your query.", "sources": []}
        return (json.dumps(payload), 200, {**CORS_HEADERS, "Content-Type": "application/json"})

    sources = [c["source"] for c in chunks]
    prompt = build_prompt(question, chunks)
    gemini = get_model()

    if use_stream:
        def generate():
            try:
                # Send sources first so UI can show them immediately
                yield sse_event({"type": "sources", "sources": sources})

                full_text = ""
                for chunk in gemini.generate_content(prompt, stream=True):
                    if chunk.text:
                        full_text += chunk.text
                        yield sse_event({"type": "chunk", "text": chunk.text})

                yield sse_event({"type": "done", "answer": full_text, "sources": sources})
            except Exception as e:
                print(f"Streaming error: {e}")
                yield sse_event({"type": "error", "message": str(e)})

        stream_headers = {
            **CORS_HEADERS,
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
        return Response(stream_with_context(generate()), headers=stream_headers)

    else:
        # Non-streaming fallback
        response = gemini.generate_content(prompt)
        answer_text = response.text if response.text else "No answer generated."
        payload = {"answer": answer_text, "sources": sources}
        return (json.dumps(payload), 200, {**CORS_HEADERS, "Content-Type": "application/json"})