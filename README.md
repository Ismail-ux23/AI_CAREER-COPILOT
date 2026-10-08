# AI Career Copilot

A Python/Flask application that compares a resume with a target role using a locally configured Ollama model. Users can paste resume text or upload a text-based PDF/DOCX, review identified skills, learning gaps, a roadmap and interview questions, and revisit their saved reports.

## Implemented features

- Signup/login with hashed passwords and session authentication
- CSRF-protected forms and POST-only logout
- Pasted resume text, PDF text extraction, and DOCX paragraph extraction
- Ollama analysis with validation of the four expected list fields
- User-specific saved report history
- SQLite local setup, with optional TLS-enabled TiDB/MySQL configuration
- A 5 MB request limit and input-length checks

This version does not implement OCR for scanned PDFs, RAG/vector search, streaming, or a public REST API. AI suggestions are model output, not verified hiring decisions. Review them before acting on them.

## Local setup

Use Python 3.12 and an installed [Ollama](https://ollama.com/) service.

```bash
git clone https://github.com/Ismail-ux23/AI_CAREER-COPILOT.git
cd AI_CAREER-COPILOT
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama pull llama3.2:1b
```

If Ollama is not already running, run `ollama serve` in a separate terminal. Then start the application:

```bash
python app.py
```

Open http://127.0.0.1:5005, sign up with a 12–128 character password, log in, and submit a resume with a target role. A missing model or unavailable Ollama service produces an error and is not saved as a successful report.

On Windows, activate the environment with `.venv\Scripts\activate` and copy the configuration with `copy .env.example .env`.

SQLite tables are created automatically. Local state is stored in ignored `instance/`: `copilot.db` contains accounts, resume text and analysis; `session.key` contains a generated development session key. Keep this folder private. The application does not retain the uploaded document file; extracted resume text is stored for successful reports.

## Configuration

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Session signing and CSRF key; use a new random value for deployments |
| `DATABASE_URL` | Optional SQLAlchemy URL; defaults to local SQLite |
| `OLLAMA_HOST` | Ollama endpoint, normally `http://localhost:11434` |
| `OLLAMA_MODEL` | Installed model name, defaults to `llama3.2:1b` |
| `PRODUCTION` | Set to `1` to require `SECRET_KEY` and enable secure session cookies |

Generate a key with `python -c "import secrets; print(secrets.token_hex(32))"` and place it in `.env`. Never commit the actual key or database credentials.

For TiDB, set your own SQLAlchemy URL in `.env`, for example:

```text
DATABASE_URL=mysql+pymysql://USERNAME:URL_ENCODED_PASSWORD@HOST:4000/DATABASE
```

The PyMySQL connection uses the certifi CA bundle and hostname verification. URL-encode reserved characters in the username/password. A configured database must already exist; the application only creates missing tables.

## Upgrading the original version

The original repository committed database credentials and used a fixed session key and plaintext account passwords. Rotate/revoke the exposed database password at the provider and use a fresh `SECRET_KEY`. Removing credentials from the current file does not remove them from Git history. No remote database is altered automatically by this change.

For an existing TiDB/MySQL database, back it up and widen the password field before registering or resetting accounts:

```sql
ALTER TABLE users MODIFY COLUMN password VARCHAR(255);
```

`create_all` does not migrate an existing column. Existing SQLite databases do not enforce the old VARCHAR length. Legacy plaintext passwords are intentionally rejected at login. A trusted operator can set a new password interactively:

```bash
python -m flask --app app reset-password --email user@example.com
```

This prompts for a new password and confirmation without printing it. Do not pass passwords as command-line options. Existing logged-in sessions should be invalidated by changing the signing key. Password reset does not separately revoke active sessions.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use an isolated SQLite database and mocked AI responses; they do not contact TiDB or run a model. Coverage includes auth, password storage, CSRF, uploads, invalid AI responses and per-user history. The `Tests` GitHub Actions workflow runs on pushes and pull requests.

## Project structure

```text
app.py                  Flask routes and trusted password-reset CLI
ai.py                   Ollama prompt, response parsing and validation
db.py                   Environment-based database setup
models.py               Users and saved reports
Templates/              Jinja templates (explicitly configured for Linux)
static/style.css        Application styling
tests/                  Regression tests
.env.example            Placeholder configuration
requirements.txt        Runtime dependencies
requirements-dev.txt    Test dependencies
```

## Remaining work

Live Ollama quality/reliability and TiDB behavior need separate verification. Before a public deployment, add login rate limiting, an audited migration process, HTTPS with a production WSGI server, and resume-data retention/deletion controls. PDF extraction only reads embedded text; scanned documents require OCR. DOCX extraction currently reads paragraphs, not table cells. AI execution remains synchronous.

## Contributing

Report reproducible bugs with the Python version, steps, and expected/actual behavior. Remove resumes, credentials and personal data from logs. Keep pull requests focused and add regression tests for changes to authentication, upload handling and report ownership.

Built by **Ismail Manzoor**.
