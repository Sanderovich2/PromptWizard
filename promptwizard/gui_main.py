from __future__ import annotations

from promptwizard.config import Config
from promptwizard.i18n import get_translator
from promptwizard.webui import launch

__all__ = ["main"]


def main() -> int:
    config = Config.load()
    return launch(config, get_translator(config.lang))


if __name__ == "__main__":
    raise SystemExit(main())
