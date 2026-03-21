import functions_framework
from google.cloud import storage
import vertexai
from vertexai.language_models import TextEmbeddingModel
import json
import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = "us-central1"


model = None


def get_model():
    global model
    if model is None:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    return model








@functions_framework.cloud_event
def embed_chunk(cloud_event):
    data = cloud_event.data

    bucket_name = data["bucket"]
    file_name = data["name"]


    #only react to processed chunks
    #processed file should be in the processed folder

    if not file_name.startswith("processed/"):
        print("Skipping non-processed file")
        return
    

    #processed file should be a .txt file
    if not file_name.endswith(".txt"):
        print("Skipping non-txt file")
        return
    
    print(f"Embedding chunk: {file_name}")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)


    text = blob.download_as_text()

    embedding_model = get_model()

    embedding = model.get_embeddings([text])[0].values

    



    embedding_data ={
        "text" : text,
        "vector" : embedding,
        "source_chunk" : file_name
    }    

    out_name = file_name.replace("processed/", "embeddings/").replace(".txt",".json")
    
    out_blob = bucket.blob(out_name)
    out_blob.upload_from_string(json.dumps(embedding_data))
    
    print(f"Saved embedding -> {out_name}")