import functions_framework
from flask import request, jsonify
from google.cloud import storage
import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "aria-incident-docs-elamin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "aria-admin-2026")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Admin-Password",
}

storage_client = storage.Client()


@functions_framework.http
def upload_document(request):
    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)

    # Check password header
    password = request.headers.get("X-Admin-Password", "")
    if password != ADMIN_PASSWORD:
        return (jsonify({"error": "Unauthorized"}), 401, CORS_HEADERS)

    # Check file was provided
    if "file" not in request.files:
        return (jsonify({"error": "No file provided"}), 400, CORS_HEADERS)

    file = request.files["file"]

    if not file.filename.endswith(".pdf"):
        return (jsonify({"error": "Only PDF files are allowed"}), 400, CORS_HEADERS)

    if file.filename == "":
        return (jsonify({"error": "No file selected"}), 400, CORS_HEADERS)

    print(f"Uploading file: {file.filename}")

    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"raw/{file.filename}")
    blob.upload_from_file(file, content_type="application/pdf")

    print(f"Uploaded to gs://{BUCKET_NAME}/raw/{file.filename}")

    return (jsonify({
        "message": f"Successfully uploaded {file.filename}",
        "path": f"gs://{BUCKET_NAME}/raw/{file.filename}",
    }), 200, CORS_HEADERS)