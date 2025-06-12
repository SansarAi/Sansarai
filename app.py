
from flask import Flask, render_template_string, request
import openai
import os
import tempfile
import pdfplumber
from docx import Document

openai.api_key = os.getenv("OPENAI_API_KEY")
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

regulation_rules_v2 = [
    {
        "id": 1,
        "category": "transparency",
        "regulation": "EU AI Act",
        "question": "Do you notify users when they are interacting with an AI system?",
        "description": "Required for high-risk systems under Articles 52 & 54.",
        "severity": "high"
    },
    {
        "id": 2,
        "category": "bias/fairness",
        "regulation": "EU AI Act",
        "question": "Have you tested your model for discriminatory bias across protected attributes?",
        "description": "Required for high-risk use cases involving people.",
        "severity": "high"
    },
    {
        "id": 3,
        "category": "human oversight",
        "regulation": "EU AI Act",
        "question": "Can a human override or stop the AI system in case of malfunction or risk?",
        "description": "Mandatory for high-risk systems (Article 14).",
        "severity": "high"
    },
    {
        "id": 4,
        "category": "data governance",
        "regulation": "EU AI Act",
        "question": "Do you document the quality and relevance of your training data?",
        "description": "Critical for high-risk systems under Article 10.",
        "severity": "medium"
    },
    {
        "id": 5,
        "category": "privacy",
        "regulation": "GDPR",
        "question": "Do you obtain explicit consent before collecting personal data for automated decision-making?",
        "description": "Per Article 22, automated profiling without consent is prohibited.",
        "severity": "high"
    },
    {
        "id": 6,
        "category": "data minimization",
        "regulation": "GDPR",
        "question": "Do you only collect data strictly necessary for the AI function?",
        "description": "Mandated by Article 5(1)(c) of the GDPR.",
        "severity": "medium"
    },
    {
        "id": 7,
        "category": "access rights",
        "regulation": "GDPR",
        "question": "Can users request access or deletion of data used in automated decisions?",
        "description": "Required by Articles 15 and 17.",
        "severity": "high"
    },
    {
        "id": 8,
        "category": "explainability",
        "regulation": "U.S. AI Executive Order",
        "question": "Can your AI system explain its decisions in plain language to end users?",
        "description": "Encouraged for transparency and due process protections.",
        "severity": "medium"
    },
    {
        "id": 9,
        "category": "accountability",
        "regulation": "U.S. AI Executive Order",
        "question": "Do you document and assign accountability for AI failures or complaints?",
        "description": "Supports public trust and governance.",
        "severity": "medium"
    }
]

def get_rules_by_regulation(reg_name):
    return [r for r in regulation_rules_v2 if r["regulation"] == reg_name]

def score_compliance(answers, rules):
    severity_weights = {"low": 1, "medium": 2, "high": 3}
    total_weight = sum(severity_weights[r['severity']] for r in rules)
    score = sum(severity_weights[r['severity']] for r in rules if answers.get(str(r["id"])) == "yes")
    return round(score / total_weight * 100)

def generate_gpt_feedback(failed_rules):
    prompt = (
        "You are a compliance AI agent. Provide step-by-step guidance for the following failed rules:\n" +
        "\n".join([f"- {r['question']} ({r['regulation']}, severity: {r['severity']})" for r in failed_rules]) +
        "\nGive 3-5 clear action items for improvement."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful compliance expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ GPT feedback unavailable: {e}"

def extract_text_from_file(file_path):
    if file_path.endswith('.pdf'):
        try:
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(page.extract_text() or '' for page in pdf.pages)
        except Exception as e:
            return f"Error reading PDF: {e}"
    elif file_path.endswith('.docx'):
        try:
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            return f"Error reading DOCX: {e}"
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

def analyze_uploaded_doc(text, selected_reg):
    prompt = (
        "Analyze the following document for AI compliance issues based on " + selected_reg + ". "
        "Return a compliance score out of 100, a breakdown of risks (high/medium/low), and 3–5 recommended next steps.\n\n"
        "DOCUMENT:\n" + text[:2000]
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert AI compliance auditor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Document feedback error: {e}"

TEMPLATE = """<!doctype html>
<title>Sansarai Compliance Check</title>
<h1>AI Compliance Self-Assessment</h1>
<form method="post">
    <label for="regulation">Choose Regulation:</label>
    <select name="regulation" onchange="this.form.submit()" required>
        <option value="">-- Select --</option>
        {% for r in unique_regs %}
        <option value="{{ r }}" {% if selected_reg == r %}selected{% endif %}>{{ r }}</option>
        {% endfor %}
    </select>
</form>

{% if rules %}
<form method="post">
    <input type="hidden" name="regulation" value="{{ selected_reg }}">
    {% for rule in rules %}
    <p>
        <label>{{ rule.question }}</label><br>
        <small>{{ rule.description }}</small><br>
        <input type="radio" name="{{ rule.id }}" value="yes" required> Yes
        <input type="radio" name="{{ rule.id }}" value="no"> No
    </p>
    {% endfor %}
    <input type="submit" value="Generate Report">
</form>
{% endif %}

{% if report %}
<hr>
<h2>Compliance Score: {{ report['score'] }}%</h2>
<h3>GPT Recommendations:</h3>
<p>{{ report['gpt_feedback']|safe }}</p>
<p><a href="/">🔄 Start Over</a></p>
{% endif %}

<hr>
<h2>Optional: Upload a Document for Compliance Review</h2>
<form method="post" enctype="multipart/form-data">
    <input type="hidden" name="regulation" value="{{ selected_reg }}">
    <input type="file" name="uploaded_file" accept=".txt">
    <input type="submit" value="Analyze Document">
</form>
{% if doc_feedback %}
<h3>📄 Document Review Result:</h3>
<p>{{ doc_feedback|safe }}</p>
{% endif %}

<hr>
<h2>Or Ask the Compliance Agent to Analyze a Document Based on Your Goal</h2>
<form method="post" enctype="multipart/form-data">
    <input type="hidden" name="regulation" value="{{ selected_reg }}">
    <label>Describe your goal:</label><br>
    <textarea name="user_goal" rows="4" cols="60" placeholder="E.g., Identify all risks under GDPR in this document."></textarea><br>
    <input type="file" name="agent_file" accept=".txt,.pdf,.docx">
    <input type="submit" value="Run Compliance Agent">
</form>
{% if agent_feedback %}
<h3>🧠 Agent Output:</h3>
<p>{{ agent_feedback|safe }}</p>
{% endif %}
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    selected_reg = request.form.get("regulation") or ""
    rules = get_rules_by_regulation(selected_reg) if selected_reg else []
    unique_regs = sorted(set(r["regulation"] for r in regulation_rules_v2))
    report = None
    doc_feedback = None
    agent_feedback = None

    if request.method == 'POST' and rules:
        answers = {k: v for k, v in request.form.items() if k.isdigit()}
        if answers:
            score = score_compliance(answers, rules)
            failed_rules = [r for r in rules if answers.get(str(r['id'])) != "yes"]
            gpt_feedback = generate_gpt_feedback(failed_rules) if failed_rules else "✅ All checks passed! No critical issues found."
            report = {"score": score, "gpt_feedback": gpt_feedback}

        if 'uploaded_file' in request.files:
            file = request.files['uploaded_file']
            if file:
                path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(path)
                extracted_text = extract_text_from_file(path)
                doc_feedback = analyze_uploaded_doc(extracted_text, selected_reg)

        if 'agent_file' in request.files and 'user_goal' in request.form:
            agent_file = request.files['agent_file']
            user_goal = request.form['user_goal']
            if agent_file and user_goal.strip():
                path = os.path.join(app.config['UPLOAD_FOLDER'], agent_file.filename)
                agent_file.save(path)
                content = extract_text_from_file(path)
                goal_prompt = (
                    "You are a professional AI compliance agent. Your task is to analyze the following document based on the user's goal.\n\n"
                    f"USER GOAL: {user_goal}\n"
                    "DOCUMENT CONTENT:\n" + content[:2000] + "\n\n"
                    "Please provide:\n"
                    "1. A COMPLIANCE SCORE (0-100)\n"
                    "2. A RISK REPORT — list key risks and their severity (High/Medium/Low)\n"
                    "3. AN ACTION PLAN — 3-5 steps that can be taken to improve compliance\n"
                    "Respond professionally in report format. Be concise, specific, and refer to common regulatory language."
                )
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a multi-step AI compliance agent."},
                            {"role": "user", "content": goal_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=850
                    )
                    agent_feedback = response['choices'][0]['message']['content']
                except Exception as e:
                    agent_feedback = f"⚠️ Agent error: {e}"

    return render_template_string(TEMPLATE, rules=rules, selected_reg=selected_reg, unique_regs=unique_regs, report=report, doc_feedback=doc_feedback, agent_feedback=agent_feedback)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
