from __future__ import annotations
from promptwizard.cli import _split_command, main

def test_split_command_finds_the_command_after_flags():
    assert _split_command(['providers'])[0] == 'providers'
    assert _split_command(['--quiet', 'providers'])[0] == 'providers'
    assert _split_command(['--provider', 'groq', 'providers'])[0] == 'providers'
    assert _split_command(['--version'])[0] == 'version'
    assert _split_command(['write a summary'])[0] == 'run'
    assert _split_command(['--provider', 'groq', 'write a summary'])[0] == 'run'

def test_split_command_removes_the_command_token():
    command, rest = _split_command(['--quiet', 'providers', '--limit', '5'])
    assert command == 'providers'
    assert '--quiet' in rest and 'providers' not in rest

def test_offline_run_prints_the_result(tmp_path, capsys):
    code = main(['--lang', 'en', '--home', str(tmp_path), '--provider', 'offline', '--no-questions', 'Write something about cats'])
    assert code == 0
    out = capsys.readouterr().out
    assert 'Improved prompt' in out
    assert 'Mode: offline' in out

def test_run_saves_a_session_by_default(tmp_path, capsys):
    main(['--lang', 'en', '--home', str(tmp_path), '--provider', 'offline', '--no-questions', 'Write something about cats'])
    capsys.readouterr()
    assert (tmp_path / 'sessions' / 'sessions.jsonl').exists()
    assert main(['sessions', '--lang', 'en', '--home', str(tmp_path)]) == 0
    assert 'Saved sessions' in capsys.readouterr().out

def test_no_save_skips_the_session_log(tmp_path, capsys):
    main(['--lang', 'en', '--home', str(tmp_path), '--provider', 'offline', '--no-questions', '--no-save', 'Write something'])
    capsys.readouterr()
    assert not (tmp_path / 'sessions' / 'sessions.jsonl').exists()

def test_export_writes_a_markdown_file(tmp_path, capsys):
    target = tmp_path / 'out' / 'result.md'
    code = main(['--lang', 'en', '--home', str(tmp_path), '--provider', 'offline', '--no-questions', '--no-save', '--out', str(target), '--format', 'md', 'Write something'])
    assert code == 0
    assert target.exists()
    assert 'Improved prompt' in target.read_text(encoding='utf-8')

def test_json_flag_prints_machine_readable_output(tmp_path, capsys):
    import json
    code = main(['--lang', 'en', '--home', str(tmp_path), '--provider', 'offline', '--no-questions', '--no-save', '--json', 'Write something'])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index('{'):])
    assert payload['provider'] == 'offline'
    assert payload['rewrite']['improved_prompt']

def test_empty_prompt_is_an_error(tmp_path, capsys):
    code = main(['--lang', 'en', '--home', str(tmp_path), '--provider', 'offline', ''])
    assert code == 1
    assert 'Error:' in capsys.readouterr().out

def test_version_command(capsys):
    assert main(['--version']) == 0
    assert 'PromptWizard' in capsys.readouterr().out

def test_providers_command(tmp_path, capsys, monkeypatch):
    import promptwizard.cli as cli
    from promptwizard.llm.base import ProviderStatus
    monkeypatch.setattr(cli, 'describe_providers', lambda config: (ProviderStatus(name='pollinations', available=True, detail='keyless, reachable'), ProviderStatus(name='groq', available=False, detail='no API key found', requires_key=True)))
    assert main(['providers', '--lang', 'en', '--home', str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert 'Providers' in out
    assert 'pollinations' in out

def test_config_init_creates_the_file(tmp_path, capsys):
    assert main(['config', '--init', '--lang', 'en', '--home', str(tmp_path)]) == 0
    assert (tmp_path / 'config.json').exists()
    capsys.readouterr()

def test_config_show_prints_redacted_config(tmp_path, capsys):
    assert main(['config', '--lang', 'en', '--home', str(tmp_path)]) == 0
    assert '"provider"' in capsys.readouterr().out

def test_sessions_show_unknown_id(tmp_path, capsys):
    assert main(['sessions', '--show', 'nope', '--lang', 'en', '--home', str(tmp_path)]) == 1
    assert 'nope' in capsys.readouterr().out
