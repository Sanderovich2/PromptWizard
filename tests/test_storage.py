from __future__ import annotations
from promptwizard.storage import get_session, list_sessions, save_session, sessions_file

def _record(identifier: str) -> dict[str, object]:
    return {'id': identifier, 'finished_at': '2026-01-01T00:00:00+03:00', 'provider': 'offline', 'model': '-', 'prompt_language': 'en'}

def test_empty_store_has_nothing(config):
    assert list_sessions(config) == []
    assert get_session(config, 'nope') is None

def test_save_then_list_newest_first(config):
    save_session(config, _record('a'))
    save_session(config, _record('b'))
    assert sessions_file(config).exists()
    assert [record['id'] for record in list_sessions(config)] == ['b', 'a']
    assert [record['id'] for record in list_sessions(config, limit=1)] == ['b']

def test_lookup_by_id_prefix(config):
    save_session(config, _record('20260101-000000-abcdef'))
    assert get_session(config, '20260101') is not None
    assert get_session(config, '20260101-000000-abcdef') is not None
    assert get_session(config, '') is None

def test_broken_lines_are_skipped(config):
    path = sessions_file(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{not json}\n{"id": "ok"}\n\n', encoding='utf-8')
    assert [record['id'] for record in list_sessions(config)] == ['ok']
