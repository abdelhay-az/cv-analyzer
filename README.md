CV Analyzer API & Web App

Overview

CV Analyzer is a full-stack project that analyzes a user's CV and matches it to the most relevant job role using NLP and semantic similarity.

The system:

Extracts text from CV files (PDF, DOCX, TXT)

Normalizes language (auto-detect + translation if needed)

Compares CV content against a jobs dataset

Computes a detailed score and breakdown

Returns actionable recommendations



---

Features

CV parsing (PDF, DOCX, TXT)

Language detection and normalization

Semantic matching using sentence-transformers

Scoring system (requirements, tools, similarity)

Actionable improvement suggestions

REST API (FastAPI)

Simple frontend interface



---

Tech Stack

Backend

FastAPI

Uvicorn

Sentence Transformers (MiniLM)

Pandas / NumPy

Scikit-learn

pdfplumber

python-docx

langdetect

deep-translator


Frontend

HTML

CSS

JavaScript (Fetch API)



---

Project Structure

cv-analyzer/
│
├── cv_api.py                # FastAPI app
├── model_cv_analyzer.py     # Core ML + logic
├── jobs_dataset.csv         # Jobs dataset
├── requirements.txt         # Dependencies
├── render.yaml              # Deployment config
├── index.html               # Frontend
├── uploads/                 # Temporary files (ignored)
└── README.md


---

Installation (Local)

1. Clone the repository

git clone https://github.com/your-username/cv-analyzer.git
cd cv-analyzer

2. Create virtual environment

python -m venv venv
source venv/bin/activate        # Linux / Mac
venv\Scripts\activate         # Windows

3. Install dependencies

pip install -r requirements.txt


---

Running the API

python -m uvicorn cv_api:app --reload

API will be available at:

http://127.0.0.1:8000

Swagger docs:

http://127.0.0.1:8000/docs


---

Using the Web Interface

1. Open index.html


2. Upload a CV


3. Click Analyze CV


4. View results (score, strengths, improvements, tools, action plan)




---

API Endpoint

POST /analyze-cv

Request:

file: CV file (PDF, DOCX, TXT)

top_k: number of job matches (optional)


Response:

{
  "best_job": {...},
  "scores": {
    "overall": 78,
    "requirements": 75,
    "tools": 70,
    "occupation_similarity": 80
  },
  "top_strengths": [...],
  "priority_improvements": [...],
  "recommended_tools": [...],
  "action_plan": [...]
}


---

Deployment (Render)

Steps

1. Push project to GitHub


2. Go to https://render.com


3. Create a Blueprint service