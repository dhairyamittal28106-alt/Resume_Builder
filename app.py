from flask import (
    Flask, render_template, request, redirect,
    session, make_response, url_for
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from xhtml2pdf import pisa
from io import BytesIO
import requests, os

# ---------------- APP CONFIG ----------------

app = Flask(__name__)
app.secret_key = "resume_secret"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["UPLOAD_FOLDER"] = "static/uploads/profile_pics"

db = SQLAlchemy(app)
oauth = OAuth(app)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openai/gpt-4o-mini"

# ---------------- OAUTH PROVIDERS ----------------

github = oauth.register(
    name="github",
    client_id="GITHUB_CLIENT_ID",
    client_secret="GITHUB_CLIENT_SECRET",
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "read:user repo"}
)

linkedin = oauth.register(
    name="linkedin",
    client_id="LINKEDIN_CLIENT_ID",
    client_secret="LINKEDIN_CLIENT_SECRET",
    access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
    authorize_url="https://www.linkedin.com/oauth/v2/authorization",
    api_base_url="https://api.linkedin.com/v2/",
    client_kwargs={"scope": "r_liteprofile"}
)

# ---------------- MODELS ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))


class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    title = db.Column(db.String(100))
    job_role = db.Column(db.String(100))
    skills = db.Column(db.Text)
    education = db.Column(db.Text)
    experience = db.Column(db.Text)
    linkedin = db.Column(db.Text)
    github = db.Column(db.Text)
    profile_pic = db.Column(db.String(200))
    template = db.Column(db.String(50))
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# ---------------- HELPERS ----------------

def ats_score(r):
    score = 0
    if len(r.skills) > 30: score += 25
    if "python" in r.skills.lower(): score += 15
    if r.github: score += 10
    if r.linkedin: score += 10
    if len(r.experience) > 40: score += 20
    if r.job_role.lower() in r.experience.lower(): score += 20
    return min(score, 100)


def ai_feedback(resume):
    prompt = f"""
You are an expert recruiter.
Job Role: {resume.job_role}

Skills: {resume.skills}
Education: {resume.education}
Experience: {resume.experience}

Give 3 short improvement suggestions.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Resume Builder"
    }

    data = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=20
        ).json()

        if "choices" in res:
            return res["choices"][0]["message"]["content"]

        return "AI feedback unavailable."

    except Exception as e:
        return str(e)


def fetch_github_projects(username):
    try:
        url = f"https://api.github.com/users/{username}/repos"
        repos = requests.get(url).json()

        projects = []
        for r in repos:
            if not r.get("fork"):
                projects.append({
                    "name": r["name"],
                    "url": r["html_url"]
                })
        return projects
    except:
        return []

# ---------------- AUTH ROUTES ----------------

@app.route("/")
def login():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def do_login():
    u = User.query.filter_by(email=request.form["email"]).first()
    if u and check_password_hash(u.password, request.form["password"]):
        session["user_id"] = u.id
        session["name"] = u.name
        return redirect("/dashboard")
    return "Invalid credentials"


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = User(
            name=request.form["name"],
            email=request.form["email"],
            password=generate_password_hash(request.form["password"])
        )
        db.session.add(user)
        db.session.commit()
        return redirect("/")
    return render_template("register.html")

# ---------------- GITHUB LOGIN ----------------

@app.route("/login/github")
def login_github():
    return github.authorize_redirect(
        url_for("auth_github", _external=True)
    )


@app.route("/auth/github")
def auth_github():
    token = github.authorize_access_token()
    user = github.get("user").json()

    session["github"] = user["login"]
    session["github_avatar"] = user["avatar_url"]
    session["projects"] = fetch_github_projects(user["login"])

    return redirect("/resume")

# ---------------- LINKEDIN LOGIN ----------------

@app.route("/login/linkedin")
def login_linkedin():
    return linkedin.authorize_redirect(
        url_for("auth_linkedin", _external=True)
    )


@app.route("/auth/linkedin")
def auth_linkedin():
    token = linkedin.authorize_access_token()
    profile = linkedin.get("me").json()

    session["name"] = (
        profile["localizedFirstName"] + " " +
        profile["localizedLastName"]
    )

    # Profile picture may or may not be available (LinkedIn restriction)
    try:
        pic = linkedin.get(
            "me?projection=(profilePicture(displayImage~:playableStreams))"
        ).json()
        session["linkedin_pic"] = pic
    except:
        pass

    return redirect("/resume")

# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():
    return render_template(
        "dashboard.html",
        name=session.get("name")
    )

# ---------------- RESUME ----------------

@app.route("/resume", methods=["GET", "POST"])
def resume():
    if request.method == "POST":

        filename = ""

        pic = request.files.get("profile_pic")
        if pic and pic.filename:
            filename = secure_filename(pic.filename)
            pic.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        if not filename:
            filename = (
                session.get("linkedin_pic")
                or session.get("github_avatar")
                or ""
            )

        projects_text = ""
        if session.get("projects"):
            projects_text = "\n\nProjects:\n" + "\n".join(
                f"- {p['name']} ({p['url']})"
                for p in session["projects"]
            )

        r = Resume(
            user_id=session["user_id"],
            title=request.form["title"],
            job_role=request.form["job_role"],
            skills=request.form["skills"],
            education=request.form["education"],
            experience=request.form["experience"] + projects_text,
            linkedin=request.form["linkedin"],
            github=request.form["github"],
            profile_pic=filename,
            template=request.form["template"]
        )

        db.session.add(r)
        db.session.commit()

        session.pop("projects", None)

        return redirect("/my-resumes")

    return render_template(
        "resume_form.html",
        projects=session.get("projects", []),
        name=session.get("name")
    )


# ---------------- MY RESUMES ----------------

@app.route("/my-resumes")
def my_resumes():
    resumes = Resume.query.filter_by(
        user_id=session["user_id"]
    ).all()
    return render_template(
        "resume_list.html",
        resumes=resumes
    )


@app.route("/delete/<int:id>", methods=["POST"])
def delete_resume(id):
    r = Resume.query.get_or_404(id)
    db.session.delete(r)
    db.session.commit()
    return redirect("/my-resumes")

# ---------------- PREVIEW & PDF ----------------

@app.route("/preview/<int:id>")
def preview(id):
    r = Resume.query.get(id)
    return render_template(
        f"resume_templates/{r.template}",
        resume=r,
        score=ats_score(r),
        ai_feedback=ai_feedback(r),
        projects=session.get("projects", [])
    )


@app.route("/download/<int:id>")
def download(id):
    r = Resume.query.get(id)

    html = render_template(
        f"resume_templates/{r.template}",
        resume=r,
        score=ats_score(r),
        projects=session.get("projects", [])
    )

    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        "attachment; filename=resume.pdf"
    )
    return response

# ---------------- PORTFOLIO ----------------



# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
@app.route("/portfolio/<int:id>")
def portfolio(id):
    r = Resume.query.get(id)
    r.views += 1
    db.session.commit()

    return render_template(
        "portfolio/portfolio.html",
        resume=r,
        projects=session.get("projects", [])
    )


# ---------------- MAIN ----------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

