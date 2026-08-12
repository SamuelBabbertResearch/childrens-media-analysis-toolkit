"""
ui/reference_css.py — load the reference stylesheets and use them directly.

`ui/reference/*.css` is extracted verbatim from the supplied HTML. This module
makes it usable as-is rather than transcribed, which is the point: every round
of hand-copying values out of that CSS lost or changed something, and the
losses were invisible until someone looked at the two side by side.

What it does:

  * resolves `var(--name)` against the `:root` block, since neither Qt's rich
    text engine nor Qt Style Sheets implement custom properties;
  * exposes named rule blocks so a caller can take the reference's `.data-table`
    without also taking its `body { background: #383838 }`, which is the dark
    backdrop the mockup is *photographed* against, not part of the design.

What it deliberately does NOT do: drive the widget chrome. Qt Style Sheets are
not CSS — different selector language, no flexbox or grid, no box-shadow, no
`:nth-child`. A QToolBar cannot be styled by `.top-toolbar` under any amount of
plumbing, so the chrome is still a translation. The report pane is the opposite
case: QTextBrowser renders real HTML, so there the reference CSS is used as
the stylesheet rather than reimplemented.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

REFERENCE_DIR = Path(__file__).parent / "reference"

_VAR_DEF = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")
_VAR_USE = re.compile(r"var\(\s*--([\w-]+)\s*\)")
_ROOT_BLOCK = re.compile(r":root\s*\{(.*?)\}", re.S)
_COMMENT = re.compile(r"/\*.*?\*/", re.S)


@lru_cache(maxsize=None)
def _raw(name: str) -> str:
    return (REFERENCE_DIR / f"{name}.css").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def variables(name: str = "library") -> dict[str, str]:
    """The `:root` custom properties, as a plain mapping."""
    css = _COMMENT.sub("", _raw(name))
    root = _ROOT_BLOCK.search(css)
    if not root:
        return {}
    return {k: v.strip() for k, v in _VAR_DEF.findall(root.group(1))}


@lru_cache(maxsize=None)
def stylesheet(name: str = "library") -> str:
    """The reference stylesheet with `var()` resolved and comments stripped."""
    css = _COMMENT.sub("", _raw(name))
    css = _ROOT_BLOCK.sub("", css, count=1)
    values = variables(name)

    def resolve(match: re.Match) -> str:
        return values.get(match.group(1), "inherit")

    # Two passes: a few reference variables are defined in terms of others.
    for _ in range(2):
        css = _VAR_USE.sub(resolve, css)
    return css.strip()


def rules(selectors, name: str = "library") -> str:
    """The reference's own rules for *selectors*, in their original order.

    Selector match is on the text before `{`, so passing "data-table" picks up
    `.data-table`, `.data-table th` and `.data-table td` together — the whole
    definition of that component as the reference wrote it.
    """
    wanted = tuple(selectors)
    out: list[str] = []
    for block in re.finditer(r"([^{}]+)\{([^{}]*)\}", stylesheet(name)):
        selector = " ".join(block.group(1).split())
        if any(w in selector for w in wanted):
            out.append(f"{selector} {{{block.group(2).strip()}}}")
    return "\n".join(out)
