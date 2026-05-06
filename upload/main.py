import os

import firebase_admin
import functions_framework

from firebase_admin import auth
from flask import jsonify, request
from google.cloud import storage


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

BUCKET_NAME = os.environ.get(
    "BUCKET_NAME",
    "aria-incident-docs-elamin"
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


# ─────────────────────────────────────────────────────────────────────────────
# Firebase Admin Init
# ─────────────────────────────────────────────────────────────────────────────

firebase_admin.initialize_app(options={
    "projectId": "cs-cloud-elamin"
})


# ─────────────────────────────────────────────────────────────────────────────
# GCS Client
# ─────────────────────────────────────────────────────────────────────────────

storage_client = storage.Client()


# ─────────────────────────────────────────────────────────────────────────────
# Upload Function
# ─────────────────────────────────────────────────────────────────────────────

@functions_framework.http
def upload_document(request):

    # Handle CORS preflight
    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)

    # ─────────────────────────────────────────────────────────────────────────
    # Verify Firebase JWT
    # ─────────────────────────────────────────────────────────────────────────

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return (
            jsonify({"error": "Unauthorized"}),
            401,
            CORS_HEADERS
        )

    token = auth_header.split("Bearer ")[1]

    try:
        decoded_token = auth.verify_id_token(token)

        uid = decoded_token["uid"]

        print(f"Authenticated user: {uid}")

    except Exception as e:
        print(f"Token verification failed: {e}")

        return (
            jsonify({"error": "Invalid token"}),
            401,
            CORS_HEADERS
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Validate Upload
    # ─────────────────────────────────────────────────────────────────────────

    if "file" not in request.files:
        return (
            jsonify({"error": "No file provided"}),
            400,
            CORS_HEADERS
        )

    file = request.files["file"]

    if file.filename == "":
        return (
            jsonify({"error": "No file selected"}),
            400,
            CORS_HEADERS
        )

    if not file.filename.lower().endswith(".pdf"):
        return (
            jsonify({"error": "Only PDF files are allowed"}),
            400,
            CORS_HEADERS
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Upload To GCS
    # ─────────────────────────────────────────────────────────────────────────

    print(f"Uploading file: {file.filename}")

    bucket = storage_client.bucket(BUCKET_NAME)

    blob = bucket.blob(f"raw/{file.filename}")

    blob.upload_from_file(
        file,
        content_type="application/pdf"
    )


    

    gcs_path = f"gs://{BUCKET_NAME}/raw/{file.filename}"

    print(f"Uploaded to {gcs_path}")

    # ─────────────────────────────────────────────────────────────────────────
    # Success Response
    # ─────────────────────────────────────────────────────────────────────────

    return (
        jsonify({
            "message": f"Successfully uploaded {file.filename}",
            "path": gcs_path,
        }),
        200,
        CORS_HEADERS
    )