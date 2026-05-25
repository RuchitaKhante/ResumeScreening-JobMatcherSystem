from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from io import BytesIO
import os
import json
import random

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

import PyPDF2
import docx

import pandas as pd

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
MODEL_DIR = os.path.join(APP_DIR, "models", "bert-matcher")


def _extract_pdf_text(file_stream) -> str:
    text = ""
    pdf_reader = PyPDF2.PdfReader(file_stream)
    for page in pdf_reader.pages:
        page_text = page.extract_text() or ""
        text += page_text
    return text


def _extract_docx_text(file_stream) -> str:
    document = docx.Document(file_stream)
    return "\n".join([p.text for p in document.paragraphs if p.text])


def extract_resume_text(resume_filename: str, file_bytes: bytes) -> str:
    file_stream = BytesIO(file_bytes)
    lower = (resume_filename or "").lower()
    if lower.endswith(".pdf"):
        return _extract_pdf_text(file_stream)
    if lower.endswith(".docx"):
        return _extract_docx_text(file_stream)
    raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")


class TrainRequest(BaseModel):
    epochs: int = 1
    batch_size: int = 8
    learning_rate: float = 2e-5
    max_samples: Optional[int] = 2000
    negative_k: int = 3
    seed: int = 42


class MatchResponse(BaseModel):
    filename: str
    match_score: float


class ModelInfoResponse(BaseModel):
    model_dir: str
    model_loaded: bool


app = FastAPI(title="Resume Job Matcher (BERT)")

# Java backend integration friendly defaults
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


MODEL_NAME_FALLBACK = "distilbert-base-uncased"

_tokenizer: Optional[AutoTokenizer] = None
_model: Optional[AutoModelForSequenceClassification] = None
_device = "cuda" if torch.cuda.is_available() else "cpu"


def _load_model_if_available():
    global _tokenizer, _model
    if os.path.isdir(MODEL_DIR) and os.path.isfile(os.path.join(MODEL_DIR, "config.json")):
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
        _model.to(_device)
        _model.eval()
        return True

    # fallback: load base model but untrained head (still runs)
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME_FALLBACK)
    _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME_FALLBACK, num_labels=1)
    _model.to(_device)
    _model.eval()
    return False


def _score_pair(resume_text: str, job_text: str) -> float:
    assert _tokenizer is not None and _model is not None

    # Cross-encoder style: [CLS] pooled classification head on concatenated pair
    # We use sigmoid on logits to map to [0,1], then scale to [0,100]
    inputs = _tokenizer(
        resume_text,
        job_text,
        truncation=True,
        max_length=512,
        return_tensors="pt",
        padding=True,
    )
    inputs = {k: v.to(_device) for k, v in inputs.items()}
    with torch.no_grad():
        out = _model(**inputs)
        logits = out.logits
        if logits.ndim == 2:
            logits = logits[:, 0]
        prob = torch.sigmoid(logits)[0].item()
    return float(round(prob * 100.0, 4))


@app.on_event("startup")
def _startup():
    os.makedirs(os.path.dirname(MODEL_DIR), exist_ok=True)
    _load_model_if_available()


@app.get("/api/health")
def health():
    return {"status": "ok", "device": _device}


@app.get("/api/model-info", response_model=ModelInfoResponse)
def model_info():
    loaded = _model is not None and _tokenizer is not None
    return ModelInfoResponse(model_dir=MODEL_DIR, model_loaded=loaded)


@app.post("/api/match", response_model=MatchResponse)
def match_resume(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
):
    if not job_description or not job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required")

    file_bytes = resume.file.read()
    resume_text = extract_resume_text(resume.filename, file_bytes)

    score = _score_pair(resume_text, job_description)
    return MatchResponse(filename=resume.filename, match_score=score)


def _train_model(req: TrainRequest) -> Dict[str, Any]:
    # Training is done with a simple pairwise margin objective using random negatives.
    # To keep it lightweight and fast, we implement a minimal training loop.
    from torch.nn.functional import logsigmoid

    df = pd.read_csv(os.path.join(DATA_DIR, "resume_job_cleaned.csv"))
    if "resume_text_clean" not in df.columns or "job_text_clean" not in df.columns:
        raise RuntimeError("resume_job_cleaned.csv must contain resume_text_clean and job_text_clean")

    # implicit positives: same row (resume_text_clean, job_text_clean)
    df = df.dropna(subset=["resume_text_clean", "job_text_clean"]).reset_index(drop=True)
    if req.max_samples is not None:
        df = df.sample(n=min(req.max_samples, len(df)), random_state=req.seed).reset_index(drop=True)

    random.seed(req.seed)

    global _tokenizer, _model
    base_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME_FALLBACK)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME_FALLBACK, num_labels=1)
    model.to(_device)
    model.train()

    optimizer = torch.optim.AdamW(model.parameters(), lr=req.learning_rate)

    # Pre-materialize texts for faster access
    resume_texts = df["resume_text_clean"].astype(str).tolist()
    job_texts = df["job_text_clean"].astype(str).tolist()

    n = len(df)
    total_steps = max(1, (req.epochs * n) // max(1, req.batch_size))

    step = 0
    for epoch in range(req.epochs):
        # shuffle indices each epoch
        idxs = list(range(n))
        random.shuffle(idxs)

        for start in range(0, n, req.batch_size):
            batch_idxs = idxs[start : start + req.batch_size]

            pos_pairs = [(resume_texts[i], job_texts[i]) for i in batch_idxs]
            # negatives: sample other jobs
            neg_pairs = []
            for i in batch_idxs:
                choices = [j for j in range(n) if j != i]
                neg_ids = random.sample(choices, k=min(req.negative_k, len(choices)))
                for nj in neg_ids:
                    neg_pairs.append((resume_texts[i], job_texts[nj]))

            # Score positives/negatives
            # Compute logits for positives and negatives separately and use a pairwise ranking loss.
            def compute_logits(pairs):
                texts_a = [p[0] for p in pairs]
                texts_b = [p[1] for p in pairs]
                enc = base_tokenizer(
                    texts_a,
                    texts_b,
                    truncation=True,
                    max_length=512,
                    padding=True,
                    return_tensors="pt",
                )
                enc = {k: v.to(_device) for k, v in enc.items()}
                out = model(**enc)
                logits = out.logits
                if logits.ndim == 2:
                    logits = logits[:, 0]
                return logits

            pos_logits = compute_logits(pos_pairs)  # [B]

            # reshape negatives to [B, K] for averaging
            if len(neg_pairs) == 0:
                continue
            neg_logits_flat = compute_logits(neg_pairs)  # [B*K]
            bsz = len(batch_idxs)
            k = max(1, int(len(neg_pairs) / bsz))
            neg_logits = neg_logits_flat.view(bsz, k).mean(dim=1)  # [B]

            # Objective: maximize pos_logit > neg_logit
            # Use log-sigmoid of (pos - neg)
            loss = -(logsigmoid(pos_logits - neg_logits).mean())

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            step += 1

    os.makedirs(MODEL_DIR, exist_ok=True)
    model.eval()
    model.save_pretrained(MODEL_DIR)
    base_tokenizer.save_pretrained(MODEL_DIR)

    return {
        "status": "trained",
        "epochs": req.epochs,
        "batch_size": req.batch_size,
        "learning_rate": req.learning_rate,
        "max_samples": req.max_samples,
        "negative_k": req.negative_k,
        "device": _device,
        "saved_to": MODEL_DIR,
    }


@app.post("/api/train")
def train(req: TrainRequest):
    # NOTE: This is synchronous training. For production, run in a background worker.
    try:
        result = _train_model(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # reload model for inference
    _load_model_if_available()
    return result

