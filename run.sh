#!/usr/bin/env sh
# Run PromptWizard on Linux/macOS without compiling anything.
set -e
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python -m promptwizard "$@"
fi

exec python3 -m promptwizard "$@"
