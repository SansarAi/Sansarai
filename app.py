
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
import os, tempfile, pdfplumber
from docx import Document
import openai
from fpdf import FPDF
import csv

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.secret_key = "supersecret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sansarai.db"
app.config["UPLOAD_FOLDER"] = tempfile.gettempdir()
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for("register"))
        new_user = User(email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

def extract_text(file_path):
    if file_path.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or '' for page in pdf.pages)
    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    feedback = None
    if request.method == "POST" and 'agent_file' in request.files:
        file = request.files["agent_file"]
        user_goal = request.form["user_goal"]
        if file and user_goal:
            path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(path)
            content = extract_text(path)
            prompt = (
                f"You are a compliance AI agent.\n"
                f"USER GOAL: {user_goal}\n"
                "DOCUMENT CONTENT:\n" + content[:2000] + "\n\n"
                "Respond with:\n"
                "1. Compliance Score (0–100)\n"
                "2. Risk Breakdown\n"
                "3. Action Plan"
            )
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an AI compliance agent."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800
            )
            feedback = response['choices'][0]['message']['content']
            with open(os.path.join(app.config['UPLOAD_FOLDER'], "agent_report.txt"), "w") as f:
                f.write(feedback)
            new_report = Report(user_id=current_user.id, content=feedback)
            db.session.add(new_report)
            db.session.commit()
    reports = Report.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", feedback=feedback, reports=reports)

@app.route("/download-agent-report-pdf")
@login_required
def download_pdf():
    path_txt = os.path.join(app.config['UPLOAD_FOLDER'], "agent_report.txt")
    path_pdf = os.path.join(app.config['UPLOAD_FOLDER'], "agent_report.pdf")
    if not os.path.exists(path_txt):
        return "No report available."
    with open(path_txt, "r") as f:
        content = f.read()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in content.split("\n"):
        pdf.multi_cell(0, 10, line)
    pdf.output(path_pdf)
    return send_file(path_pdf, as_attachment=True)

@app.route("/download-compliance-score-csv")
@login_required
def download_csv():
    path_csv = os.path.join(app.config['UPLOAD_FOLDER'], "compliance_score.csv")
    with open(path_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Compliance Score", "See report"])
    return send_file(path_csv, as_attachment=True)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
