"""Client create / update — field-length guard.

clients.first_name and last_name are varchar(100), phone varchar(20) and email
varchar(255) (alembic ee7039bc78b2). The endpoints used to hand any length to
the INSERT/UPDATE, so one over-long phone raised psycopg2
StringDataRightTruncation and came back as a generic 500 ("Wystapil blad
serwera") which the React form then pinned on the first-name input.

Now they answer 400 and the message names the field in Polish: the form's
assignFieldError() picks the input to highlight from that text.

Auth is patched the same way as tests/routes/test_visit_notes_routes.py.
"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}
CLIENTS_FULL = {'has_access': True, 'read_only': False, 'own_data': False}

# (payload field, column limit, label the error must name)
LIMITED_FIELDS = [
    ('phone', 20, 'Telefon'),
    ('first_name', 100, 'Imię'),
    ('last_name', 100, 'Nazwisko'),
    ('email', 255, 'Email'),
]
IDS = [f[0] for f in LIMITED_FIELDS]

# Mirror of assignFieldError() in frontend/src/pages/clients/ClientFormPage.tsx:
# first matching keyword wins, default first_name.
_FORM_KEYWORDS = [
    ('first_name', ('imię', 'first')),
    ('last_name', ('nazwisko', 'last')),
    ('phone', ('telefon', 'phone')),
    ('email', ('email', 'e-mail')),
    ('date_of_birth', ('data', 'birth')),
]


def _form_field_for(message):
    lower = message.lower()
    for field, words in _FORM_KEYWORDS:
        if any(w in lower for w in words):
            return field
    return 'first_name'


def _of_length(field, length):
    """A value of exactly `length` characters that is otherwise plausible for `field`."""
    if field == 'email':
        return 'a' * (length - len('@a.pl')) + '@a.pl'
    return 'x' * length


def _payload(**overrides):
    body = {'first_name': 'Anna', 'last_name': 'Nowak', 'phone': '600 700 800',
            'email': 'anna@example.com'}
    body.update(overrides)
    return body


def _logged_in():
    from database.models import User
    user = User(email='t@test.pl', password_hash='x', full_name='Test User',
                role='manager', is_active=True, id=5)
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: (
        dict(CLIENTS_FULL) if module == 'clients'
        else {'has_access': False, 'read_only': False, 'own_data': False})
    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=user))
    return stack


@pytest.fixture
def env(app):
    from database.models import Client
    app.config['WTF_CSRF_ENABLED'] = False
    repo = MagicMock()
    repo.find_by_email.return_value = None
    repo.create.return_value = 42
    repo.update.return_value = True
    repo.get_by_id.return_value = {'id': 42}
    repo.row_to_client.return_value = Client(first_name='Anna', last_name='Nowak', id=42)
    app.client_repo = repo
    with patch('routes.api_routes._audit'), patch('routes.api_routes._audit_changes'):
        yield SimpleNamespace(c=app.test_client(), repo=repo)


def _create(env, **overrides):
    with _logged_in():
        return env.c.post('/api/clients', headers=XHR, json=_payload(**overrides))


def _update(env, **overrides):
    with _logged_in():
        return env.c.put('/api/clients/42', headers=XHR, json=_payload(**overrides))


@pytest.mark.parametrize('field,limit,label', LIMITED_FIELDS, ids=IDS)
class TestCreateClient:
    def test_over_limit_is_400_naming_the_field(self, env, field, limit, label):
        resp = _create(env, **{field: _of_length(field, limit + 1)})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False
        assert label in body['error'] and str(limit) in body['error']
        env.repo.create.assert_not_called()

    def test_message_lands_on_the_matching_form_input(self, env, field, limit, label):
        resp = _create(env, **{field: _of_length(field, limit + 1)})
        assert _form_field_for(resp.get_json()['error']) == field

    def test_exactly_at_limit_is_saved(self, env, field, limit, label):
        resp = _create(env, **{field: _of_length(field, limit)})
        assert resp.status_code == 200
        env.repo.create.assert_called_once()


@pytest.mark.parametrize('field,limit,label', LIMITED_FIELDS, ids=IDS)
class TestUpdateClient:
    def test_over_limit_is_400_naming_the_field(self, env, field, limit, label):
        resp = _update(env, **{field: _of_length(field, limit + 1)})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False
        assert label in body['error'] and str(limit) in body['error']
        env.repo.update.assert_not_called()

    def test_message_lands_on_the_matching_form_input(self, env, field, limit, label):
        resp = _update(env, **{field: _of_length(field, limit + 1)})
        assert _form_field_for(resp.get_json()['error']) == field

    def test_exactly_at_limit_is_saved(self, env, field, limit, label):
        resp = _update(env, **{field: _of_length(field, limit)})
        assert resp.status_code == 200
        env.repo.update.assert_called_once()


class TestPaddingIsNotCounted:
    """The endpoints store the .strip()ped value, so that is what the limit applies to."""

    def test_create_phone_padded_past_the_limit_is_saved(self, env):
        resp = _create(env, phone='  ' + 'x' * 20 + '  ')
        assert resp.status_code == 200
        assert env.repo.create.call_args[0][0].phone == 'x' * 20

    def test_update_phone_padded_past_the_limit_is_saved(self, env):
        resp = _update(env, phone='  ' + 'x' * 20 + '  ')
        assert resp.status_code == 200
        env.repo.update.assert_called_once()
