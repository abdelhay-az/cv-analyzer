# cv_api.py

import os
import shutil
import traceback

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from model_cv_analyzer import (
    extract_cv_text,
    normalize_cv_language,
    analyze_cv_against_best_job,
    format_result_for_frontend,
)

app = FastAPI(title="CV Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later replace with your real website URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
def home():
    return {
        "message": "CV Analyzer API is running",
        "endpoint": "/analyze-cv",
    }


@app.post("/analyze-cv")
async def analyze_cv(
    file: UploadFile = File(...),
    top_k: int = Form(5),
    threshold: float = Form(0.30),
):
    allowed_extensions = [".pdf", ".docx", ".doc", ".txt"]

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file uploaded."
        )

    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use PDF, DOCX, DOC, or TXT."
        )

    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        # 1) Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2) Extract text
        cv_text = extract_cv_text(file_path)

        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(
                status_code=400,
                detail="Could not extract enough text from the CV."
            )

        # 3) Normalize language
        cv_text_en, original_lang, translated = normalize_cv_language(cv_text)

        # 4) Run model
        raw_result = analyze_cv_against_best_job(
            cv_text=cv_text_en,
            top_k=top_k,
            threshold=threshold,
        )

        # 5) Add metadata
        raw_result["original_language"] = original_lang
        raw_result["translated"] = translated

        # 6) Format result for website
        result = format_result_for_frontend(raw_result)

        return result

    except HTTPException:
        raise

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("cv_api:app", host="0.0.0.0", port=port)