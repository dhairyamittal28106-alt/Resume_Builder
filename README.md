# Resume Builder

A Flask application for creating resumes and public portfolio pages. It includes account flows, resume templates, profile-picture uploads, a heuristic ATS-style score, and recruiter feedback integration.

## Run locally

Use Python 3.10 or newer:

    python -m venv .venv
    # Activate the environment, then:
    pip install -r requirements.txt
    python app.py

Flask typically serves the app at `http://127.0.0.1:5000`. The application uses a local SQLite database and stores profile uploads under `static/uploads/profile_pics`.

## Configuration

OAuth and AI feedback integrations need your own provider credentials. Review the configuration in `app.py`, replace demo placeholders, and set a secure Flask secret before deployment. Keep credentials out of source control.

## Source layout

- `app.py`: routes, database models, scoring, and integrations
- `templates/`: login, dashboard, resume form, and portfolio pages
- `static/`: styles and uploaded images
- `requirements.txt`: Python dependencies

The ATS-style score is a basic heuristic, not a hiring assessment.
