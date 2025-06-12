from flask import Flask, render_template_string, request
import openai
import os
from typing import List, Dict

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

sample_policy = """
All AI systems must:
- Log decision outputs for audit purposes
- Provide a way for humans to override outcomes
- Avoid profiling without explicit consent
- Be tested for bias on sensitive attributes
"""

def parse_policy_to_rules(policy_text: str) -> List[Dict]:
    rules = [
        {"id": 1, "description": "Log decision outputs", "question": "Do you log all AI decisions for audit?", "category": "transparency"},
        {"id": 2, "description": "Human override", "question": "Can a human override AI decisions?", "category": "oversight"},
        {"id": 3, "description": "Profiling consent", "question": "Do you obtain explicit consent before profiling users?", "category": "privacy"},
        {"id": 4, "description": "Bias testing", "question": "Have you tested for bias in your AI system?", "category": "fairness"},
    ]
    return rules

def generate_onboarding_questions(rules: List[Dict]) -> List[str]:
    return [rule['question'] for rule in rules]

def score_compliance(answers: Dict[int, bool], rules: List[Dict]) -> Dict:
    total = len(rules)
    passed = sum(1 for rule in rules if answers.get(rule['id'], False))

    category_risk = {}
    for rule in rules:
        cat = rule['category']
        category_risk.setdefault(cat, []).append(answers.get(rule['id'], False))

    category_scores = {cat: sum(vals)/len(vals) for cat, vals in category_risk.items()}
    overall_score = passed / total
    return {"overall": overall_score, "by_category": category_scores}

def generate_report(score_data: Dict, rules: List[Dict], answers: Dict[int, bool]) -> str:
    report = ["<h2>SANSARAI COMPLIANCE REPORT</h2>"]
    report.append(f"<p><strong>Overall Compliance Score:</strong> {round(score_data['overall'] * 100)}%</p>")

    report.append("<ul>")
    for category, score in score_data['by_category'].items():
        report.append(f"<li><strong>{category.title()} Compliance:</strong> {round(score * 100)}%</li>")
    report.append("</ul>")

    report.append("<h3>Detailed Breakdown:</h3><ul>")
    for rule in rules:
        status = "✅ PASS" if answers.get(rule['id'], False) else "❌ FAIL"
        report.append(f"<li>{rule['description']}: {status}</li>")
    report.append("</ul>")
    return "\n".join(report)

def get_gpt_recommendations(answers: Dict[int, bool], rules: List[Dict]) -> str:
    failed = [rule['description'] for rule in rules if not answers.get(rule['id'], False)]
    prompt = (
        "You are an AI compliance consultant. The user failed the following categories: "
        + ", ".join(failed) +
        ". Based on global AI regulations (like EU AI Act and GDPR), provide a bullet-point list of practical, compliant, and risk-reducing action steps. Use a formal tone. Respond as a compliance advisor."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful compliance consultant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ GPT generation failed: {e}"

TEMPLATE = """
<!doctype html>
<title>Sansarai Compliance Agent</title>
<h1>AI Compliance Assessment</h1>
<form method=post>
  {% for rule in rules %}
    <p><label>{{ rule.question }}</label><br>
    <input type="radio" name="q{{ rule.id }}" value="yes" required> Yes
    <input type="radio" name="q{{ rule.id }}" value="no"> No
    </p>
  {% endfor %}
  <input type=submit value="Generate Report">
</form>
{% if report %}
<hr>
{{ report|safe }}
<h3>Stay Updated:</h3>
<form action="https://yournewsletterprovider.com/subscribe" method="POST">
  <label>Want to receive AI compliance updates from Sansarai?</label><br>
  <input type="email" name="EMAIL" placeholder="Enter your email" required>
  <input type="submit" value="Subscribe">
</form>
<p><a href="/">🔄 Start a new scan</a></p>
<p style="font-size: 12px;">This tool does not constitute legal advice. For formal compliance audits, consult a licensed professional.</p>
{% endif %}
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    rules = parse_policy_to_rules(sample_policy)
    report = ""
    if request.method == 'POST':
        answers = {}
        for rule in rules:
            val = request.form.get(f'q{rule["id"]}')
            answers[rule['id']] = (val == 'yes')
        scores = score_compliance(answers, rules)
        report = generate_report(scores, rules, answers)
        gpt_recommendations = get_gpt_recommendations(answers, rules)
        report += "<h3>AI-Generated Recommendations:</h3><p>{}</p>".format(gpt_recommendations.replace("\n", "<br>"))
    return render_template_string(TEMPLATE, rules=rules, report=report)

if __name__ == '__main__':
    app.run(debug=True)
