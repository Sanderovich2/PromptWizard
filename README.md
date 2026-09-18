# PromptWizard

Analyze a prompt, ask the questions that are actually missing, and rewrite it into something a
model understands better. Runs on Windows, Linux and macOS, with a CLI (+ interactive mode) and an
optional tkinter window, using **free LLM providers only**. It works with **no API key and no
setup** out of the box, and can also use a local Ollama, the free tiers of Gemini, Groq and
OpenRouter, or a deterministic no-LLM mode.

Пошаговый туториал по запуску на русском — в разделе [«Как запустить (RU)»](#как-запустить-ru) ниже.

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
promptwizard gui                                 # the interface (local web UI in a native window)
promptwizard gui --tk                            # the older tkinter window
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

## Interface

`promptwizard gui` opens the interface: a local web UI shown in a native window (pywebview), or in
the default browser when that is unavailable. It is a four-step workbench - Prompt, Analysis,
Questions, Result - with a numbered step rail, the issues as an editorial list, the whole question
batch with an answer field and option chips under each question, and the rewritten prompt as the
final draft. Ctrl+Enter runs the current step.

The interface talks to the same Python core over a small local HTTP API (`/api/state`,
`/api/analyze`, `/api/rewrite`), bound to 127.0.0.1 only. For the native window install the optional
dependency:

```bash
python -m pip install -e ".[web]"
```

Without it `gui` still works and opens the browser. `gui --tk` keeps the older tkinter window.

## Providers (free only)

| Provider | Kind | Key | Where to get it |
|---|---|---|---|
| `pollinations` | keyless community endpoint (**default**) | none | works immediately, no account |
| `ollama` | local, no key by default | — | [ollama.com](https://ollama.com) — `ollama pull llama3.2` |
| `gemini` | Google AI free tier | `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `groq` | free tier | `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| `openrouter` | models with the `:free` suffix | `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `offline` | deterministic, no LLM at all | — | built in |
| `openai_compatible` | any other free OpenAI-compatible tier | `OPENAI_API_KEY` | your provider |

### No keys at all

`pollinations` is the default provider: a keyless, community-run endpoint. After install,
`promptwizard "..."` produces a real rewrite with no account, no key and no local server.

```bash
promptwizard "write about our product"    # just works
promptwizard providers                     # shows it as reachable
```

It is free, therefore rate-limited. When it pushes back, the run does not fail: it degrades to the
deterministic template and says why, and you can switch provider for the next run:

| Want | Command |
|---|---|
| keyless (default) | `promptwizard "..."` |
| fully local, no network | `ollama pull llama3.2` then `promptwizard --provider ollama "..."` |
| a specific free tier | `promptwizard --provider groq --model llama-3.3-70b-versatile "..."` |
| no LLM at all (rules only) | `promptwizard --provider offline "..."` |

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
  "provider": "pollinations",
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

## Как запустить (RU)

Пошаговый туториал: установка, CLI, GUI, провайдеры, сборка. Ключи не нужны — по умолчанию
работает безключевой провайдер `pollinations` (см. [No keys at all](#no-keys-at-all)).

### 1. Установка

```bash
git clone https://github.com/Sanderovich2/PromptWizard.git
cd PromptWizard
python -m venv .venv
```

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"     # Windows
```

```bash
.venv/bin/python -m pip install -e ".[dev]"             # Linux / macOS
```

Нужен Python 3.10+. После установки доступны: команда `promptwizard`, лаунчеры `run.bat`
(Windows) / `run.sh` (Linux, macOS) и `python -m promptwizard`. Для GUI нужен tkinter: на Windows и
macOS он есть в установщиках с python.org, на Linux — пакет `python3-tk`.

### 2. Быстрый старт

```powershell
cd C:\path\to\PromptWizard
.\run.bat "напиши короткий текст про котиков"
```

Чтобы писать просто `promptwizard`, активируй окружение: `.\\.venv\\Scripts\\Activate.ps1`.

### 3. CLI

**Интерактивный режим** — самый полный: запусти `run.bat` без аргументов. Программа попросит
вставить промт (пустая строка завершает ввод), покажет проблемы, **задаст все уточняющие вопросы
сразу** (ответы — по одной строке, пустая строка = пропустить) и выдаст улучшенный промт с
объяснением правок. Вопросы задаются только в интерактивном терминале.

```powershell
.\run.bat "промт"                                       # сразу с промтом
.\run.bat --no-questions "промт"                        # без вопросов
.\run.bat --file prompt.txt                             # из файла
.\run.bat --lang ru --out result.md --format md "промт"  # экспорт в файл
.\run.bat --json "промт"                                # машинный вывод
.\run.bat --provider offline "промт"                    # совсем без сети
.\run.bat --help
```

| Флаг | Что делает |
|---|---|
| `--lang ru\|en` | язык интерфейса |
| `--provider <имя>` | pollinations / ollama / gemini / groq / openrouter / offline |
| `--model`, `--base-url` | переопределить модель или адрес провайдера |
| `--temperature`, `--max-tokens`, `--timeout` | параметры запроса |
| `--max-questions N` | сколько вопросов задавать (0 — ни одного) |
| `--no-questions`, `--no-save` | пропустить вопросы / не писать сессию |
| `--out FILE --format md\|txt\|json` | сохранить результат |
| `--json` | результат в JSON |
| `--home`, `--config` | где искать `~/.promptwizard` и `config.json` |

Служебные команды:

```powershell
.\run.bat providers                  # кто доступен и какие модели
.\run.bat sessions                   # история прогонов
.\run.bat sessions --show <id>       # один прогон целиком
.\run.bat config --init              # создать config.json
.\run.bat config                     # текущие настройки (ключи скрыты)
.\run.bat --version
```

### 4. Интерфейс

```powershell
.\run.bat gui          # локальный веб-интерфейс в нативном окне (или в браузере)
.\run.bat gui --tk     # прежнее окно на tkinter
```

Четыре шага: Промт → Анализ → Вопросы → Результат. Слева рельс шагов, внизу строка состояния.
`Ctrl + Enter` запускает текущий шаг. Отвечать на все вопросы не обязательно.

Пока идёт запрос к модели, кнопки неактивны, в статусе «Работаю...». Если провайдер недоступен,
окно не падает: показывает ошибку и её причину.

### 5. Провайдеры

| Что нужно | Как |
|---|---|
| Без ключей (по умолчанию) | `.\run.bat "промт"` — `pollinations` |
| Совсем без сети | `--provider offline` — только правила, без модели |
| Полностью локально | установить [Ollama](https://ollama.com), `ollama pull llama3.2`, затем `--provider ollama` |
| Ключевой free-tier | скопировать `.env.example` в `.env`, вписать ключ (например `GROQ_API_KEY`), затем `--provider groq --model llama-3.3-70b-versatile` |

Ключи читаются из переменных окружения и `.env` и никогда не попадают в код.

### 6. Сборка `.exe` (Windows)

```powershell
.\packaging\build.bat
.\dist\promptwizard.exe "промт"
.\dist\promptwizard.exe gui
```

### 7. Linux / macOS

```bash
./run.sh "промт"
./run.sh gui
./packaging/build.sh
sudo apt-get install -y python3-tk     # для GUI, если tkinter нет
```

### 8. Если что-то не так

| Симптом | Что делать |
|---|---|
| `ModuleNotFoundError: No module named 'tkinter'` | этот Python без Tk: используй CLI, либо поставь сборку с python.org / пакет `python3-tk` |
| `no API key found for groq` | ключ в `.env`, либо `--provider pollinations` |
| `cannot reach the provider` | проверь сеть, либо `--provider offline` |
| Вопросы не задаются | терминал не интерактивный: промт пришёл из аргумента или из пайпа |
| «Режим: template» | провайдер упёрся в лимит: повтори запуск или смени `--provider` |

Данные лежат в `~/.promptwizard/`: `config.json` и `sessions/sessions.jsonl` (история прогонов).

## License

MIT — see [LICENSE](LICENSE).
