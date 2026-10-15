"""SupportTicketService — validation, ownership and the status machine (no database)."""
import io
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from exceptions import ConflictError, NotFoundError, ValidationError
from services.support_ticket_service import SupportTicketService, parse_context, read_images, _title_from

USER = SimpleNamespace(id=7, role='stylist')
AGENT = SimpleNamespace(id=1, role='superuser')


def _png(size=(20, 10)):
    buf = io.BytesIO()
    Image.new('RGB', size, 'red').save(buf, format='PNG')
    buf.seek(0)
    return buf


class _Upload:
    def __init__(self, data, filename='x.png'):
        self._data = data.getvalue() if hasattr(data, 'getvalue') else data
        self.filename = filename

    def read(self):
        return self._data


def _ticket(**over):
    base = {
        'id': 5, 'created_by': USER.id, 'status': 'in_progress', 'priority': 'normal', 'assigned_to': None,
        'close_reason': None, 'closed_at': None, 'first_response_at': None, 'kind': 'problem',
        'area': 'sms', 'area_label': 'Wysyłki SMS', 'title': 't',
        'created_at': datetime(2026, 10, 1), 'updated_at': datetime(2026, 10, 1),
    }
    base.update(over)
    return base


def _svc(ticket=None, recent=0):
    repo = MagicMock()
    repo.get_ticket.return_value = ticket
    repo.count_recent_by_user.return_value = recent
    repo.create_ticket.return_value = 99
    repo.add_message.return_value = 123
    repo.list_agents.return_value = [{'id': 1, 'full_name': 'Admin'}]
    return SupportTicketService(repo), repo


FORM = {'kind': 'problem', 'area': 'sms', 'area_label': 'Wysyłki SMS',
        'body': 'Nie wysyła się SMS do klientki. Klikam i nic.', 'context': '{"page": {"path": "/x"}}'}


# ── create ───────────────────────────────────────────────────────────────────

def test_create_stores_context_with_server_block_and_title():
    svc, repo = _svc()
    assert svc.create(USER, FORM, [], {'ip': '1.2.3.4'}) == {'id': 99}
    kwargs = repo.create_ticket.call_args.kwargs
    assert kwargs['title'] == 'Nie wysyła się SMS do klientki.'
    assert kwargs['context']['page'] == {'path': '/x'}
    assert kwargs['context']['server']['ip'] == '1.2.3.4'
    assert kwargs['priority'] == 'normal'


def test_create_needs_text_or_screenshot():
    svc, _ = _svc()
    with pytest.raises(ValidationError):
        svc.create(USER, {**FORM, 'body': 'krótko'}, [], {})
    svc.create(USER, {**FORM, 'body': ''}, [_Upload(_png())], {})  # screenshot alone is enough


@pytest.mark.parametrize('field,value', [('kind', 'spam'), ('area', ''), ('area', 'DROP TABLE')])
def test_create_rejects_bad_kind_or_area(field, value):
    svc, _ = _svc()
    with pytest.raises(ValidationError):
        svc.create(USER, {**FORM, field: value}, [], {})


def test_create_is_rate_limited():
    svc, _ = _svc(recent=10)
    with pytest.raises(ConflictError) as exc:
        svc.create(USER, FORM, [], {})
    assert exc.value.status_code == 429


# ── images & context ─────────────────────────────────────────────────────────

def test_read_images_sniffs_the_real_format():
    out = read_images([_Upload(_png((30, 40)), 'shot.jpg')])
    assert out[0]['mime'] == 'image/png' and out[0]['filename'] == 'shot.png'
    assert (out[0]['width'], out[0]['height']) == (30, 40)


def test_read_images_rejects_non_images_and_too_many():
    with pytest.raises(ValidationError):
        read_images([_Upload(b'<html>hi</html>', 'a.png')])
    with pytest.raises(ValidationError):
        read_images([_Upload(_png()) for _ in range(4)])


def test_parse_context_drops_heavy_parts_over_the_cap():
    ctx = parse_context({'page': {'path': '/a', 'text': 'x' * 500_000}, 'user': {'id': 1}})
    assert ctx['page']['path'] == '/a'
    assert ctx['page']['text'].startswith('[usunięte')
    assert parse_context('not json') == {'_error': 'context was not valid JSON'}
    assert parse_context('[1,2]') == {'_error': 'context was not an object'}


def test_title_falls_back_and_truncates():
    assert _title_from('', 'Wysyłki SMS') == 'Wysyłki SMS'
    assert len(_title_from('a' * 300, 'x')) == 118


# ── author side ──────────────────────────────────────────────────────────────

def test_someone_elses_ticket_is_not_found():
    svc, _ = _svc(_ticket(created_by=42))
    with pytest.raises(NotFoundError):
        svc.get_mine(USER, 5)
    with pytest.raises(NotFoundError):
        svc.reply_as_author(USER, 5, {'body': 'hej'}, [])


@pytest.mark.parametrize('status', ['waiting_user', 'resolved'])
def test_author_reply_reopens(status):
    svc, repo = _svc(_ticket(status=status))
    svc.reply_as_author(USER, 5, {'body': 'Nadal nie działa'}, [])
    kwargs = repo.add_message.call_args.kwargs
    assert kwargs['ticket_updates']['status'] == 'in_progress'
    assert kwargs['events'][0]['meta'] == {'from': status, 'to': 'in_progress', 'by': 'user'}


def test_author_reply_keeps_in_progress():
    svc, repo = _svc(_ticket(status='in_progress'))
    svc.reply_as_author(USER, 5, {'body': 'Dodam jeszcze'}, [])
    assert 'status' not in repo.add_message.call_args.kwargs['ticket_updates']


def test_closed_ticket_reopens_only_within_14_days():
    svc, _ = _svc(_ticket(status='closed', closed_at=datetime.utcnow() - timedelta(days=20)))
    with pytest.raises(ConflictError):
        svc.reply_as_author(USER, 5, {'body': 'hej'}, [])
    svc, repo = _svc(_ticket(status='closed', closed_at=datetime.utcnow() - timedelta(days=2)))
    svc.reply_as_author(USER, 5, {'body': 'hej'}, [])
    assert repo.add_message.call_args.kwargs['ticket_updates']['status'] == 'in_progress'


def test_confirm_only_from_resolved():
    svc, _ = _svc(_ticket(status='in_progress'))
    with pytest.raises(ConflictError):
        svc.confirm_fixed(USER, 5)
    svc, repo = _svc(_ticket(status='resolved'))
    svc.confirm_fixed(USER, 5)
    updates, events = repo.apply_changes.call_args.args[1:]
    assert updates['status'] == 'closed' and updates['close_reason'] == 'confirmed'


def test_author_cannot_fetch_internal_attachment():
    svc, repo = _svc()
    repo.get_attachment.return_value = {'created_by': USER.id, 'is_internal': True}
    with pytest.raises(NotFoundError):
        svc.attachment_for(USER, 1, is_agent=False)
    assert svc.attachment_for(AGENT, 1, is_agent=True)


# ── agent side ───────────────────────────────────────────────────────────────

def test_first_public_reply_takes_the_ticket_and_stamps_first_response():
    svc, repo = _svc(_ticket(status='seen'))
    svc.admin_reply(AGENT, 5, {'body': 'Sprawdzam'}, [])
    updates = repo.add_message.call_args.kwargs['ticket_updates']
    assert updates['status'] == 'in_progress'
    assert updates['first_response_at'] == 'NOW'
    assert updates['last_admin_activity_at'] == 'NOW'


def test_internal_note_is_invisible_bookkeeping():
    svc, repo = _svc(_ticket(status='seen'))
    svc.admin_reply(AGENT, 5, {'body': 'notatka', 'is_internal': 'true'}, [])
    kwargs = repo.add_message.call_args.kwargs
    assert kwargs['is_internal'] is True
    assert 'last_admin_activity_at' not in kwargs['ticket_updates']
    assert 'status' not in kwargs['ticket_updates']
    with pytest.raises(ValidationError):
        svc.admin_reply(AGENT, 5, {'body': 'x', 'is_internal': '1', 'status': 'resolved'}, [])


def test_submit_as_resolved_and_closed():
    svc, repo = _svc(_ticket(status='in_progress', first_response_at=datetime(2026, 10, 2)))
    svc.admin_reply(AGENT, 5, {'body': 'Naprawione', 'status': 'resolved'}, [])
    updates = repo.add_message.call_args.kwargs['ticket_updates']
    assert updates['status'] == 'resolved' and updates['resolved_at'] == 'NOW'
    assert 'first_response_at' not in updates

    svc, repo = _svc(_ticket(status='in_progress'))
    svc.admin_update(AGENT, 5, {'status': 'closed', 'close_reason': 'declined'})
    updates, events = repo.apply_changes.call_args.args[1:]
    assert updates['close_reason'] == 'declined' and events[0]['meta']['reason'] == 'declined'


def test_admin_cannot_set_new_or_garbage():
    svc, _ = _svc(_ticket())
    for bad in ({'status': 'new'}, {'status': 'nope'}, {'priority': 'p0'}, {'assigned_to': 999}):
        with pytest.raises(ValidationError):
            svc.admin_update(AGENT, 5, bad)


def test_opening_a_new_ticket_marks_it_seen():
    svc, repo = _svc(_ticket(status='new', context={}, requester_name='A', requester_email='a@x',
                             requester_role='stylist', requester_role_label='Stylistka', assignee_name=None,
                             resolved_at=None, last_user_activity_at=None, last_admin_activity_at=None))
    repo.list_attachments.return_value = []
    repo.list_messages.return_value = []
    repo.requester_history.return_value = []
    svc.admin_get(AGENT, 5)
    updates, events = repo.apply_changes.call_args.args[1:]
    assert updates['status'] == 'seen'
    repo.mark_read.assert_called_with(5, 'admin')
