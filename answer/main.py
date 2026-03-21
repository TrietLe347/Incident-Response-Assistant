import functions_framework
from flask import request, jsonify
import requests
import vertexai
from vertexai.generative_models import GenerativeModel
import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = "us-central1"

RETRIEVAL_URL = "https://retrieval-service-571628338947.us-central1.run.app"

model = None


def get_model():
    global model

    if model is None:
        print("Initializing Vertex AI Gemini model")

        vertexai.init(
            project=PROJECT_ID,
            location=LOCATION
        )

        # ✅ THIS is the correct model name format for Vertex
        model = GenerativeModel("gemini-2.5-flash")

    return model #test


def build_prompt(question, chunks):

    context = "\n\n".join(
        [f"Source: {c['source']}\n{c['text']}" for c in chunks]
    )

    prompt = f"""
    You are an incident response assistant for university housing.

    Use ONLY the context below to answer the question.
    If the answer is not present, say you do not know.

    When possible:
    - Answer clearly
    - Use bullet points if helpful
    - Mention key procedures or rules

    Context:
    {context}

    Question:
    {question}

    Semantic hints:
    maintenance emergency urgent repair safety hazard housing facilities reporting procedure

    Final Answer:
    """

    return prompt


@functions_framework.http
def answer(request):

    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        return ("", 204, headers)

    headers = {
        "Access-Control-Allow-Origin": "*"
    }

    req_json = request.get_json(silent=True)

    if not req_json or "query" not in req_json:
        return (jsonify({"error": "Missing query"}), 400, headers)
    question = req_json["query"]

    print(f"User question: {question}")

    # ---- call retrieval service ----
    r = requests.post(
        RETRIEVAL_URL,
        json={"query": question},
        timeout=30
    )

    if r.status_code != 200:
        print("Retrieval failed")
        return jsonify({
            "error": "Retrieval service failed",
            "status": r.status_code
        }), 500

    chunks = r.json()

    print(f"Chunks received: {len(chunks)}")

    if not chunks:
        return jsonify({"answer": "No relevant information found."})

    prompt = build_prompt(question, chunks)

    gemini = get_model()

    print("Sending prompt to Gemini")

    response = gemini.generate_content(prompt)

    answer_text = response.text if response.text else "No answer generated."

    return (jsonify({
        "answer": answer_text,
        "sources": [c["source"] for c in chunks]
    }),200,headers)