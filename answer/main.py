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
    return f"data: {json.dumps(data)}\n\n"


@functions_framework.http
def answer(request):
    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = Response("", status=204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
        response.headers["Access-Control-Max-Age"] = "3600"
        return response

    req_json = request.get_json(silent=True)
    if not req_json or "query" not in req_json:
        response = Response(
            json.dumps({"error": "Missing query"}),
            status=400,
            content_type="application/json"
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    question = req_json["query"].strip()
    use_stream = req_json.get("stream", True)

    print(f"Query: {question} | stream={use_stream}")

    try:
        r = requests.post(RETRIEVAL_URL, json={"query": question}, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Retrieval failed: {e}")
        response = Response(
            json.dumps({"error": "Retrieval service failed"}),
            status=502,
            content_type="application/json"
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    chunks = [c for c in r.json() if c["score"] > 0.55][:8]
    print(f"Chunks after filter: {len(chunks)}")

    if not chunks:
        response = Response(
            json.dumps({"answer": "No relevant policy information found for your query.", "sources": []}),
            status=200,
            content_type="application/json"
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    sources = [c["source"] for c in chunks]
    prompt = build_prompt(question, chunks)
    gemini = get_model()

    if use_stream:
        def generate():
            try:
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

        response = Response(stream_with_context(generate()), status=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    else:
        response_obj = gemini.generate_content(prompt)
        answer_text = response_obj.text if response_obj.text else "No answer generated."
        response = Response(
            json.dumps({"answer": answer_text, "sources": sources}),
            status=200,
            content_type="application/json"
        )
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response