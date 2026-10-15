"""/api/support — the agent endpoints are gated by the 'support_tickets' module.

A role without the module must be refused on every /admin route AND must not reach
the service; the author endpoints only need a session.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}
ON = {'has_access': True, 'read_only': False, 'own_data': False}
OFF = {'has_access': False, 'read_only': False, 'own_data': False}
RO = {'has_access': True, 'read_only': True, 'own_data': False}


def _user(role='stylist', uid=7):
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User', role=role, is_active=True, id=uid)


@pytest.fixture
def api(app):
    app.config['WTF_CSRF_ENABLED'] = False
    return app.test_client()


def _as(flags, role='stylist'):
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda r, module: dict(flags if module == 'support_tickets' else ON)
    service = MagicMock()
    service.admin_list.return_value = {'tickets': [], 'total': 0, 'counts': {}}
    service.admin_overview.return_value = {'counts': {}, 'stats': {}, 'agents': []}
    service.list_mine.return_value = {'tickets': [], 'unread': 0}
    service.create.return_value = {'id': 3}
    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('routes.support_routes.SupportTicketService', return_value=service))
    stack.enter_context(patch('routes.support_routes.audit_event'))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=_user(role)))
    return stack, service


ADMIN_CALLS = [
    ('get', '/api/support/admin/overview', None),
    ('get', '/api/support/admin/tickets', None),
    ('get', '/api/support/admin/tickets/1', None),
    ('post', '/api/support/admin/tickets/1/messages', {'body': 'x'}),
    ('patch', '/api/support/admin/tickets/1', None),
]


@pytest.mark.parametrize('method,url,data', ADMIN_CALLS)
def test_admin_routes_refuse_without_module(api, method, url, data):
    stack, service = _as(OFF)
    with stack:
        resp = getattr(api, method)(url, headers=XHR, data=data, json=None if data else {})
    assert resp.status_code == 403
    assert not any(call[0].startswith('admin') for call in service.method_calls)


def test_admin_read_only_can_list_but_not_write(api):
    stack, service = _as(RO)
    with stack:
        assert api.get('/api/support/admin/tickets', headers=XHR).status_code == 200
        assert api.patch('/api/support/admin/tickets/1', headers=XHR, json={'status': 'resolved'}).status_code == 403
    service.admin_update.assert_not_called()


def test_agent_reaches_the_service(api):
    stack, service = _as(ON, role='superuser')
    with stack:
        resp = api.get('/api/support/admin/tickets?view=new', headers=XHR)
    assert resp.status_code == 200
    service.admin_list.assert_called_once()


def test_author_routes_need_only_a_session(api):
    stack, service = _as(OFF)
    with stack:
        assert api.get('/api/support/tickets', headers=XHR).status_code == 200
        resp = api.post('/api/support/tickets', headers=XHR,
                        data={'kind': 'problem', 'area': 'sms', 'body': 'abcdefghijkl'})
    assert resp.status_code == 201 and resp.get_json()['id'] == 3
    server_ctx = service.create.call_args.args[3]
    assert server_ctx['user']['id'] == 7 and 'ip' in server_ctx


def test_anonymous_is_refused(api):
    resp = api.get('/api/support/tickets', headers=XHR)
    assert resp.status_code in (401, 302)
