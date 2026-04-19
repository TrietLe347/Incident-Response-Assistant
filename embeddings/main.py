import functions_framework
from google.cloud import storage
import vertexai
from vertexai.language_models import TextEmbeddingModel
import json
import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = "us-central1"

_model = None


def get_model():
    global _model
    if _model is None:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        _model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return _model


@functions_framework.cloud_event
def embed_chunk(cloud_event):
    data = cloud_event.data

    bucket_name = data["bucket"]
    file_name = data["name"]

    if not file_name.startswith("processed/"):
        print(f"Skipping non-processed file: {file_name}")
        return

    if not file_name.endswith(".txt"):
        print(f"Skipping non-txt file: {file_name}")
        return

    print(f"Embedding chunk: {file_name}")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    text = blob.download_as_text()

    if not text.strip():
        print(f"Skipping empty chunk: {file_name}")
        return

    model = get_model()
    embedding = model.get_embeddings([text])[0].values

    embedding_data = {
        "text": text,
        "vector": embedding,
        "source_chunk": file_name,
    }

    out_name = (
        file_name
        .replace("processed/", "embeddings/")
        .replace(".txt", ".json")
    )

    out_blob = bucket.blob(out_name)
    out_blob.upload_from_string(json.dumps(embedding_data), content_type="application/json")

    print(f"Saved embedding -> {out_name}")