import functions_framework
from google.cloud import storage
import pdfplumber
import io
from google.cloud import firestore

# The size of each text chunk in characters
# 500 characters balances context quality vs search precision
CHUNK_SIZE = 500


def get_db():
    return firestore.Client()


def log_document(file_name, num_chunks):
    db = get_db()

    try:
        
        doc_ref = db.collection("documents").add({
            "file_name":file_name,
            "upload_timestamp":firestore.SERVER_TIMESTAMP,
            "num_chunks":num_chunks
        })

        document_id = doc_ref[1].id

        print(f"Document logged with ID: {document_id}")

    except Exception as e:
        print("Firestore document logging error:",e)

@functions_framework.cloud_event
def ingest_document(cloud_event):
    """
    Triggered by Eventarc when a new file is uploaded to the GCS bucket.
    Extracts text from PDF files and splits them into chunks for embedding.
    """
    data = cloud_event.data

    # Get the bucket name and file path from the event
    bucket_name = data["bucket"]
    file_name = data["name"]

    # Only process files in the raw/ folder — ignore processed/ and embeddings/
    if not file_name.startswith("raw/"):
        print("Skipping non-raw file")
        return

    # Only process PDF files — ignore any other file types
    if not file_name.endswith(".pdf"):
        print("Skipping non-PDF file")
        return

    print(f"Ingesting document: {file_name}")

    # Connect to Cloud Storage and download the PDF as bytes
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    pdf_bytes = blob.download_as_bytes()

    # Extract text from every page of the PDF using pdfplumber
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    print(f"Extracted text length: {len(text)}")

    # Split the full text into chunks of CHUNK_SIZE characters
    # Each chunk will become a separate embedding in the next pipeline step
    chunks = []
    for i in range(0, len(text), CHUNK_SIZE):
        chunks.append(text[i:i+CHUNK_SIZE])

    print(f"Total chunks created: {len(chunks)}")


    

    # Extract the base filename without the path and .pdf extension
    # e.g. "raw/housing_emergency_procedures.pdf" -> "housing_emergency_procedures"
    base_name = file_name.split("/")[-1].split(".pdf")[0]
    clean_name = file_name.split("/")[-1]

    # Save each chunk as a separate .txt file in the processed/ folder
    # Eventarc will detect each new file and trigger embed_chunk automatically
    for idx, chunk in enumerate(chunks):
        chunk_blob = bucket.blob(f"processed/{base_name}_chunk_{idx}.txt")
        chunk_blob.upload_from_string(chunk)

    log_document(clean_name,len(chunks))

    