"""Pipeline: the full run, the deterministic fallback, and the offline mode."""

from __future__ import annotations

import json

from promptwizard.pipeline import Session, run

ANALYSIS = json.dumps(
    {
        "language": "en",
        "score": 40,
        "summary": "weak",
        "issues": [{"category": "format", "severity": "high", "title": "No format", "detail": "add one"}],
    }
)
QUESTIONS = json.dumps(
    {
        "questions": [
            {
                "id": "format",
                "text": "Which format?",
                "why": "because",
                "kind": "choice",
                "options": ["table", "list"],
            }
        ]
    }
)
REWRITE = json.dumps(
    {
        "improved_prompt": "Task:\nDo the thing",
        "changes": [{"what": "Added format", "why": "so it is unambiguous"}],
        "language": "en",
    }
)


def test_full_run_uses_the_model_and_asks_once(config, translator, make_provider):
    provider = make_provider([ANALYSIS, QUESTIONS, REWRITE])
    calls: list[list[str]] = []

    def ask(questions):
        calls.append([question.id for question in questions])
        return {question.id: "table" for question in questions}

    result = run(config, translator, "Do the thing", provider=provider, ask=ask)

    assert result.mode == "llm"
    assert result.rewrite is not None
    assert result.rewrite.improved_prompt.startswith("Task:")
    assert result.answers == {"format": "table"}
    assert calls == [["format"]]
    assert len(provider.requests) == 3
    assert "Do the thing" in provider.requests[0].prompt
    assert provider.requests[0].json_mode is True


def test_unparseable_answers_fall_back_to_the_template(config, translator, make_provider):
    provider = make_provider(["not json at all", "still not json", "nope"])
    result = run(config, translator, "Do the thing", provider=provider)

    assert result.mode == "template"
    assert result.warnings
    assert result.rewrite is not None
    assert result.analysis.issues


def test_provider_errors_fall_back_instead_of_raising(config, translator, make_provider):
    from promptwizard.errors import MissingCredentials

    provider = make_provider()

    def explode(request):
        raise MissingCredentials("fake: no API key found", hint_key="error.provider.missing_key", hint_kwargs={"provider": "fake", "env_var": "FAKE_API_KEY"})

    provider.complete = explode  # type: ignore[method-assign]
    result = run(config, translator, "Do the thing", provider=provider)

    assert result.mode == "template"
    assert any("FAKE_API_KEY" in warning for warning in result.warnings)


def test_offline_provider_never_calls_a_model(config, translator):
    config.provider = "offline"
    result = run(config, translator, "Do the thing")

    assert result.mode == "offline"
    assert result.rewrite is not None
    assert result.provider == "offline"


def test_no_questions_skips_the_question_step(config, translator, make_provider):
    provider = make_provider([ANALYSIS, REWRITE])
    result = run(config, translator, "Do the thing", provider=provider, no_questions=True)

    assert result.questions == ()
    assert len(provider.requests) == 2
    assert result.rewrite is not None


def test_session_is_reusable_and_caches_steps(config, translator, make_provider):
    provider = make_provider([ANALYSIS, QUESTIONS, REWRITE])
    session = Session(config, translator, "Do the thing", provider=provider)

    first = session.analyze()
    assert session.analyze() is first
    questions = session.make_questions()
    assert session.make_questions() is questions
    session.set_answers({"format": "table"})
    assert session.run_rewrite().improved_prompt.startswith("Task:")
    assert session.mode() == "llm"


def test_result_round_trips_through_json(config, translator, make_provider):
    provider = make_provider([ANALYSIS, QUESTIONS, REWRITE])
    result = run(config, translator, "Do the thing", provider=provider)
    restored = type(result).from_dict(json.loads(json.dumps(result.to_dict())))

    assert restored.id == result.id
    assert restored.analysis.issues == result.analysis.issues
    assert restored.rewrite is not None
    assert restored.rewrite.improved_prompt == result.rewrite.improved_prompt
