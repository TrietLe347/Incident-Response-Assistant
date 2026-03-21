import functions_framework
from flask import request, jsonify
from google.cloud import storage
import vertexai
from vertexai.language_models import TextEmbeddingModel
import numpy as np
import json
import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = "us-central1"
BUCKET_NAME = "incident-assistant-docs-bucket"

storage_client = storage.Client()

emb_matrix = None
metadata = []

vertex_model = None

def load_embeddings():
    global emb_matrix, metadata

    print(f"Loading embeddings from bucket {BUCKET_NAME}")

    bucket = storage_client.bucket(BUCKET_NAME)

    vectors = []
    meta = []


    for blob in bucket.list_blobs(prefix="embeddings/"):
        if not blob.name.endswith(".json"):
            continue

        data = json.loads(blob.download_as_text())

        vectors.append(data["vector"])
        meta.append(data)

        print(f"Loaded embedding file: {blob.name}")

    if len(vectors) == 0:
        print("No embeddings found yet")
        emb_matrix = None
        metadata = []
        return

    emb_matrix = np.array(vectors, dtype=np.float32)
    metadata = meta
    
    print(f"Total embeddings loaded into memory: {len(metadata)}")


def get_vertex_model():
    global vertex_model

    if vertex_model is None:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        vertex_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    return vertex_model
    


load_embeddings()


def handle_search(request):

    if emb_matrix is None:
        return jsonify({"error": "No embeddings available yet"}), 400
    
    req_json = request.get_json(silent = True)

    if not req_json or "query" not in req_json:
        print("ERROR: Missing query in request")
        return jsonify({"error": "Missing query"}), 400

    query = req_json["query"]
    print(f"Incoming query: {query}")
    model = get_vertex_model()

    query_vec = model.get_embeddings([query])[0].values
    query_vec = np.array(query_vec, dtype=np.float32)

    print(f"Query embedding dimension: {len(query_vec)}")
    
    sims = emb_matrix @ query_vec
    sims = sims / (np.linalg.norm(emb_matrix,axis=1) * np.linalg.norm(query_vec))

    top_indices = np.argsort(sims)[-5:][::-1]

    print("Top similarity scores:")
    for idx in top_indices:
        print(float(sims[idx]), metadata[idx]["source_chunk"])

    results = []


    for idx in top_indices:
        results.append({
            "score":float(sims[idx]),
            "text": metadata[idx]["text"],
            "source":metadata[idx]["source_chunk"]
        })

    return jsonify(results)


def reload_embeddings(request):

    print("Manual reload triggered")

    load_embeddings()

    if emb_matrix is None:
        return jsonify({
            "status": "no_embeddings_found"
        }), 200

    return jsonify({
        "status": "reloaded",
        "embeddings_loaded": len(metadata)
    })

@functions_framework.http
def app(request):

    path = request.path

    if path == "/reload":
        print("Manual reload triggered")
        load_embeddings()

        if emb_matrix is None:
            return jsonify({"status": "no_embeddings_found"}), 200

        return jsonify({
            "status": "reloaded",
            "embeddings_loaded": len(metadata)
        })

    # default → search
    return handle_search(request)