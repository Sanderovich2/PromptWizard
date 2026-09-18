"""PromptWizard - analyze a prompt, ask what is missing, rewrite it better."""

from __future__ import annotations

__all__ = ["__version__", "main"]

__version__ = "0.1.0"
__app_name__ = "PromptWizard"


def __getattr__(name: str):  # pragma: no cover - trivial lazy import
    """Import :func:`promptwizard.cli.main` lazily so ``import promptwizard`` stays cheap.

    Keeping the CLI import out of ``__init__`` also means importing the package
    never touches tkinter, argparse or the network.
    """
    if name == "main":
        from promptwizard.cli import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
