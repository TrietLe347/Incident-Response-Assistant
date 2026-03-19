import functions_framework
from google.cloud import storage
import pdfplumber
import io

CHUNK_SIZE = 500

@functions_framework.cloud_event
def ingest_document(cloud_event):
    data = cloud_event.data

    bucket_name = data["bucket"]
    file_name = data["name"]

    # Only process RAW PDFs
    if not file_name.startswith("raw/"):
        print("Skipping non-raw file")
        return

    if not file_name.endswith(".pdf"):
        print("Skipping non-PDF file")
        return

    print(f"Ingesting document: {file_name}")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    pdf_bytes = blob.download_as_bytes()

    text = ""

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    print(f"Extracted text length: {len(text)}")

    # Chunking
    chunks = []
    for i in range(0, len(text), CHUNK_SIZE):
        chunks.append(text[i:i+CHUNK_SIZE])

    print(f"Total chunks created: {len(chunks)}")

    # Save chunks to processed layer
    base_name = file_name.split("/")[-1].split(".pdf")[0]
    

    for idx, chunk in enumerate(chunks):
        chunk_blob = bucket.blob(f"processed/{base_name}_chunk_{idx}.txt")
        chunk_blob.upload_from_string(chunk)

    #print("Chunks uploaded to processed/ folder")

    print("UPLOADED FROM GITHUB YEHOO")