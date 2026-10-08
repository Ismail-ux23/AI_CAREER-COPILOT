import io
import re
from types import SimpleNamespace

import docx
import pytest
from werkzeug.security import check_password_hash


RESULT = {'skills':['Python'], 'missing_skills':['SQL'],
          'roadmap':['Build an API'], 'interview_questions':['What is a list?']}


def test_templates_and_access_control(client):
    for path in ['/login', '/signup']:
        assert client.get(path).status_code == 200
    for path in ['/dashboard', '/history']:
        assert client.get(path).headers['Location'] == '/login'


def test_hashed_passwords_and_logout(learner, application):
    with application.SessionLocal() as db:
        user = db.query(application.models.User).one()
        assert user.password != 'a long secure password'
        assert check_password_hash(user.password, 'a long secure password')
    assert learner.get('/dashboard').status_code == 200
    assert learner.get('/logout').status_code == 405
    assert learner.post('/logout').status_code == 302
    assert learner.post('/login', data={
        'email':'learner@example.com', 'password':'wrong password',
    }).status_code == 401


def test_legacy_plaintext_password_is_rejected(client, application):
    with application.SessionLocal() as db:
        db.add(application.models.User(email='legacy@example.com', password='legacy password'))
        db.commit()
    assert client.post('/login', data={
        'email':'legacy@example.com', 'password':'legacy password',
    }).status_code == 401


def test_operator_can_reset_legacy_password(client, application):
    with application.SessionLocal() as db:
        db.add(application.models.User(email='legacy@example.com', password='legacy password'))
        db.commit()
    result = application.app.test_cli_runner().invoke(
        args=['reset-password', '--email', 'legacy@example.com'],
        input='a new secure password\na new secure password\n',
    )
    assert result.exit_code == 0, result.output
    assert 'a new secure password' not in result.output
    assert client.post('/login', data={
        'email':'legacy@example.com', 'password':'a new secure password',
    }).status_code == 302


def test_signup_validation_and_duplicate_email(client):
    assert client.post('/signup', data={}).status_code == 400
    data = {'email':' Learner@Example.com ', 'password':'a long secure password'}
    assert client.post('/signup', data=data).status_code == 302
    assert client.post('/signup', data=data).status_code == 409


def test_analysis_history_and_user_isolation(learner, application, monkeypatch):
    monkeypatch.setattr(application, 'analyze_resume', lambda text, role: RESULT)
    assert learner.post('/dashboard', data={'resume':'Python developer', 'role':'Backend'}).status_code == 200
    assert b'Python developer' in learner.get('/history').data
    other = application.app.test_client()
    other.post('/signup', data={'email':'other@example.com', 'password':'another secure password'})
    other.post('/login', data={'email':'other@example.com', 'password':'another secure password'})
    assert b'Python developer' not in other.get('/history').data


def test_docx_upload_extracts_text(learner, application, monkeypatch):
    captured = []
    monkeypatch.setattr(application, 'analyze_resume', lambda text, role: captured.append(text) or RESULT)
    document = docx.Document()
    document.add_paragraph('Python and SQL experience')
    stream = io.BytesIO()
    document.save(stream)
    stream.seek(0)
    response = learner.post('/dashboard', data={
        'file':(stream, 'RESUME.DOCX'), 'role':'Developer',
    })
    assert response.status_code == 200
    assert captured == ['Python and SQL experience']


@pytest.mark.parametrize('filename', ['resume.docx', 'resume.pdf', 'resume.exe'])
def test_bad_uploads_do_not_call_ai_or_save(learner, application, monkeypatch, filename):
    def unexpected(*args):
        pytest.fail('AI should not be called after upload failure')
    monkeypatch.setattr(application, 'analyze_resume', unexpected)
    response = learner.post('/dashboard', data={
        'file':(io.BytesIO(b'invalid document'), filename), 'role':'Developer',
        'resume':'Fallback must not hide an upload error',
    })
    assert b'Error:' in response.data
    with application.SessionLocal() as db:
        assert db.query(application.models.Reports).count() == 0


def test_provider_failure_is_not_saved(learner, application, monkeypatch):
    monkeypatch.setattr(application, 'analyze_resume', lambda *args: {'error':'Provider unavailable'})
    assert b'Provider unavailable' in learner.post('/dashboard', data={
        'resume':'Python developer', 'role':'Backend',
    }).data
    with application.SessionLocal() as db:
        assert db.query(application.models.Reports).count() == 0


def test_csrf_protects_forms_and_logout(client, application, monkeypatch):
    monkeypatch.setitem(application.app.config, 'WTF_CSRF_ENABLED', True)
    assert client.post('/signup', data={}).status_code == 400
    assert client.post('/logout').status_code == 400
    html = client.get('/signup').data.decode()
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    assert client.post('/signup', data={
        'email':'csrf@example.com', 'password':'a long secure password', 'csrf_token':token,
    }).status_code == 302


@pytest.mark.parametrize('content', ['[]', '{"skills":[]}', '{"skills":"bad"}', 'not JSON'])
def test_malformed_ai_results_are_safe(application, monkeypatch, content):
    import ai
    monkeypatch.setattr(ai, 'chat', lambda **kwargs: SimpleNamespace(message=SimpleNamespace(content=content)))
    result = ai.analyze_resume('Resume', 'Backend')
    assert 'error' in result
    assert result['skills'] == []


def test_valid_ai_result_and_configurable_model(application, monkeypatch):
    import ai
    import json
    calls = []
    def chat(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps(RESULT)))
    monkeypatch.setattr(ai, 'chat', chat)
    monkeypatch.setenv('OLLAMA_MODEL', 'test-model')
    assert ai.analyze_resume('Resume', 'Backend') == RESULT
    assert calls[0]['model'] == 'test-model'
