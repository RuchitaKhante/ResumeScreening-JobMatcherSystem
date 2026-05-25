from fastapi import FastAPI, UploadFile, File
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import PyPDF2
import docx
from io import BytesIO

app = FastAPI()

# Load AI Model
model = SentenceTransformer('all-MiniLM-L6-v2')


# Function to extract text from PDF
def extract_pdf_text(file):

    text = ""

    pdf_reader = PyPDF2.PdfReader(file)

    for page in pdf_reader.pages:
        extracted = page.extract_text()

        if extracted:
            text += extracted

    return text


# Function to extract text from DOCX
def extract_docx_text(file):

    text = ""

    document = docx.Document(file)

    for para in document.paragraphs:
        text += para.text + "\n"

    return text


# API Endpoint
@app.post("/match-resume")
async def match_resume(
    resume: UploadFile = File(...),
    job_description: str = ""
):

    filename = resume.filename

    # Read uploaded file
    file_bytes = await resume.read()

    file_stream = BytesIO(file_bytes)

    # Extract text based on file type
    if filename.endswith(".pdf"):

        resume_text = extract_pdf_text(file_stream)

    elif filename.endswith(".docx"):

        resume_text = extract_docx_text(file_stream)

    else:
        return {
            "error": "Only PDF and DOCX files are supported"
        }

    # Generate embeddings
    resume_embedding = model.encode([resume_text])

    job_embedding = model.encode([job_description])

    # Similarity Score
    similarity = cosine_similarity(
        resume_embedding,
        job_embedding
    )[0][0]

    return {
        "filename": filename,
        "similarity_score": round(similarity * 100, 2)
    }