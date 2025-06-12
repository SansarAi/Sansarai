
from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import openai, os, uuid, pdfplumber
from fpdf import FPDF
from docx import Document
import csv

app = Flask(__name__)
app.secret_key = "secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["UPLOAD_FOLDER"] = "uploads"
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    pro = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET", "POST"])
def home():
    feedback = ""
    score = None
    if request.method == "POST":
        regulation = request.form.get("regulation")
        text = request.form.get("text")
        prompt = f"Assess this system against the {regulation}. Give a compliance score out of 100 and suggestions.\n\n{text}"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        feedback = response.choices[0].message["content"]
        score = sum(int(s) for s in feedback.split() if s.isdigit() and int(s) <= 100)
        session_id = str(uuid.uuid4())

        # Save report as CSV
        with open(f"uploads/{session_id}.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow(["Regulation", "Score", "Feedback"])
            writer.writerow([regulation, score, feedback[:100].replace("\n", " ")])

        # Save as PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, feedback)
        pdf.output(f"uploads/{session_id}.pdf")

        return render_template("report.html", score=score, feedback=feedback, sid=session_id)
    return render_template("home.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    if file.filename.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    elif file.filename.endswith(".docx"):
        doc = Document(file)
        text = "\n".join([p.text for p in doc.paragraphs])
    else:
        return "Unsupported file"
    return render_template("home.html", text=text)

@app.route("/report/<sid>/csv")
def download_csv(sid):
    return send_file(f"uploads/{sid}.csv", as_attachment=True)

@app.route("/report/<sid>/pdf")
def download_pdf(sid):
    return send_file(f"uploads/{sid}.pdf", as_attachment=True)

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/login")
def login(): return render_template("login.html")

@app.route("/pricing")
def pricing(): return render_template("pricing.html")

@app.route("/faq")
def faq(): return render_template("faq.html")

@app.route("/contact")
def contact(): return render_template("contact.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
app.run(host='0.0.0.0', port=10000)
