# model_cv_analyzer.py

import os
import re
import ast
import random
import shutil
import subprocess

import pandas as pd
import numpy as np
import pdfplumber
import docx

from langdetect import detect
from deep_translator import GoogleTranslator
from sentence_transformers import SentenceTransformer, util


# ============================================================
# 1) Load dataset
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "jobs_dataset.csv")
df = pd.read_csv(DATA_PATH)

# df = pd.read_csv(DATA_PATH)
# df = pd.read_csv("jobs_dataset.csv")  
df = df.drop(columns=["Unnamed: 0"], errors="ignore")

list_cols = [
    "skills_Element Name",
    "tasks_Task",
    "tech_Example",
    "tools_Example",
    "knowledge_Element Name",
    "abilities_Element Name",
    "skills_Data Value",
    "knowledge_Data Value",
    "abilities_Data Value"
]

for col in list_cols:
    if col in df.columns:
        df[col] = df[col].fillna("").astype(str)


df["job_profile"] = (
    "Title: " + df["Title"].fillna("") + "\n" +
    "Description: " + df["Description"].fillna("") + "\n" +
    "Skills: " + df["skills_Element Name"].fillna("") + "\n" +
    "Tasks: " + df["tasks_Task"].fillna("") + "\n" +
    "Technologies: " + df["tech_Example"].fillna("") + "\n" +
    "Tools: " + df["tools_Example"].fillna("") + "\n" +
    "Knowledge: " + df["knowledge_Element Name"].fillna("") + "\n" +
    "Abilities: " + df["abilities_Element Name"].fillna("")
)


# ============================================================
# 2) Load embedding model
# ============================================================

model = SentenceTransformer("all-MiniLM-L6-v2")

job_embeddings = model.encode(
    df["job_profile"].tolist(),
    convert_to_tensor=True,
    show_progress_bar=True
)


# ============================================================
# 3) Language normalization
# ============================================================

SUPPORTED_LANGS = ["en", "fr", "ar", "es", "de", "it", "pt", "nl"]


def chunk_text(text, max_chars=4500):
    chunks = []

    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start = end

    return chunks


def normalize_cv_language(cv_text):
    """
    Detects CV language.
    If not English, translates to English.
    Returns:
    - normalized text
    - original language
    - translated True/False
    """

    try:
        lang = detect(cv_text)
    except Exception:
        return cv_text, "unknown", False

    if lang not in SUPPORTED_LANGS:
        return cv_text, lang, False

    if lang == "en":
        return cv_text, lang, False

    translated_parts = []

    for chunk in chunk_text(cv_text, max_chars=4500):
        try:
            translated = GoogleTranslator(source=lang, target="en").translate(chunk)
            translated_parts.append(translated)
        except Exception:
            translated_parts.append(chunk)

    return "\n".join(translated_parts), lang, True


# ============================================================
# 4) File extraction
# ============================================================

def convert_doc_to_docx(input_file):
    """
    Converts old .doc to .docx using LibreOffice/soffice.
    Requires LibreOffice installed.
    """

    output_dir = os.path.dirname(input_file) or "."

    possible_commands = [
        "libreoffice",
        "soffice"
    ]

    command = None

    for cmd in possible_commands:
        if shutil.which(cmd):
            command = cmd
            break

    if command is None:
        raise RuntimeError(
            "Cannot convert .doc file because LibreOffice/soffice is not installed. "
            "Please upload .pdf, .docx, or .txt instead."
        )

    subprocess.run(
        [
            command,
            "--headless",
            "--convert-to",
            "docx",
            "--outdir",
            output_dir,
            input_file
        ],
        check=True
    )

    new_file = os.path.splitext(input_file)[0] + ".docx"

    if not os.path.exists(new_file):
        raise FileNotFoundError("DOC to DOCX conversion failed.")

    return new_file


def extract_text_from_pdf(file_path):
    text = ""

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    return text.strip()


def extract_text_from_docx(file_path):
    document = docx.Document(file_path)

    text = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text.append(paragraph.text.strip())

    return "\n".join(text).strip()


def extract_text_from_txt(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def extract_cv_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".doc":
        file_path = convert_doc_to_docx(file_path)
        ext = ".docx"

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)

    elif ext == ".docx":
        return extract_text_from_docx(file_path)

    elif ext == ".txt":
        return extract_text_from_txt(file_path)

    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ============================================================
# 5) Utility functions
# ============================================================

def clean_list_string(x):
    """
    Converts string lists from CSV into real Python lists.
    Handles values like np.float64(4.2).
    """

    if isinstance(x, list):
        return x

    if pd.isna(x):
        return []

    x = str(x)

    if not x.strip():
        return []

    x = re.sub(r"np\.float64\((.*?)\)", r"\1", x)
    x = re.sub(r"np\.int64\((.*?)\)", r"\1", x)

    try:
        value = ast.literal_eval(x)

        if isinstance(value, list):
            return value

        return [value]

    except Exception:
        return []


def split_cv_sentences(cv_text):
    sentences = re.split(r"[.\n;•]+", cv_text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def clean_tool_name(tool):
    tool = str(tool).strip()
    tool = re.sub(r"\s+", " ", tool)
    return tool


def is_bad_tool_name(tool):
    tool = clean_tool_name(tool)
    lower = tool.lower()

    if len(tool) <= 1:
        return True

    bad_keywords = [
        "desktop computers",
        "laptop computers",
        "personal computers",
        "smartphones",
        "tablet computers",
        "laser printers",
        "usb flash drives",
        "multi-line telephone systems"
    ]

    if lower in bad_keywords:
        return True

    return False


def exact_tool_match(cv_text, item):
    """
    Safer exact matching for tools/technologies.
    Avoids false matches like C inside words.
    """

    item = clean_tool_name(item)

    if len(item) <= 1:
        return False

    cv_lower = cv_text.lower()
    item_lower = item.lower()

    pattern = r"(?<![a-zA-Z0-9])" + re.escape(item_lower) + r"(?![a-zA-Z0-9])"

    return re.search(pattern, cv_lower) is not None


# ============================================================
# 6) Job detection
# ============================================================

def detect_jobs_from_cv(cv_text, top_k=5):
    cv_embedding = model.encode(cv_text, convert_to_tensor=True)

    scores = util.cos_sim(cv_embedding, job_embeddings)[0]
    top_results = scores.topk(k=top_k)

    results = []

    for score, idx in zip(top_results.values, top_results.indices):
        row = df.iloc[int(idx)]

        results.append({
            "title": row["Title"],
            "code": row["O*NET-SOC Code"],
            "similarity": round(float(score), 4),
            "description": row["Description"]
        })

    return results


# ============================================================
# 7) Weighted requirements matching
# ============================================================

def semantic_weighted_match_score(cv_text, job_row, model, threshold=0.30):
    skills = clean_list_string(job_row.get("skills_Element Name", ""))
    skill_weights = clean_list_string(job_row.get("skills_Data Value", ""))

    knowledge = clean_list_string(job_row.get("knowledge_Element Name", ""))
    knowledge_weights = clean_list_string(job_row.get("knowledge_Data Value", ""))

    abilities = clean_list_string(job_row.get("abilities_Element Name", ""))
    ability_weights = clean_list_string(job_row.get("abilities_Data Value", ""))

    requirements = []
    weights = []
    categories = []

    for item, weight in zip(skills, skill_weights):
        requirements.append(str(item))
        weights.append(float(weight))
        categories.append("skill")

    for item, weight in zip(knowledge, knowledge_weights):
        requirements.append(str(item))
        weights.append(float(weight))
        categories.append("knowledge")

    for item, weight in zip(abilities, ability_weights):
        requirements.append(str(item))
        weights.append(float(weight))
        categories.append("ability")

    if len(requirements) == 0:
        return {
            "match_score_100": 0,
            "match_score_10": 0,
            "found_requirements": [],
            "missing_requirements": []
        }

    cv_chunks = split_cv_sentences(cv_text)

    if len(cv_chunks) == 0:
        cv_chunks = [cv_text]

    req_embeddings = model.encode(requirements, convert_to_tensor=True)
    cv_embeddings = model.encode(cv_chunks, convert_to_tensor=True)

    sim_matrix = util.cos_sim(req_embeddings, cv_embeddings)

    max_scores = sim_matrix.max(dim=1).values.cpu().numpy()
    best_sentence_idx = sim_matrix.argmax(dim=1).cpu().numpy()

    found = []
    missing = []

    matched_weight = 0
    total_weight = 0

    for item, weight, category, sim, idx in zip(
        requirements,
        weights,
        categories,
        max_scores,
        best_sentence_idx
    ):
        total_weight += weight

        result_item = {
            "item": item,
            "category": category,
            "weight": round(weight, 2),
            "similarity": round(float(sim), 3),
            "matched_sentence": cv_chunks[int(idx)]
        }

        if sim >= threshold:
            matched_weight += weight
            found.append(result_item)
        else:
            missing.append(result_item)

    score_100 = round((matched_weight / max(total_weight, 1)) * 100, 2)

    return {
        "match_score_100": score_100,
        "match_score_10": round(score_100 / 10, 1),
        "found_requirements": sorted(found, key=lambda x: x["weight"], reverse=True),
        "missing_requirements": sorted(missing, key=lambda x: x["weight"], reverse=True)
    }


# ============================================================
# 8) Technology/tools matching
# ============================================================

def tech_tools_score(cv_text, job_row):
    techs = clean_list_string(job_row.get("tech_Example", ""))
    tools = clean_list_string(job_row.get("tools_Example", ""))

    all_items = []

    for tech in techs:
        tool_name = clean_tool_name(tech)

        if not is_bad_tool_name(tool_name):
            all_items.append({
                "item": tool_name,
                "category": "technology"
            })

    for tool in tools:
        tool_name = clean_tool_name(tool)

        if not is_bad_tool_name(tool_name):
            all_items.append({
                "item": tool_name,
                "category": "tool"
            })

    if len(all_items) == 0:
        return {
            "tech_tools_score": 0,
            "found_tech_tools": [],
            "missing_tech_tools": []
        }

    found = []
    missing = []

    for obj in all_items:
        if exact_tool_match(cv_text, obj["item"]):
            found.append(obj)
        else:
            missing.append(obj)

    score = round((len(found) / len(all_items)) * 100, 2)

    return {
        "tech_tools_score": score,
        "found_tech_tools": found,
        "missing_tech_tools": missing
    }


# ============================================================
# 9) Suggestions
# ============================================================

def generate_specific_suggestions(job_title, missing_requirements, missing_tech_tools):
    suggestions = []

    top_missing = [
        x for x in missing_requirements
        if x["category"] in ["skill", "knowledge", "ability"]
    ][:5]

    if top_missing:
        names = [x["item"] for x in top_missing]

        suggestions.append(
            f"For {job_title}, strengthen your CV by showing evidence of: "
            + ", ".join(names)
            + "."
        )

    if missing_tech_tools:
        tech_names = [x["item"] for x in missing_tech_tools[:5]]

        suggestions.append(
            "If relevant, mention tools or technologies you have used, such as: "
            + ", ".join(tech_names)
            + "."
        )

    suggestions.append(
        "Rewrite experience/project bullets using: action + skill/tool + measurable result."
    )

    suggestions.append(
        "Example: Managed project tasks using GitHub Projects or Jira, improving task tracking through clear milestones, ownership, and progress updates."
    )

    return suggestions


# ============================================================
# 10) Main analyzer
# ============================================================

def analyze_cv_against_best_job(cv_text, top_k=5, threshold=0.30, debug=False):
    detected_jobs = detect_jobs_from_cv(cv_text, top_k=top_k)

    best_job = detected_jobs[0]

    job_row = df[df["O*NET-SOC Code"] == best_job["code"]].iloc[0]

    weighted_result = semantic_weighted_match_score(
        cv_text=cv_text,
        job_row=job_row,
        model=model,
        threshold=threshold
    )

    tech_result = tech_tools_score(cv_text, job_row)

    occupation_similarity_score = round(best_job["similarity"] * 100, 2)

    final_score = round(
        0.60 * weighted_result["match_score_100"] +
        0.30 * tech_result["tech_tools_score"] +
        0.10 * occupation_similarity_score,
        2
    )

    result = {
        "detected_jobs": detected_jobs,
        "best_job": best_job,

        "weighted_requirements_score": weighted_result["match_score_100"],
        "tech_tools_score": tech_result["tech_tools_score"],
        "occupation_similarity_score": occupation_similarity_score,

        "match_score_100": final_score,
        "match_score_10": round(final_score / 10, 1),

        "found_weighted_requirements": weighted_result["found_requirements"][:20],
        "missing_weighted_requirements": weighted_result["missing_requirements"][:20],

        "found_tech_tools": tech_result["found_tech_tools"][:20],
        "missing_tech_tools": tech_result["missing_tech_tools"][:20],

        "suggestions": generate_specific_suggestions(
            best_job["title"],
            weighted_result["missing_requirements"],
            tech_result["missing_tech_tools"]
        )
    }

    return result


# ============================================================
# 11) Frontend helpers
# ============================================================

def get_score_label(score):
    if score < 30:
        return "Weak Match"
    elif score < 60:
        return "Moderate Match"
    elif score < 80:
        return "Good Match"
    else:
        return "Strong Match"


SCORE_EXPLANATIONS = {
    "Weak Match": [
        "Your CV currently shows limited alignment with this role. Focus on adding clearer skills, tools, and practical experience.",
        "The match is weak at the moment. The CV needs stronger evidence of role-specific requirements.",
        "This CV does not yet communicate enough relevant experience for the detected role.",
        "The detected role requires several skills and tools that are not clearly visible in the CV.",
        "Your CV needs more targeted content to fit this occupation better."
    ],
    "Moderate Match": [
        "Your CV has a moderate match. It shows relevant elements, but some important skills, tools, or achievements need to be clearer.",
        "The CV is partially aligned with this role, but it needs stronger evidence in key requirement areas.",
        "There is a good foundation, but the CV should better highlight role-specific experience and measurable impact.",
        "Your CV shows some relevant strengths, but several important requirements are still weakly represented.",
        "The profile is promising, but it needs more focused examples related to the detected occupation."
    ],
    "Good Match": [
        "Your CV is a good match. It already shows strong alignment, but improving a few missing areas could make it more competitive.",
        "The CV fits this role well, with only some gaps in specific skills, tools, or evidence.",
        "This is a solid match. Focus now on polishing weak areas and adding measurable achievements.",
        "Your profile is well aligned with the role, but a few improvements can increase its impact.",
        "The CV shows good relevance for this occupation and can be strengthened with more specific results."
    ],
    "Strong Match": [
        "Your CV is strongly aligned with this role. Only minor refinements are needed.",
        "This is a strong match. The CV clearly demonstrates many important requirements.",
        "Your profile fits the detected occupation very well. Focus on polishing wording and presentation.",
        "The CV shows excellent alignment with the role and only needs small improvements.",
        "This CV is highly relevant for the detected job. Minor additions can make it even stronger."
    ]
}


def generate_score_explanation(score, seed=None):
    level = get_score_label(score)
    rng = random.Random(seed)
    return rng.choice(SCORE_EXPLANATIONS[level])


def build_top_strengths(found_requirements, limit=8):
    strengths = []

    for item in found_requirements[:limit]:
        strengths.append({
            "name": item["item"],
            "type": item["category"],
            "importance": item["weight"],
            "confidence": item["similarity"],
            "evidence": item.get("matched_sentence", "")
        })

    return strengths


def build_priority_improvements(missing_requirements, limit=6):
    improvements = []

    for item in missing_requirements[:limit]:
        improvements.append({
            "name": item["item"],
            "type": item["category"],
            "importance": item["weight"],
            "reason": f"This is an important {item['category']} for the detected role but was weakly represented in the CV.",
            "how_to_improve": f"Add a bullet point, project, or experience example showing your use of {item['item']}."
        })

    return improvements


def clean_found_tools(found_tech_tools, limit=12):
    return [x["item"] for x in found_tech_tools[:limit]]


def build_recommended_tools(
    missing_tech_tools,
    best_job,
    found_weighted_requirements=None,
    model=None,
    limit=5
):
    if not missing_tech_tools or model is None:
        return []

    candidates = []

    for obj in missing_tech_tools:
        tool = clean_tool_name(obj["item"])

        if not is_bad_tool_name(tool):
            candidates.append(tool)

    if not candidates:
        return []

    job_context = (
        best_job["title"] + ". " +
        best_job.get("description", "")
    )

    if found_weighted_requirements:
        important_items = [
            x["item"] for x in found_weighted_requirements[:10]
        ]
        job_context += ". Important requirements: " + ", ".join(important_items)

    context_embedding = model.encode(job_context, convert_to_tensor=True)
    tool_embeddings = model.encode(candidates, convert_to_tensor=True)

    scores = util.cos_sim(tool_embeddings, context_embedding).cpu().numpy().flatten()

    ranked_tools = []

    for tool, score in zip(candidates, scores):
        ranked_tools.append({
            "name": tool,
            "relevance": round(float(score), 3)
        })

    ranked_tools = sorted(
        ranked_tools,
        key=lambda x: x["relevance"],
        reverse=True
    )

    return ranked_tools[:limit]


def get_tool_names(recommended_tools):
    tool_names = []

    for tool in recommended_tools:
        if isinstance(tool, dict):
            name = tool.get("name")
        else:
            name = str(tool)

        if name:
            tool_names.append(name)

    return tool_names


def build_action_plan(job_title, missing_requirements, recommended_tools):
    actions = []

    if missing_requirements:
        top_missing = [x["item"] for x in missing_requirements[:3]]

        actions.append({
            "title": "Strengthen missing requirements",
            "description": (
                f"For {job_title}, add clearer evidence for: "
                + ", ".join(top_missing)
                + "."
            ),
            "priority": "High"
        })

    tool_names = get_tool_names(recommended_tools)

    if tool_names:
        actions.append({
            "title": "Add relevant tools",
            "description": (
                "Mention tools you have used such as: "
                + ", ".join(tool_names[:5])
                + "."
            ),
            "priority": "Medium"
        })

    actions.append({
        "title": "Improve experience bullets",
        "description": "Rewrite experience/project bullets using: action + skill/tool + measurable result.",
        "priority": "High"
    })

    actions.append({
        "title": "Add measurable impact",
        "description": (
            "Use numbers such as percentages, number of users, projects completed, "
            "time saved, costs reduced, or accuracy improved."
        ),
        "priority": "High"
    })

    return actions


def generate_analysis_summary(result):
    job_title = result["best_job"]["title"]
    score = result["match_score_100"]
    label = result["score_label"]

    return (
        f"Your CV is closest to {job_title} with a {label.lower()} "
        f"score of {score}/100."
    )


def score_pct(x):
    return f"{round(x, 2)}%"


# ============================================================
# 12) Frontend result formatter
# ============================================================

def format_result_for_frontend(result):
    result["score_label"] = get_score_label(result["match_score_100"])

    result["score_explanation"] = generate_score_explanation(
        result["match_score_100"],
        seed=result["best_job"]["code"] + str(round(result["match_score_100"], 1))
    )

    result["top_strengths"] = build_top_strengths(
        result.get("found_weighted_requirements", [])
    )

    result["priority_improvements"] = build_priority_improvements(
        result.get("missing_weighted_requirements", [])
    )

    result["technologies_found"] = clean_found_tools(
        result.get("found_tech_tools", [])
    )

    result["recommended_tools"] = build_recommended_tools(
        missing_tech_tools=result.get("missing_tech_tools", []),
        best_job=result["best_job"],
        found_weighted_requirements=result.get("found_weighted_requirements", []),
        model=model,
        limit=5
    )

    result["action_plan"] = build_action_plan(
        result["best_job"]["title"],
        result.get("missing_weighted_requirements", []),
        result["recommended_tools"]
    )

    result["analysis_summary"] = generate_analysis_summary(result)
    result["match_score_pct"] = score_pct(result["match_score_100"])

    frontend_result = {
        "best_job": result["best_job"],
        "detected_jobs": result["detected_jobs"],

        "scores": {
            "overall": result["match_score_100"],
            "out_of_10": result["match_score_10"],
            "label": result["score_label"],
            "requirements": result["weighted_requirements_score"],
            "tools": result["tech_tools_score"],
            "occupation_similarity": result["occupation_similarity_score"],
            "percentage": result["match_score_pct"]
        },

        "language": {
            "original": result.get("original_language"),
            "translated": result.get("translated")
        },

        "summary": result["analysis_summary"],
        "score_explanation": result["score_explanation"],
        "top_strengths": result["top_strengths"],
        "priority_improvements": result["priority_improvements"],
        "technologies_found": result["technologies_found"],
        "recommended_tools": result["recommended_tools"],
        "action_plan": result["action_plan"],

        "raw": {
            "found_weighted_requirements": result.get("found_weighted_requirements", []),
            "missing_weighted_requirements": result.get("missing_weighted_requirements", []),
            "found_tech_tools": result.get("found_tech_tools", []),
            "missing_tech_tools": result.get("missing_tech_tools", []),
            "suggestions": result.get("suggestions", [])
        }
    }

    return frontend_result