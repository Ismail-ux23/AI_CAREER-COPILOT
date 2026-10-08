"""Local resume analysis application."""
import json
import os
import secrets
from pathlib import Path

import click
import docx
import PyPDF2
from flask import Flask, redirect, render_template, request, session
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

import models
from ai import analyze_resume
from db import Base, SessionLocal, engine

app = Flask(__name__, template_folder='Templates')
secret = os.getenv('SECRET_KEY')
if not secret:
    if os.getenv('PRODUCTION') == '1':
        raise RuntimeError('Set SECRET_KEY before running in production')
    key_path = Path(app.instance_path) / 'session.key'
    key_path.parent.mkdir(exist_ok=True)
    try:
        with key_path.open('x') as key_file:
            key_path.chmod(0o600)
            key_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    secret = key_path.read_text()
app.config.update(
    SECRET_KEY=secret,
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('PRODUCTION') == '1',
)
CSRFProtect(app)
Base.metadata.create_all(bind=engine)


@app.route('/')
def home():
    return redirect('/dashboard' if 'user' in session else '/login')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or '@' not in email or len(email) > 100 or not 12 <= len(password) <= 128:
            return render_template('signup.html', error='Enter an email and a 12–128 character password.'), 400
        with SessionLocal() as db:
            user = models.User(email=email, password=generate_password_hash(password))
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                return render_template('signup.html', error='That email is already registered.'), 409
        return redirect('/login')
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        with SessionLocal() as db:
            user = db.query(models.User).filter_by(email=email).first()
            # Legacy plaintext passwords must be reset; never authenticate them.
            stored = user.password if user else ''
            valid = bool(len(password) <= 128 and stored and stored.startswith(('scrypt:', 'pbkdf2:')))
            if valid:
                try:
                    valid = check_password_hash(stored, password)
                except ValueError:
                    valid = False
            if valid:
                session.clear()
                session['user'] = user.email
                return redirect('/dashboard')
        return render_template('login.html', error='Invalid credentials.'), 401
    return render_template('login.html')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    result = None
    if request.method == 'POST':
        goal = request.form.get('role', '').strip()
        resume_text = request.form.get('resume', '').strip()
        upload = request.files.get('file')
        if upload and upload.filename:
            suffix = Path(upload.filename).suffix.lower()
            try:
                if suffix == '.pdf':
                    reader = PyPDF2.PdfReader(upload)
                    resume_text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                elif suffix == '.docx':
                    document = docx.Document(upload)
                    resume_text = '\n'.join(paragraph.text for paragraph in document.paragraphs)
                else:
                    result = {'error': 'Upload a PDF or DOCX file.'}
            except Exception:
                result = {'error': 'Could not read that document. Try a text-based PDF, DOCX, or paste your resume.'}
        if result is None:
            if not resume_text.strip() or not goal:
                result = {'error': 'Provide readable resume text and a target role.'}
            elif len(resume_text) > 50000 or len(goal) > 200:
                result = {'error': 'Keep resume text under 50,000 characters and the role under 200.'}
            else:
                try:
                    result = analyze_resume(resume_text, goal)
                    if not result.get('error'):
                        with SessionLocal() as db:
                            user = db.query(models.User).filter_by(email=session['user']).first()
                            if not user:
                                session.clear()
                                return redirect('/login')
                            db.add(models.Reports(user_id=user.id, resume_text=resume_text, result=json.dumps(result)))
                            db.commit()
                except Exception:
                    app.logger.error('Resume analysis or report persistence failed')
                    result = {'error': 'Analysis could not be completed. Please try again.'}
    return render_template('dashboard.html', user=session['user'], result=result)


@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/login')
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email=session['user']).first()
        if not user:
            session.clear()
            return redirect('/login')
        reports = db.query(models.Reports).filter_by(user_id=user.id).order_by(models.Reports.id.desc()).all()
        parsed_reports = []
        for report in reports:
            try:
                result = json.loads(report.result)
                if not isinstance(result, dict):
                    result = {}
            except (TypeError, json.JSONDecodeError):
                result = {}
            parsed_reports.append({'resume': report.resume_text, 'result': result})
    return render_template('history.html', reports=parsed_reports)


@app.post('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.cli.command('reset-password')
@click.option('--email', prompt=True)
@click.password_option()
def reset_password(email, password):
    """Reset an account password through trusted operator access."""
    if not 12 <= len(password) <= 128:
        raise click.ClickException('Use a 12–128 character password.')
    with SessionLocal() as db:
        user = db.query(models.User).filter_by(email=email.strip().lower()).first()
        if not user:
            raise click.ClickException('Account not found.')
        user.password = generate_password_hash(password)
        db.commit()
    click.echo('Password reset. The user can now sign in.')


if __name__ == '__main__':
    app.run(port=5005, debug=False)
