"""Dotted-key translator with a per-bot override layer.

Lookup order for `t("catalog.buy")`:
  1. `texts:` in the bot's own config.yaml  (niche wording wins)
  2. `<lang>.yml` in this package           (language pack)
  3. `en.yml`                               (fallback)
  4. the key itself                         (never crashes on a typo)
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any, Mapping

import yaml

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
FALLBACK_LANG = "en"


@functools.lru_cache(maxsize=16)
def _load_pack(lang: str) -> dict[str, Any]:
    path = HERE / f"{lang}.yml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - packs are ours
        log.error("i18n: %s is invalid YAML: %s", path, exc)
        return {}


def available_languages() -> list[str]:
    return sorted(p.stem for p in HERE.glob("*.yml"))


def _dig(tree: Mapping[str, Any], key: str) -> str | None:
    node: Any = tree
    for part in key.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


class Translator:
    """Callable translator bound to one language and one bot's overrides."""

    __slots__ = ("lang", "_overrides", "_pack", "_fallback")

    def __init__(self, lang: str = "ru", overrides: Mapping[str, str] | None = None) -> None:
        self.lang = lang
        self._overrides = dict(overrides or {})
        self._pack = _load_pack(lang)
        self._fallback = _load_pack(FALLBACK_LANG) if lang != FALLBACK_LANG else self._pack

    def __call__(self, key: str, /, **kwargs: Any) -> str:
        template = (
            self._overrides.get(key)
            or _dig(self._pack, key)
            or _dig(self._fallback, key)
        )
        if template is None:
            log.warning("i18n: missing key %r for lang %r", key, self.lang)
            return key
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError) as exc:
            # A bad override must not take the bot down mid-sale.
            log.warning("i18n: cannot format %r (%s)", key, exc)
            return template

    def get(self, key: str, default: str = "", **kwargs: Any) -> str:
        template = (
            self._overrides.get(key)
            or _dig(self._pack, key)
            or _dig(self._fallback, key)
        )
        if template is None:
            return default
        return self(key, **kwargs)

    def has(self, key: str) -> bool:
        return (
            key in self._overrides
            or _dig(self._pack, key) is not None
            or _dig(self._fallback, key) is not None
        )


__all__ = ["Translator", "available_languages", "FALLBACK_LANG"]
