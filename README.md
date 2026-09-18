# PromptWizard

Analyze a prompt, ask the questions that are actually missing, and rewrite it into something a
model understands better. Runs on Windows, Linux and macOS, with a CLI (+ interactive mode) and an
optional tkinter window, using **free LLM providers only** — a local Ollama, or the free tiers of
Gemini, Groq and OpenRouter — and a deterministic no-LLM mode when nothing is configured.

```
$ promptwizard "write about our product"

Issues and weak spots
Clarity score: 10/100
1. [high] Missing detail: Too little information to act on
2. [high] Ambiguity: Vague wording leaves room for several readings
3. [high] Output format: The expected output format is not specified
...

Clarifying questions
1. In what form should the answer come?      -> short summary | bullet list | table | code | free text
2. Who will read the answer?                 -> colleague | client | beginner | expert

Improved prompt
Task:
write about our product

Audience:
small business owners who are new to the product

Output format:
a short landing-page summary, 150 words, no bullet lists

What changed and why
- Specified the expected output format.
- Stated who the answer is for.

Mode: LLM
```

## What it does

1. **Takes** a prompt (argument, file, stdin, or the interactive editor).
2. **Analyzes** it: clarity, structure, ambiguity, missing detail, weak phrasing, constraints,
   output format, audience, examples, scope, tone, context.
3. **Asks** the clarifying questions — **all at once**, never one by one.
4. **Rewrites** the prompt in the *language of the original prompt*, and explains every change in
   the *UI language*.

Every run is saved to a JSONL session history, and the result can be exported to `.md`, `.txt` or
`.json`.

## Install

Python 3.10+.

```bash
git clone https://github.com/Sanderovich2/PromptWizard.git
cd PromptWizard
python -m venv .venv
# Windows
.venv\Scripts\python.exe -m pip install -e ".[dev]"
# Linux / macOS
.venv/bin/python -m pip install -e ".[dev]"
```

No mandatory third-party dependencies: the core is standard library only (`urllib` for HTTP,
`argparse` for the CLI, `tkinter` for the GUI).

### tkinter

The GUI needs `tkinter`. It ships with the python.org installers on Windows and macOS. On Linux you
usually need the system package:

```bash
sudo apt-get install -y python3-tk     # Debian / Ubuntu
sudo dnf install -y python3-tkinter    # Fedora
```

The CLI works without it; only `promptwizard gui` needs it.

## Run

```bash
promptwizard "write about our product"           # analyze, ask, rewrite
promptwizard                                     # interactive: paste the prompt, empty line ends it
promptwizard --file prompt.txt                   # read the prompt from a file
cat prompt.txt | promptwizard --lang en          # from stdin
promptwizard --no-questions "summarize this"     # skip the questions
promptwizard --out result.md --format md "..."   # export the result
promptwizard --json "..."                        # machine-readable output
promptwizard gui                                 # the tkinter window
promptwizard providers                           # what is configured and reachable
promptwizard sessions                            # the session history
promptwizard sessions --show 20260918-160401-1a2b3c
promptwizard config --init                       # write a default config.json
```

Without an installed console script, use `python -m promptwizard ...` or the launchers:

| Platform | Launcher |
|---|---|
| Windows | `run.bat "your prompt"` |
| Linux / macOS | `./run.sh "your prompt"` |

## Providers (free only)

| Provider | Kind | Key | Where to get it |
|---|---|---|---|
| `ollama` | local, no key by default | — | [ollama.com](https://ollama.com) — `ollama pull llama3.2` |
| `gemini` | Google AI free tier | `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `groq` | free tier | `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| `openrouter` | models with the `:free` suffix | `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `offline` | deterministic, no LLM at all | — | built in |
| `openai_compatible` | any other free OpenAI-compatible tier | `OPENAI_API_KEY` | your provider |

Pick one per run:

```bash
promptwizard --provider groq --model llama-3.3-70b-versatile "..."
promptwizard --provider gemini "..."
promptwizard --provider openai_compatible --base-url https://api.cerebras.ai/v1 --model llama3.1-8b "..."
promptwizard --provider offline "..."          # rules only, no model call
```

`promptwizard providers` prints every configured provider, whether it is reachable, and — when the
provider exposes it — the models your key can use. **If the provider is unreachable, the run does not
fail**: the affected step falls back to the deterministic template, and the reason is shown.

Free-tier model ids change often, so they are **not** scattered through the code: they live in one
table, `PROVIDER_DEFAULTS` in `promptwizard/config.py`, and every one of them can be overridden with
`--model` or in `config.json`.

### Adding a free tier without touching the code

```json
{
  "provider": "cerebras",
  "providers": {
    "cerebras": {
      "base_url": "https://api.cerebras.ai/v1",
      "model": "llama3.1-8b",
      "api_key_env": "CEREBRAS_API_KEY"
    }
  }
}
```

Any provider that speaks the OpenAI `/chat/completions` dialect works this way.

## Keys and configuration

Keys are **never** hardcoded and never printed. Resolution order: the provider's environment
variable (including a `.env` file), then the `api_key` field of that provider in `config.json`.

```bash
cp .env.example .env      # then fill in the keys you actually use
```

Precedence, lowest to highest: built-in defaults → `config.json` → `.env` → environment → CLI flags.

`~/.promptwizard/config.json`:

```json
{
  "lang": "ru",
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "temperature": 0.3,
  "max_tokens": 1200,
  "timeout": 60,
  "max_questions": 6
}
```

Relevant environment variables: `PROMPTWIZARD_HOME`, `PROMPTWIZARD_LANG`, `PROMPTWIZARD_PROVIDER`,
`PROMPTWIZARD_MODEL`, `PROMPTWIZARD_TEMPERATURE`, `PROMPTWIZARD_MAX_TOKENS`, `PROMPTWIZARD_TIMEOUT`,
`PROMPTWIZARD_MAX_QUESTIONS`, `OLLAMA_HOST`, plus the per-provider `*_API_KEY`.

## Languages

Two independent languages:

- **UI language** — `--lang ru|en`, `"lang"` in the config, or the switch inside the GUI — decides
  the menus, the questions, the issue wording and the explanations.
- **Prompt language** — detected from your prompt — decides the language of the rewritten prompt,
  because that text is fed to a model and has to match your material.

A Russian prompt rewritten with `--lang en` still produces a Russian prompt, with English
explanations.

## Session history

Every run is appended to `~/.promptwizard/sessions/sessions.jsonl` — one JSON object per line, so a
crashed run cannot corrupt earlier ones. `--no-save` skips it.

```bash
promptwizard sessions --limit 10
promptwizard sessions --show <id>
promptwizard sessions --json
```

## Build a standalone binary

PyInstaller recipe: [`packaging/promptwizard.spec`](packaging/promptwizard.spec) (kept in the repo
on purpose — it is the build recipe).

```bash
# Windows -> dist\promptwizard.exe
packaging\build.bat

# Linux / macOS -> dist/promptwizard
./packaging/build.sh
```

Two Windows entry points, as required:

| File | What it is |
|---|---|
| `run.bat` | runs the app without compiling, using the venv (or `py -3`) |
| `dist\promptwizard.exe` | the compiled application, from `packaging\build.bat` |

On Linux/macOS run it with `python -m promptwizard`, or use the compiled `dist/promptwizard`.

CI (`.github/workflows/ci.yml`) runs the test suite on Windows, Linux and macOS, and builds the
binary on all three.

## Tests and evals

```bash
python -m pytest -q            # gate tests: deterministic, offline, fast
PROMPTWIZARD_EVAL=1 python -m pytest evals -q   # quality evals: real provider calls
```

The gate tests never touch the network (providers are replaced with a fake) and never cost money.
The evals do call a real provider, so they are skipped unless `PROMPTWIZARD_EVAL=1` is set and a
provider actually answers.

## Project layout

```
promptwizard/
  cli.py          command line: dispatch, flags, output
  gui.py          optional tkinter window (two phases: analyze, then rewrite)
  pipeline.py     Session: analyze -> ask -> rewrite, with the deterministic fallback
  analyzer.py     issue detection (LLM JSON + deterministic rules)
  questions.py    the question batch (LLM JSON + rules)
  rewriter.py     the improved prompt and the change log
  parsing.py      lenient JSON extraction from model answers
  llm/            provider contract + ollama, gemini, groq, openrouter, offline
  storage.py      JSONL session history
  export.py       md / txt / json rendering
  i18n.py         RU/EN UI language
  locales/        ru.json, en.json
tests/            gate tests (no network)
evals/            quality evals (real provider, opt-in)
packaging/        PyInstaller spec and build scripts
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'tkinter'` | This Python build has no Tk. Use the CLI, or install a python.org build / `python3-tk`. |
| `ollama: model 'llama3.2' is not pulled locally` | `ollama pull llama3.2` |
| `cannot reach the provider` | Start `ollama serve`, or check the network; or use `--provider offline`. |
| `no API key found for groq` | Set `GROQ_API_KEY`, or put it in `.env`. |
| `rate limit / quota exceeded` | Wait, or switch with `--provider`. |

## Русский

PromptWizard принимает промт, анализирует его (структура, ясность, неоднозначности, недостающие
детали, слабые формулировки), задаёт уточняющие вопросы **сразу пачкой**, переписывает промт
(на языке исходного промта) и объясняет правки (на языке интерфейса).

```bash
promptwizard "напиши про наш продукт"      # запуск
promptwizard --lang ru --provider groq     # провайдер и язык интерфейса
promptwizard gui                            # окно на tkinter
packaging\build.bat                         # сборка .exe под Windows
```

Провайдеры — только бесплатные: локальный Ollama, бесплатные тарифы Gemini / Groq / OpenRouter и
офлайн-режим без LLM. Ключи задаются переменными окружения или файлом `.env` и не попадают в код.
История сессий — `~/.promptwizard/sessions/sessions.jsonl`.

## License

MIT — see [LICENSE](LICENSE).
