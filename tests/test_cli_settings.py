from __future__ import annotations

import json

from promptwizard.cli import main


def test_config_set_writes_settings(tmp_path, capsys):
    code = main(
        [
            "config",
            "--set",
            "theme=dark",
            "--set",
            "provider=offline",
            "--set",
            "model=demo",
            "--lang",
            "en",
            "--home",
            str(tmp_path),
        ]
    )
    assert code == 0
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["theme"] == "dark"
    assert saved["provider"] == "offline"
    assert saved["model"] == "demo"
    capsys.readouterr()


def test_config_set_rejects_a_missing_value(tmp_path, capsys):
    assert main(["config", "--set", "theme", "--lang", "en", "--home", str(tmp_path)]) == 1
    assert "Error:" in capsys.readouterr().out


def test_config_set_rejects_an_unknown_key(tmp_path, capsys):
    assert main(["config", "--set", "nonsense=1", "--lang", "en", "--home", str(tmp_path)]) == 1
    assert "Error:" in capsys.readouterr().out


def test_models_command_lists_the_model(tmp_path, capsys):
    code = main(["models", "--provider", "offline", "--lang", "en", "--home", str(tmp_path)])
    assert code == 0
    assert "deterministic-stub" in capsys.readouterr().out


def test_saved_theme_is_reloaded(tmp_path, capsys):
    main(["config", "--set", "theme=dark", "--lang", "en", "--home", str(tmp_path)])
    capsys.readouterr()
    assert main(["config", "--lang", "en", "--home", str(tmp_path)]) == 0
    assert '"theme": "dark"' in capsys.readouterr().out
