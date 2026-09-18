from __future__ import annotations
from promptwizard.i18n import DEFAULT_LANGUAGE, available_languages, detect_text_language, get_translator, load_catalog, normalize_language

def test_both_catalogs_ship():
    assert {'ru', 'en'} <= set(available_languages())

def test_catalogs_cover_the_same_keys():
    assert set(load_catalog('ru')) == set(load_catalog('en'))

def test_normalize_language_accepts_the_usual_spellings():
    assert normalize_language('ru-RU') == 'ru'
    assert normalize_language('EN_us') == 'en'
    assert normalize_language('Русский') == 'ru'
    assert normalize_language(None) == DEFAULT_LANGUAGE
    assert normalize_language('klingon') == DEFAULT_LANGUAGE

def test_detect_text_language_is_script_based():
    assert detect_text_language('Привет, как дела?') == 'ru'
    assert detect_text_language('Hello there, how are you?') == 'en'
    assert detect_text_language('123 ... !!!') == 'unknown'

def test_translator_formats_and_falls_back_to_the_key():
    translator = get_translator('en')
    assert translator('app.name') == 'PromptWizard'
    assert translator('does.not.exist') == 'does.not.exist'
    assert translator('run.score', score=42) == 'Clarity score: 42/100'

def test_translator_returns_the_template_when_a_placeholder_is_missing():
    translator = get_translator('en')
    assert translator('run.score') == 'Clarity score: {score}/100'

def test_every_catalog_template_has_a_valid_format_spec():

    class AnyValue(dict):

        def __missing__(self, key):
            return 'v'
    for lang in ('ru', 'en'):
        for key, template in load_catalog(lang).items():
            if '{' not in template:
                continue
            try:
                rendered = template.format_map(AnyValue())
            except (ValueError, KeyError, IndexError) as exc:
                raise AssertionError(f'{lang}:{key} has an invalid format spec: {exc}') from exc
            assert '{' not in rendered, f'{lang}:{key} left a placeholder unrendered: {rendered!r}'
