# Resume Builder

Flask app for creating resumes and portfolio pages, with account flows, templates, profile uploads, heuristic ATS scoring, and recruiter feedback integration.

    python -m venv .venv
    pip install -r requirements.txt
    python app.py

Activate the environment first. Typically opens at http://127.0.0.1:5000. Configure a secure Flask secret and your own OAuth/API credentials before deployment. Uses SQLite and stores uploads in static/uploads/profile_pics. ATS scoring is heuristic.
