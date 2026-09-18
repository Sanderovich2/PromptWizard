"""Locale catalogs (RU/EN) shipped as package data.

Kept as a package (with this ``__init__``) so :func:`importlib.resources.files`
can address it as ``promptwizard.locales`` both from a source checkout and from
an installed wheel.
"""

from __future__ import annotations

__all__ = ["CATALOGS"]

#: Locale codes that ship a catalog. Mirrors :data:`promptwizard.i18n.LANGUAGES`.
CATALOGS: tuple[str, ...] = ("ru", "en")
