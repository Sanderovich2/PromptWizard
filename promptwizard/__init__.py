from __future__ import annotations
__all__ = ['__version__', 'main']
__version__ = '0.3.3'
__app_name__ = 'PromptWizard'

def __getattr__(name: str):
    if name == 'main':
        from promptwizard.cli import main
        return main
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
