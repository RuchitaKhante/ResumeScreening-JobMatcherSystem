from PyPDF2 import PdfReader
import docx
import yake

# 🔹 Extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    reader = PdfReader(file_path)
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

# 🔹 Extract text from DOCX
def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    return "\n".join(text)

# 🔹 Automatic skill extraction using YAKE
def extract_skills(text):
    kw_extractor = yake.KeywordExtractor(
        lan="en",
        n=2,        # phrases (e.g., "machine learning")
        top=15      # top keywords
    )

    keywords = kw_extractor.extract_keywords(text)

    skills = list(set([kw[0].lower() for kw in keywords]))

    return skills

# 🔹 Skill matching
def skill_match(resume_skills, job_skills):
    resume_set = set(resume_skills)
    job_set = set(job_skills)

    matched = resume_set.intersection(job_set)

    if len(job_set) == 0:
        return 0, []

    score = len(matched) / len(job_set)

    return score, list(matched)
import PyPDF2
import yake

def extract_text_from_pdf(pdf_path):

    text = ""

    with open(pdf_path, "rb") as file:

        reader = PyPDF2.PdfReader(file)

        for page in reader.pages:
            text += page.extract_text() + " "

    return text


def extract_skills(text):

    kw_extractor = yake.KeywordExtractor(
        lan="en",
        n=1,
        dedupLim=0.9,
        top=20
    )

    keywords = kw_extractor.extract_keywords(text)

    skills = [kw[0].lower() for kw in keywords]

    return list(set(skills))


def skill_match(resume_skills, job_skills):

    matched = list(
        set(resume_skills).intersection(set(job_skills))
    )

    if len(job_skills) == 0:
        return 0, []

    score = len(matched) / len(job_skills)

    return score, matched