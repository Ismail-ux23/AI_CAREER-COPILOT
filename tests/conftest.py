import importlib

import pytest


@pytest.fixture(scope='session')
def application(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        database = tmp_path_factory.mktemp('database') / 'test.db'
        patch.setenv('DATABASE_URL', f'sqlite:///{database}')
        patch.setenv('SECRET_KEY', 'tests-only-secret')
        patch.setenv('PRODUCTION', '0')
        module = importlib.import_module('app')
        module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        yield module
        module.engine.dispose()


@pytest.fixture
def client(application):
    application.Base.metadata.drop_all(bind=application.engine)
    application.Base.metadata.create_all(bind=application.engine)
    return application.app.test_client()


@pytest.fixture
def learner(client):
    assert client.post('/signup', data={
        'email':'learner@example.com', 'password':'a long secure password',
    }).status_code == 302
    assert client.post('/login', data={
        'email':'learner@example.com', 'password':'a long secure password',
    }).status_code == 302
    return client
