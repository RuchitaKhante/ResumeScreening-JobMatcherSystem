from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, Form
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import PyPDF2
import docx
from io import BytesIO
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model once
model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)


# Extract PDF Text
def extract_pdf_text(file):
    text = ""
    pdf_reader = PyPDF2.PdfReader(file)
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    return text.strip()


# Extract DOCX Text
def extract_docx_text(file):
    text = ""
    document = docx.Document(file)
    for para in document.paragraphs:
        text += para.text + "\n"
    return text.strip()


# Honest score calculation
# all-MiniLM-L6-v2 cosine similarity gives values between 0.0 and 1.0
# Realistic ranges:
#   0.00 - 0.30  → very poor match
#   0.30 - 0.50  → weak match
#   0.50 - 0.65  → moderate match
#   0.65 - 0.80  → good match
#   0.80 - 1.00  → excellent match
def calculate_honest_score(similarity):

    # Step 1: convert numpy float32 → Python float
    sim = float(similarity)

    # Step 2: direct percentage — NO artificial boost
    # similarity is already 0.0 to 1.0, just multiply by 100
    score = sim * 100

    # Step 3: small penalty for very low matches
    # so truly unrelated resumes don't show 40%+
    if sim < 0.30:
        score = score * 0.6       # reduce low scores further

    # Step 4: cap at 95 (100% match is unrealistic)
    score = min(score, 95.0)

    return round(score, 2)


# Resume Matching API
@app.post("/match-resume")
async def match_resume(
    resume:          UploadFile = File(...),
    job_description: str        = Form(...)
):
    filename = resume.filename

    # Read uploaded file
    file_bytes  = await resume.read()
    file_stream = BytesIO(file_bytes)

    # Extract Resume Text
    if filename.lower().endswith(".pdf"):
        resume_text = extract_pdf_text(file_stream)
    elif filename.lower().endswith(".docx"):
        resume_text = extract_docx_text(file_stream)
    else:
        return {"error": "Only PDF and DOCX supported"}

    if not resume_text:
        return {"error": "Could not extract text from resume"}

    # Create embeddings
    resume_embedding = model.encode([resume_text])
    jd_embedding     = model.encode([job_description])

    # Cosine Similarity (returns 0.0 to 1.0 for this model)
    similarity = cosine_similarity(resume_embedding, jd_embedding)[0][0]

    # Honest score
    score = calculate_honest_score(similarity)

    # Match label for frontend display
    if score >= 75:
        label = "Excellent Match"
    elif score >= 55:
        label = "Good Match"
    elif score >= 35:
        label = "Moderate Match"
    else:
        label = "Poor Match"

    return {
        "filename":         filename,
        "similarity_score": score,
        "match_label":      label
    }


# Health check
@app.get("/")
def health():
    return {"status": "Running"}


# Run server
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)