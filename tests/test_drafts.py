from __future__ import annotations

import json

from promptwizard.config import Config
from promptwizard.drafts import DRAFT_LIMIT, add_draft, clear_drafts, drafts_file, list_drafts, remove_draft


def test_drafts_start_empty(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    assert list_drafts(config) == []


def test_a_draft_is_remembered_newest_first(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    add_draft(config, "first")
    add_draft(config, "second")
    assert list_drafts(config) == ["second", "first"]
    assert json.loads(drafts_file(config).read_text(encoding="utf-8")) == ["second", "first"]


def test_the_same_prompt_moves_to_the_front(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    add_draft(config, "first")
    add_draft(config, "second")
    add_draft(config, "first")
    assert list_drafts(config) == ["first", "second"]


def test_blank_prompts_are_ignored(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    add_draft(config, "   ")
    assert list_drafts(config) == []


def test_the_list_is_capped(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    for index in range(DRAFT_LIMIT + 5):
        add_draft(config, f"prompt-{index}")
    items = list_drafts(config)
    assert len(items) == DRAFT_LIMIT
    assert items[0] == f"prompt-{DRAFT_LIMIT + 4}"


def test_a_draft_can_be_removed_and_cleared(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    add_draft(config, "first")
    add_draft(config, "second")
    assert remove_draft(config, "first") == ["second"]
    assert clear_drafts(config) == []
    assert list_drafts(config) == []


def test_a_broken_drafts_file_does_not_explode(tmp_path):
    config = Config.load(home=tmp_path, dotenv=False)
    drafts_file(config).write_text("{not json", encoding="utf-8")
    assert list_drafts(config) == []
