from __future__ import annotations
from typing import Mapping
from promptwizard.analyzer import append_extra_instructions
from promptwizard.errors import LLMResponseError
from promptwizard.i18n import Translator
from promptwizard.parsing import as_str, extract_json
__all__ = ['build_system_prompt', 'build_user_prompt', 'parse']

def build_system_prompt(translator: Translator, target_language: str, extra: str='') -> str:
    schema = '{"translated_prompt":"<the prompt in the target language>","language":"ru|en|other"}'
    target = translator.get(f'language.{target_language}', default=translator('language.unknown'))
    system = f'You are PromptWizard. Translate the user\'s prompt into {target} without changing what it asks for, and answer with STRICT JSON only:\n' + schema + f"""\nRules:\n- Keep every constraint, number, name, path and formatting hint of the original.\n- Translate only: do not answer the prompt, do not improve it, add nothing.\n- Write "translated_prompt" in {target}.\n- Set "language" to the language of the translation."""
    return append_extra_instructions(system, extra)

def build_user_prompt(prompt: str) -> str:
    return 'Translate this prompt:\n<PROMPT>\n' + prompt + '\n</PROMPT>'

def parse(text: str, language: str='unknown') -> str:
    data = extract_json(text)
    if not isinstance(data, Mapping):
        raise LLMResponseError('translate: the model did not return a JSON object', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'api'})
    translated = as_str(data.get('translated_prompt')) or as_str(data.get('prompt'))
    if not translated.strip():
        raise LLMResponseError('translate: the model returned no translation', hint_key='error.provider.bad_response', hint_kwargs={'provider': 'api'})
    return translated
