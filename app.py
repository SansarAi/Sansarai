
from flask import Flask, render_template_string, request
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

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
        "category": "privacy",
        "regulation": "GDPR",
        "question": "Do you obtain explicit consent before collecting personal data for automated decision-making?",
        "description": "Per Article 22, automated profiling without consent is prohibited.",
        "severity": "high"
    },
    {
        "id": 3,
        "category": "accountability",
        "regulation": "ISO 42001",
        "question": "Do you maintain an AI risk register or log?",
        "description": "ISO recommends documenting risks and controls for each system.",
        "severity": "medium"
    },
    {
        "id": 4,
        "category": "bias/fairness",
        "regulation": "EU AI Act",
        "question": "Have you tested your model for discriminatory bias across protected attributes?",
        "description": "Required for high-risk use cases involving people.",
        "severity": "high"
    },
    {
        "id": 5,
        "category": "explainability",
        "regulation": "U.S. AI Executive Order",
        "question": "Can your AI system explain its decisions in plain language to end users?",
        "description": "Encouraged for transparency and due process protections.",
        "severity": "medium"
    },
    {
        "id": 6,
        "category": "human oversight",
        "regulation": "EU AI Act",
        "question": "Can a human override or stop the AI system in case of malfunction or risk?",
        "description": "Mandatory for high-risk systems (Article 14).",
        "severity": "high"
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
        "As an AI compliance consultant, provide actionable compliance advice based on the following failed rules:
" +
        "
".join([f"- {r['question']} (from {r['regulation']}, severity: {r['severity']})" for r in failed_rules]) +
        "
Give step-by-step guidance for each issue based on applicable regulations."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful AI compliance expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ GPT feedback unavailable: {e}"

TEMPLATE = """
<!doctype html>
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
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    selected_reg = request.form.get("regulation") or ""
    rules = get_rules_by_regulation(selected_reg) if selected_reg else []
    unique_regs = sorted(set(r["regulation"] for r in regulation_rules_v2))
    report = None

    if request.method == 'POST' and rules:
        answers = {k: v for k, v in request.form.items() if k.isdigit()}
        score = score_compliance(answers, rules)
        failed_rules = [r for r in rules if answers.get(str(r['id'])) != "yes"]
        gpt_feedback = generate_gpt_feedback(failed_rules)
        report = {"score": score, "gpt_feedback": gpt_feedback}

    return render_template_string(TEMPLATE, rules=rules, selected_reg=selected_reg, unique_regs=unique_regs, report=report)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
