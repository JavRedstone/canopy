"""Render a course's learner-visible material as a downloadable, Canopy-branded PDF coursebook."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from io import BytesIO
from pathlib import Path
import re
from typing import Iterator

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFontFile
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    Image,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from app.course_category import accent_colors_for
from app.schemas import CitationExcerptResponse, ConceptDetailResponse, CourseMapResponse, CourseSummary

# The lesson generator emits placement markers like "{{example:1}}"/"{{quiz:2}}" inline in
# explanation prose (apps/web/components/concept-detail.tsx's LESSON_MARKER splits the
# interactive lesson view on these to interleave the actual example/quiz card at that
# position). The PDF still shows every worked example and quiz item -- just gathered into
# their own cards after the prose, rather than re-implementing positional interleaving in a
# static document -- so the markers themselves are just noise here and are stripped.
_LESSON_MARKER = re.compile(r"\{\{\s*(?:example|quiz)\s*:\s*\d+\s*\}\}")

_ASSETS_DIR = Path(__file__).parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_LOGO_PATH = _ASSETS_DIR / "canopy-logo.png"

# Same embedded brand font as certificate_pdf.py (see there for provenance) -- registering
# twice under the same name is a no-op in reportlab's global font registry, so it's safe
# for both modules to do this independently rather than one importing internals from the other.
_REGULAR_FONT = "GoogleSans"
_BOLD_FONT = "GoogleSans-Bold"
pdfmetrics.registerFont(TTFont(_REGULAR_FONT, str(_FONTS_DIR / "GoogleSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont(_BOLD_FONT, str(_FONTS_DIR / "GoogleSans-Bold.ttf")))

# Courier for code and Symbol for math are reportlab built-ins. The brand font carries only
# ~228 glyphs (Latin-1 plus a handful of punctuation marks) -- no Greek and no math
# operators -- so every such character has to be emitted inside a <font name="Symbol"> run
# or it silently renders as a missing-glyph box. See _symbol()/_math_markup().
_MONO_FONT = "Courier"
_SYMBOL_FONT = "Symbol"
_DINGBAT_FONT = "ZapfDingbats"

# Exactly which code points the brand font can draw, read from its own cmap. Anything outside
# this set renders as a silent blank box (reportlab does not raise), which is how emoji and
# check marks in generated lesson prose turned into holes in the page -- see _fallback_runs().
_BRAND_GLYPHS = frozenset(TTFontFile(str(_FONTS_DIR / "GoogleSans-Regular.ttf")).charToGlyph)

_PAGE_SIZE = LETTER
_MARGIN_X = 0.78 * inch
_MARGIN_TOP = 0.8 * inch
_MARGIN_BOTTOM = 0.8 * inch
_CONTENT_WIDTH = _PAGE_SIZE[0] - 2 * _MARGIN_X

_INK = "#0f172a"
_BODY_INK = "#24324a"
_MUTED = "#64748b"
_HAIRLINE = "#e2e8f0"
_LINK = "#4338ca"
_CODE_BACKGROUND = "#0f172a"
_CODE_INK = "#e2e8f0"

# Mirrors apps/web/lib/palette.ts so a lesson's kind reads the same colour here as in the app.
_KIND_COLORS = {"conceptual": "#818cf8", "coding": "#2dd4bf", "assessment": "#fbbf24"}
_KIND_LABELS = {"conceptual": "LESSON", "coding": "LAB", "assessment": "MASTERY CHECK"}

# A long code block cannot split across pages (a card is one table row per flowable, and a
# single Preformatted is atomic), so long listings are chunked into consecutive cards.
_CODE_LINES_PER_CARD = 42


@dataclass(frozen=True)
class _Theme:
    accent: str
    tint: str


# ---------------------------------------------------------------------------- math


# LaTeX command -> the Unicode character to render in the Symbol font.
_MATH_SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "θ", "iota": "ι", "kappa": "κ",
    # "mu" uses the micro sign (U+00B5), not Greek mu: visually identical, and the brand font
    # carries it directly so it needs no Symbol run.
    "lambda": "λ", "mu": "µ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ",
    "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    "nabla": "∇", "partial": "∂", "infty": "∞", "sum": "∑", "prod": "∏", "int": "∫",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈",
    "equiv": "≡", "sim": "∼", "propto": "∝", "times": "×", "cdot": "⋅", "div": "÷",
    "pm": "±", "in": "∈", "notin": "∉", "subset": "⊂", "cup": "∪", "cap": "∩",
    "forall": "∀", "exists": "∃", "rightarrow": "→", "to": "→", "leftarrow": "←",
    "Rightarrow": "⇒", "leftrightarrow": "↔", "mapsto": "→", "ldots": "…", "cdots": "…",
    "prime": "′", "angle": "∠", "perp": "⊥", "therefore": "∴", "emptyset": "∅",
    "dots": "…", "vdots": "…", "implies": "⇒", "iff": "↔", "subseteq": "⊆", "supseteq": "⊇",
    "supset": "⊃", "neg": "¬", "lnot": "¬", "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨",
    "bigcup": "∪", "bigcap": "∩", "bigoplus": "⊕", "oplus": "⊕", "otimes": "⊗",
}

# Commands whose glyph no bundled font can draw, so they degrade to readable ASCII instead.
# Symbol has no angle brackets, ceilings or floors reachable by Unicode (verified), and a
# missing glyph renders as a blank box -- "<V, E>" beats a hole in the sentence.
_MATH_TEXT = {
    "langle": "<", "rangle": ">",
    "lceil": "[", "rceil": "]", "lfloor": "[", "rfloor": "]",
    "lbrace": "{", "rbrace": "}", "lbrack": "[", "rbrack": "]",
    "setminus": "\\", "backslash": "\\", "colon": ":", "mid": "|",
    # No Symbol glyph reachable by Unicode for these two, so they degrade to ASCII.
    "circ": "o", "mp": "-/+",
    # Operator names: TeX sets these upright, and the name is already the right output.
    "log": "log", "ln": "ln", "lg": "lg", "exp": "exp", "sin": "sin", "cos": "cos",
    "tan": "tan", "max": "max", "min": "min", "det": "det", "dim": "dim", "gcd": "gcd",
    "deg": "deg", "arg": "arg", "bmod": "mod", "pmod": "mod", "argmax": "argmax", "argmin": "argmin",
}

# Dropped outright: sizing/spacing directives with no visual meaning in flowed text. Matched
# as whole command names -- a plain substring replace of "\left" also ate the front of
# "\leftrightarrow" and "\leftarrow", turning them into stray words.
_MATH_NOISE_COMMANDS = frozenset({
    "left", "right", "displaystyle", "limits", "nolimits", "quad", "qquad", "mathstrut",
})
_MATH_SPACING = re.compile(r"\\[,;:!]|\\(?= )")

# TeX escapes for characters that are otherwise LaTeX syntax.
_LATEX_ESCAPES = re.compile(r"\\([{}%&_$#])")


def _symbol(text: str) -> str:
    """Wrap characters the brand font lacks in the Symbol font so they actually render."""
    return f'<font name="{_SYMBOL_FONT}">{text}</font>'


# Everything _math_markup can emit is by definition drawable in the Symbol font, so the same
# table doubles as the fallback set for these characters appearing in ordinary prose.
_SYMBOL_FALLBACK = frozenset(_MATH_SYMBOLS.values())

# Marks the brand font lacks but ZapfDingbats carries; each variant folds onto one glyph.
_DINGBAT_FALLBACK = {
    "✓": "✓", "✔": "✓", "☑": "✓", "✅": "✓",
    "✗": "✗", "✘": "✗", "❌": "✗", "☒": "✗",
    "★": "★", "⭐": "★", "☆": "★",
}
# Last-resort ASCII for marks no bundled font can draw.
_TEXT_FALLBACK = {"⚠": "!", "⇐": "<-", "⇔": "<->", "↑": "^", "↓": "v", "•": "•", "‣": "•"}
# Emoji, pictographs and variation selectors: dropped outright, since a blank box mid-sentence
# reads as a rendering bug. Anything else unsupported is left alone rather than silently
# deleted -- losing real prose would be worse than an odd glyph.
_PICTOGRAPH_RANGES = ((0x1F000, 0x1FAFF), (0x2190, 0x21FF), (0x2600, 0x27BF), (0xFE00, 0xFE0F), (0x2B00, 0x2BFF))
_PLACEHOLDER = re.compile(r"\x00[IM]\d+\x00")


def _is_pictograph(character: str) -> bool:
    point = ord(character)
    return any(low <= point <= high for low, high in _PICTOGRAPH_RANGES)


def _fallback_runs(text: str, stash) -> str:
    """Route characters the brand font cannot draw to a font that can.

    Runs over the plain-text stretches only, leaving already-stashed code/math placeholders
    untouched (their contents have their own fonts and must not be re-processed).
    """

    def convert(segment: str) -> str:
        out: list[str] = []
        for character in segment:
            if character in "\n\t" or ord(character) in _BRAND_GLYPHS:
                out.append(character)
            elif character in _DINGBAT_FALLBACK:
                out.append(stash(f'<font name="{_DINGBAT_FONT}">{_DINGBAT_FALLBACK[character]}</font>'))
            elif character in _SYMBOL_FALLBACK:
                out.append(stash(_symbol(character)))
            elif character in _TEXT_FALLBACK:
                out.append(_TEXT_FALLBACK[character])
            elif not _is_pictograph(character):
                out.append(character)
        return "".join(out)

    parts: list[str] = []
    cursor = 0
    for match in _PLACEHOLDER.finditer(text):
        parts.append(convert(text[cursor:match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(convert(text[cursor:]))
    return "".join(parts)


def _fold_code(text: str) -> str:
    """Courier is a WinAnsi base-14 font, so anything outside cp1252 cannot render in code."""
    folded: list[str] = []
    for character in text:
        try:
            character.encode("cp1252")
        except UnicodeEncodeError:
            folded.append("" if _is_pictograph(character) else "?")
        else:
            folded.append(character)
    return "".join(folded)


def _latex_token(name: str, stash, *, known_only: bool) -> str:
    """One LaTeX command -> markup: Symbol-font glyph, ASCII stand-in, or a fallback.

    ``known_only`` is the difference between the two callers. Inside real maths delimiters an
    unrecognised command is still maths, so it degrades to its own name. In undelimited prose
    it might not be LaTeX at all, so an unknown command is left exactly as written -- that is
    what keeps a Windows path like C:\\Users\\name from collapsing to "C:Usersname".
    """
    if name in _MATH_NOISE_COMMANDS:
        return ""
    character = _MATH_SYMBOLS.get(name)
    if character:
        return stash(_symbol(character))
    if name in _MATH_TEXT:
        return _MATH_TEXT[name]
    return f"\\{name}" if known_only else name


def _loose_latex(text: str, stash) -> str:
    """Convert LaTeX that arrives with no math delimiters at all.

    The lesson generator writes maths straight into prose -- "a graph is written as
    \\langle V, E\\rangle", "\\Theta(V + E)", "\\{u, v\\}" -- with no $...$ or \\(...\\)
    around it. A delimiter-only renderer therefore printed the raw commands. Runs on prose
    only: code spans and delimited maths are already stashed by the time this is called.
    """
    if "\\" not in text:
        return text
    text = re.sub(r"\\\\", " ", text)                             # TeX line break
    text = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}", "", text)      # environment wrappers
    text = re.sub(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\s*\{([^{}]*)\}", lambda m: stash(_symbol("√")) + f"({m.group(1)})", text)
    text = re.sub(r"\\(?:text|mathrm|mathbf|mathit|mathcal|operatorname)\s*\{([^{}]*)\}", r"\1", text)
    text = _MATH_SPACING.sub(" ", text)
    text = _LATEX_ESCAPES.sub(lambda m: stash(escape(m.group(1))), text)
    text = re.sub(r"\\([A-Za-z]+)", lambda m: _latex_token(m.group(1), stash, known_only=True), text)
    # Only the braced script forms: bare "_x" would mangle snake_case identifiers in prose.
    text = re.sub(r"\^\{([^{}]*)\}", lambda m: stash(f"<super>{escape(m.group(1))}</super>"), text)
    text = re.sub(r"_\{([^{}]*)\}", lambda m: stash(f"<sub>{escape(m.group(1))}</sub>"), text)
    return text


def _math_markup(tex: str) -> str:
    """Turn a LaTeX fragment into readable reportlab markup.

    There is no TeX engine here, so this is deliberately a legibility pass rather than a
    renderer: commands become their Unicode symbol, sub/superscripts become real <sub>/<super>
    runs, and fractions degrade to (a)/(b). The alternative -- printing raw "\\theta_{t+1}" --
    is what this replaces.
    """
    fragments: list[str] = []

    def stash(markup: str) -> str:
        fragments.append(markup)
        return f"\x00M{len(fragments) - 1}\x00"

    text = _MATH_SPACING.sub(" ", tex.strip())
    # Innermost-first so nested fractions unwrap completely.
    fraction = re.compile(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
    while fraction.search(text):
        text = fraction.sub(r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\s*\{([^{}]*)\}", lambda m: stash(_symbol("√")) + f"({m.group(1)})", text)
    text = re.sub(r"\\(?:text|mathrm|mathbf|mathit|mathcal|operatorname)\s*\{([^{}]*)\}", r"\1", text)
    # Escaped literals are stashed so the brace-stripping pass below cannot eat them.
    text = _LATEX_ESCAPES.sub(lambda m: stash(escape(m.group(1))), text)
    text = re.sub(r"\\([A-Za-z]+)", lambda m: _latex_token(m.group(1), stash, known_only=False), text)
    text = re.sub(r"\^\{([^{}]*)\}", lambda m: stash(f"<super>{escape(m.group(1))}</super>"), text)
    text = re.sub(r"\^(-?\w)", lambda m: stash(f"<super>{escape(m.group(1))}</super>"), text)
    text = re.sub(r"_\{([^{}]*)\}", lambda m: stash(f"<sub>{escape(m.group(1))}</sub>"), text)
    text = re.sub(r"_(\w)", lambda m: stash(f"<sub>{escape(m.group(1))}</sub>"), text)
    text = text.replace("{", "").replace("}", "")
    text = escape(text)
    # Stashed fragments can nest (a superscript containing a symbol), so resolve repeatedly.
    for _ in range(6):
        if "\x00M" not in text:
            break
        text = re.sub(r"\x00M(\d+)\x00", lambda m: fragments[int(m.group(1))], text)
    return f"<i>{re.sub(r'\\s+', ' ', text).strip()}</i>"


# -------------------------------------------------------------------------- inline


def _code_markup(code: str) -> str:
    return f'<font name="{_MONO_FONT}" color="{_INK}">{escape(code)}</font>'


# The lesson generator cites sources by writing the raw chunk id inline, e.g.
# "...depends on the graph type. [b64d1cbb-db0b-476b-861d-b51145f97751]". The web view turns
# these into numbered superscripts (markdown-text.tsx's CITATION_PATTERN); the PDF used to
# print the bare uuid, dropping 16 distinct hashes into the reading text of a 37-page export.
_CITATION_MARKER = re.compile(
    r"\s*\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]", re.IGNORECASE
)


def _citation_markup(text: str, citations: dict[str, int] | None, stash) -> str:
    """Inline chunk-id markers become superscript references into the References page.

    A marker with no matching reference (deleted or legacy citation) is dropped rather than
    printed, so a raw uuid can never reach the page.
    """
    if "[" not in text:
        return text

    def replace(match: re.Match[str]) -> str:
        number = (citations or {}).get(match.group(1).lower())
        if not number:
            return ""
        return stash(f'<super><a href="#ref-{number}" color="{_LINK}">[{number}]</a></super>')

    return _CITATION_MARKER.sub(replace, text)


def _emphasis(text: str) -> str:
    """Bold/italic/strikethrough on already-escaped text."""
    # Not <b>...</b>: reportlab's <b> tag resolves a family's bold variant through
    # pdfmetrics.registerFontFamily/addMapping, which -- empirically, even when registered --
    # doesn't reliably kick in for a non-standard embedded TTF across reportlab versions, and
    # silently renders "bold" text in the regular weight with no error. Naming the actual
    # registered bold font directly sidesteps that resolution path entirely.
    text = re.sub(r"\*\*(.+?)\*\*", rf'<font name="{_BOLD_FONT}">\1</font>', text)
    text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", rf'<font name="{_BOLD_FONT}">\1</font>', text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<i>\1</i>", text)
    # Guarded against intra-word underscores so snake_case_names survive unmangled.
    text = re.sub(r"(?<![\w_])_([^_\n]+?)_(?![\w_])", r"<i>\1</i>", text)
    text = re.sub(r"~~(.+?)~~", r"<strike>\1</strike>", text)
    return text


def _inline(markdown: str, citations: dict[str, int] | None = None) -> str:
    """Inline markdown -> reportlab paragraph markup."""
    fragments: list[str] = []

    def stash(markup: str) -> str:
        fragments.append(markup)
        return f"\x00I{len(fragments) - 1}\x00"

    text = markdown.strip()
    # Code and math come out first so no later rule can reach inside them -- otherwise a URL's
    # underscores get italicised and a code span's asterisks get read as emphasis.
    text = re.sub(r"``(.+?)``|`([^`]+)`", lambda m: stash(_code_markup(m.group(1) or m.group(2))), text)
    text = re.sub(r"\$\$(.+?)\$\$", lambda m: stash(_math_markup(m.group(1))), text, flags=re.S)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: stash(_math_markup(m.group(1))), text, flags=re.S)
    text = re.sub(r"\$(?![\s\d])([^$\n]+?)\$(?!\d)", lambda m: stash(_math_markup(m.group(1))), text)
    text = _citation_markup(text, citations, stash)
    # Undelimited LaTeX is the common case in generated lessons, so this runs on every
    # paragraph -- after the delimited forms above have already been taken out.
    text = _loose_latex(text, stash)
    text = _fallback_runs(text, stash)
    text = escape(text)
    # Images can't be fetched during a synchronous export, so keep the alt text.
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(
        r"\[([^\]]+)\]\(\s*([^)\s]+?)(?:\s+&quot;[^&]*&quot;)?\s*\)",
        lambda m: stash(f'<link href="{m.group(2)}" color="{_LINK}"><u>{_emphasis(m.group(1))}</u></link>'),
        text,
    )
    text = _emphasis(text)
    for _ in range(6):
        if "\x00I" not in text:
            break
        text = re.sub(r"\x00I(\d+)\x00", lambda m: fragments[int(m.group(1))], text)
    return text


# ----------------------------------------------------------------------- flowables


class _Rule(Flowable):
    """A thin horizontal rule -- markdown's `---`, which otherwise vanished into a Spacer."""

    def __init__(self, width: float, color: str = _HAIRLINE) -> None:
        super().__init__()
        self.width = width
        self.color = color

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        return self.width, 9

    def draw(self) -> None:
        self.canv.setStrokeColor(HexColor(self.color))
        self.canv.setLineWidth(0.75)
        self.canv.line(0, 4, self.width, 4)


class _TocMark(Flowable):
    """Zero-height marker the doc template turns into a table-of-contents entry.

    Using a dedicated flowable (rather than sniffing headings in afterFlowable) keeps the
    entry decoupled from how a heading happens to be laid out -- module titles live inside a
    card, so there is no top-level Paragraph to detect.
    """

    def __init__(self, level: int, text: str, key: str) -> None:
        super().__init__()
        self.level = level
        self.text = text
        self.key = key

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        return 0, 0

    def draw(self) -> None:
        return None


class _RoundedCard(Table):
    """A ReportLab table with the same soft card treatment as the web course view."""

    # The card attributes carry defaults purely so reportlab can reconstruct this class when it
    # splits a table across pages -- Table._splitRows calls self.__class__(data, ...) with only
    # the stock Table arguments, so any required keyword-only argument raises there instead.
    # split() below re-stamps the real values onto each fragment.
    def __init__(self, *args, background: str = "#ffffff", border: str | None = None, radius: int = 14, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._card_background = HexColor(background)
        self._card_border = HexColor(border) if border else None
        self._card_radius = radius

    def split(self, available_width: float, available_height: float):  # type: ignore[no-untyped-def]
        fragments = super().split(available_width, available_height)
        for fragment in fragments:
            if isinstance(fragment, _RoundedCard):
                fragment._card_background = self._card_background
                fragment._card_border = self._card_border
                fragment._card_radius = self._card_radius
        return fragments

    def draw(self) -> None:  # type: ignore[no-untyped-def]
        self.canv.saveState()
        self.canv.setFillColor(self._card_background)
        if self._card_border:
            self.canv.setStrokeColor(self._card_border)
            self.canv.setLineWidth(0.65)
            self.canv.roundRect(0, 0, self._width, self._height, self._card_radius, fill=1, stroke=1)
        else:
            self.canv.roundRect(0, 0, self._width, self._height, self._card_radius, fill=1, stroke=0)
        self.canv.restoreState()
        super().draw()


def _card(
    content: list,
    background: str,
    *,
    width: float,
    padding: int = 12,
    border: str | None = _HAIRLINE,
    radius: int = 14,
) -> Table:
    """A rounded card that is exactly ``width`` wide and can split across pages.

    One table *row* per flowable rather than one cell holding them all: a single-row table is
    atomic, so a long worked example or quiz card would overflow the page instead of
    breaking. Row-per-flowable lets ReportLab split it, and each fragment draws its own
    rounded background. Callers must pass the width available to them, so a card nested in a
    padded parent shrinks to fit instead of overhanging it.
    """
    rows = [[item] for item in content] or [[Spacer(0, 0)]]
    card = _RoundedCard(rows, colWidths=[width], background=background, border=border, radius=radius)
    last = len(rows) - 1
    card.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (0, 0), padding),
        ("BOTTOMPADDING", (0, last), (-1, last), padding),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return card


def _inner_width(width: float, padding: int) -> float:
    return width - 2 * padding


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _logo(size: float) -> Image:
    image = Image(str(_LOGO_PATH), width=size, height=size)
    image.hAlign = "CENTER"
    return image


# ------------------------------------------------------------------ block markdown


_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE_DELIMITER = re.compile(r"^\s*\|?[\s:-]*-{2,}[\s:|-]*\|?\s*$")
_BULLETS = ("•", "–", "·")  # only glyphs the brand font actually carries


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _column_alignments(delimiter: str) -> list[str]:
    alignments = []
    for cell in _split_table_row(delimiter):
        left, right = cell.startswith(":"), cell.endswith(":")
        alignments.append("CENTER" if left and right else "RIGHT" if right else "LEFT")
    return alignments


def _table_flowable(rows: list[list[str]], alignments: list[str], styles: dict[str, ParagraphStyle], theme: _Theme, width: float, citations: dict[str, int] | None = None) -> Table:
    """A real GFM table. Previously these collapsed into one run-on paragraph of pipes."""
    header, body = rows[0], rows[1:]
    columns = max(len(row) for row in rows)
    alignments = (alignments + ["LEFT"] * columns)[:columns]

    def pad(row: list[str]) -> list[str]:
        return (row + [""] * columns)[:columns]

    # Weight columns by their longest cell so a "Default: 0.01" column doesn't get the same
    # width as a prose column, with a floor so nothing collapses to unreadable.
    weights = [max(len(row[index]) for row in [pad(r) for r in rows]) or 1 for index in range(columns)]
    total = sum(weights)
    minimum = width / (columns * 2.5)
    widths = [max(minimum, width * weight / total) for weight in weights]
    widths = [value * width / sum(widths) for value in widths]

    header_style = ParagraphStyle("TableHeader", parent=styles["small"], fontName=_BOLD_FONT, textColor=HexColor(theme.accent), spaceAfter=0)
    cell_style = ParagraphStyle("TableCell", parent=styles["small"], textColor=HexColor(_BODY_INK), spaceAfter=0)
    data = [[Paragraph(_inline(cell, citations), header_style) for cell in pad(header)]]
    data.extend([Paragraph(_inline(cell, citations), cell_style) for cell in pad(row)] for row in body)

    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(theme.tint)),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, HexColor(theme.accent)),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, HexColor(_HAIRLINE)),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(_HAIRLINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for index, alignment in enumerate(alignments):
        style.append(("ALIGN", (index, 0), (index, -1), alignment))
    table.setStyle(TableStyle(style))
    return table


def _code_cards(code: str, styles: dict[str, ParagraphStyle], width: float) -> Iterator[Table]:
    """Wrap long code lines to the card width and chunk very long listings.

    ReportLab's Preformatted does not wrap, so an unwrapped 140-character line simply ran off
    the page. Courier is fixed-pitch, which makes the character budget exact.
    """
    padding = 12
    style = styles["code"]
    available = _inner_width(width, padding)
    character = pdfmetrics.stringWidth("0", _MONO_FONT, style.fontSize)
    budget = max(24, int(available / character))

    wrapped: list[str] = []
    for raw in _fold_code(code).split("\n"):
        line = raw.replace("\t", "    ").rstrip()
        if len(line) <= budget:
            wrapped.append(line)
            continue
        # Continuation lines keep the original indent (plus a two-space step) so wrapped code
        # still reads as one logical statement.
        indent = " " * min(len(line) - len(line.lstrip(" ")) + 2, max(budget - 12, 0))
        remainder, first = line, True
        while remainder:
            take = budget if first else budget - len(indent)
            wrapped.append((remainder[:take]) if first else indent + remainder[:take])
            remainder = remainder[take:]
            first = False

    for start in range(0, len(wrapped), _CODE_LINES_PER_CARD):
        chunk = wrapped[start:start + _CODE_LINES_PER_CARD]
        yield _card(
            [Preformatted("\n".join(chunk), style)],
            _CODE_BACKGROUND,
            width=width,
            padding=padding,
            border=None,
            radius=12,
        )


def _list_flowables(items: list[tuple[int, str, str]], styles: dict[str, ParagraphStyle], citations: dict[str, int] | None = None) -> Iterator[Paragraph]:
    """Indented, tightly-spaced list items. Nesting used to be flattened flush-left and every
    item picked up a full paragraph's worth of trailing space."""
    indents = sorted({indent for indent, _, _ in items})
    for indent, marker, text in items:
        depth = min(indents.index(indent), 2)
        ordered = marker[0].isdigit()
        bullet = marker if ordered else _BULLETS[depth]
        style = ParagraphStyle(
            f"ListLevel{depth}",
            parent=styles["body"],
            leftIndent=16 + depth * 16,
            firstLineIndent=-12,
            spaceBefore=0,
            spaceAfter=3,
        )
        yield Paragraph(f"{escape(bullet)}&nbsp;&nbsp;{_inline(text, citations)}", style)


def _markdown_flowables(markdown: str, styles: dict[str, ParagraphStyle], theme: _Theme, width: float, citations: dict[str, int] | None = None) -> Iterator:
    lines = markdown.replace("\r\n", "\n").split("\n")
    index = 0
    paragraph: list[str] = []

    def flush() -> Iterator[Paragraph]:
        if paragraph:
            text = " ".join(part.strip() for part in paragraph).strip()
            paragraph.clear()
            if text:
                yield Paragraph(_inline(text, citations), styles["body"])

    while index < len(lines):
        raw = lines[index]
        text = raw.strip()

        if text.startswith("```") or text.startswith("~~~"):
            yield from flush()
            fence = text[:3]
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith(fence):
                code.append(lines[index])
                index += 1
            index += 1
            yield Spacer(1, 4)
            yield from _code_cards("\n".join(code), styles, width)
            yield Spacer(1, 8)
            continue

        if text.startswith("$$") or text.startswith("\\["):
            yield from flush()
            closer = "$$" if text.startswith("$$") else "\\]"
            body = text[2:]
            math: list[str] = []
            if closer in body:
                math.append(body.split(closer, 1)[0])
                index += 1
            else:
                math.append(body)
                index += 1
                while index < len(lines) and closer not in lines[index]:
                    math.append(lines[index])
                    index += 1
                if index < len(lines):
                    math.append(lines[index].split(closer, 1)[0])
                    index += 1
            yield Paragraph(_math_markup(" ".join(math)), styles["math"])
            continue

        # A table needs its delimiter row to be unambiguous ("| --- | --- |").
        if "|" in text and index + 1 < len(lines) and _TABLE_DELIMITER.match(lines[index + 1]) and "|" in lines[index + 1]:
            yield from flush()
            header = _split_table_row(text)
            alignments = _column_alignments(lines[index + 1])
            index += 2
            rows = [header]
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(_split_table_row(lines[index]))
                index += 1
            yield Spacer(1, 4)
            yield _table_flowable(rows, alignments, styles, theme, width, citations)
            yield Spacer(1, 9)
            continue

        if _LIST_ITEM.match(raw):
            yield from flush()
            items: list[tuple[int, str, str]] = []
            while index < len(lines):
                match = _LIST_ITEM.match(lines[index])
                if match:
                    indent, marker, item = match.groups()
                    items.append((len(indent), marker, item))
                    index += 1
                elif lines[index].strip() and lines[index][:1] in (" ", "\t") and items:
                    # A wrapped continuation line belongs to the item above it.
                    last = items[-1]
                    items[-1] = (last[0], last[1], f"{last[2]} {lines[index].strip()}")
                    index += 1
                elif not lines[index].strip() and index + 1 < len(lines) and _LIST_ITEM.match(lines[index + 1]):
                    index += 1
                else:
                    break
            yield Spacer(1, 3)
            yield from _list_flowables(items, styles, citations)
            yield Spacer(1, 6)
            continue

        if text.startswith(">"):
            yield from flush()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            padding = 13
            inner = list(_markdown_flowables("\n".join(quote), {**styles, "body": styles["callout"]}, theme, _inner_width(width, padding), citations))
            yield _card(inner, "#ffffff", width=width, padding=padding, border=theme.accent, radius=12)
            yield Spacer(1, 8)
            continue

        heading = _HEADING.match(text)
        if heading:
            yield from flush()
            level = min(len(heading.group(1)), 4)
            yield Paragraph(_inline(heading.group(2), citations), styles[f"h{level}"])
            index += 1
            continue

        if text in {"---", "***", "___"}:
            yield from flush()
            yield Spacer(1, 3)
            yield _Rule(width)
            yield Spacer(1, 5)
            index += 1
            continue

        if not text:
            yield from flush()
        else:
            paragraph.append(raw)
        index += 1

    yield from flush()


# ------------------------------------------------------------------- page assembly


class _Coursebook(SimpleDocTemplate):
    """Records table-of-contents entries so the contents page can carry real page numbers."""

    def afterFlowable(self, flowable) -> None:  # type: ignore[no-untyped-def]
        if isinstance(flowable, _TocMark):
            self.notify("TOCEntry", (flowable.level, flowable.text, self.page, flowable.key))


def _page_furniture(canvas, document) -> None:  # type: ignore[no-untyped-def]
    """Branded footer: the Canopy mark on the left, page number on the right."""
    canvas.saveState()
    baseline = 0.46 * inch
    size = 11
    canvas.drawImage(str(_LOGO_PATH), _MARGIN_X, baseline - 2, size, size, mask="auto")
    canvas.setFont(_BOLD_FONT, 8.5)
    canvas.setFillColor(HexColor(_INK))
    canvas.drawString(_MARGIN_X + size + 5, baseline + 1, "Canopy")
    canvas.setFont(_REGULAR_FONT, 8.5)
    canvas.setFillColor(HexColor(_MUTED))
    canvas.drawRightString(_PAGE_SIZE[0] - _MARGIN_X, baseline + 1, str(document.page))
    canvas.setStrokeColor(HexColor(_HAIRLINE))
    canvas.setLineWidth(0.5)
    canvas.line(_MARGIN_X, baseline + 15, _PAGE_SIZE[0] - _MARGIN_X, baseline + 15)
    canvas.restoreState()


def _cover_page(canvas, document) -> None:  # type: ignore[no-untyped-def]
    """The cover carries the brand itself, so it gets no running footer."""
    return None


def _build_styles(theme: _Theme) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body", parent=sample["BodyText"], fontName=_REGULAR_FONT, fontSize=10.5, leading=15.5,
        textColor=HexColor(_BODY_INK), spaceAfter=7,
    )
    small = ParagraphStyle("Small", parent=body, fontSize=9, leading=12.5, textColor=HexColor(_MUTED), spaceAfter=4)
    # keepWithNext is the real fix for orphaned headings -- a heading can no longer be the last
    # thing on a page with its content stranded overleaf.
    section = ParagraphStyle(
        "Section", parent=sample["Heading2"], fontName=_BOLD_FONT, fontSize=15, leading=19.5,
        textColor=HexColor(_INK), spaceBefore=13, spaceAfter=8, keepWithNext=1,
    )
    return {
        "body": body,
        "small": small,
        "section": section,
        "h1": ParagraphStyle("H1", parent=section, fontSize=14.5, spaceBefore=15),
        "h2": ParagraphStyle("H2", parent=section, fontSize=12.8, spaceBefore=13),
        "h3": ParagraphStyle("H3", parent=body, fontName=_BOLD_FONT, fontSize=11.2, spaceBefore=11, spaceAfter=4, keepWithNext=1),
        "h4": ParagraphStyle("H4", parent=body, fontName=_BOLD_FONT, fontSize=10.5, textColor=HexColor(_MUTED), spaceBefore=9, spaceAfter=3, keepWithNext=1),
        "callout": ParagraphStyle("Callout", parent=body, textColor=HexColor(theme.accent), spaceAfter=4),
        "math": ParagraphStyle("Math", parent=body, alignment=TA_CENTER, fontSize=11.5, leading=17, spaceBefore=7, spaceAfter=9, textColor=HexColor(_INK)),
        "code": ParagraphStyle("Code", fontName=_MONO_FONT, fontSize=8.4, leading=11.4, textColor=HexColor(_CODE_INK)),
    }


def _cover_story(course: CourseSummary, course_map: CourseMapResponse, theme: _Theme, styles: dict[str, ParagraphStyle]) -> list:
    title = ParagraphStyle("CoverTitle", parent=styles["body"], fontName=_BOLD_FONT, fontSize=28, leading=33, alignment=TA_CENTER, textColor=white, spaceAfter=12)
    goal = ParagraphStyle("CoverGoal", parent=styles["body"], fontSize=11.5, leading=17, alignment=TA_CENTER, textColor=HexColor("#e8ecf8"), spaceAfter=0)
    wordmark = ParagraphStyle("CoverWordmark", parent=styles["body"], fontName=_BOLD_FONT, fontSize=13, alignment=TA_CENTER, textColor=white, spaceAfter=0)
    label = ParagraphStyle("CoverLabel", parent=styles["small"], fontSize=8.5, alignment=TA_CENTER, textColor=HexColor("#c7d2fe"), spaceAfter=0)

    padding = 34
    badge = _card([_logo(46)], "#ffffff", width=0.92 * inch, padding=11, border=None, radius=20)
    badge.hAlign = "CENTER"
    modules = len(course_map.modules)
    lessons = sum(len(module.concepts) for module in course_map.modules)
    meta = f"{_plural(modules, 'module')} &nbsp;&middot;&nbsp; {_plural(lessons, 'lesson')}"

    cover = _card(
        [
            badge,
            Spacer(1, 12),
            Paragraph("CANOPY", wordmark),
            Spacer(1, 22),
            Paragraph(_inline(course.title), title),
            Paragraph(_inline(course.goal), goal),
            Spacer(1, 24),
            Paragraph(meta, label),
        ],
        theme.accent,
        width=_CONTENT_WIDTH,
        padding=padding,
        border=None,
        radius=26,
    )
    return [Spacer(1, 1.15 * inch), cover, PageBreak()]


def _contents_story(theme: _Theme, styles: dict[str, ParagraphStyle]) -> list:
    heading = ParagraphStyle("ContentsHeading", parent=styles["section"], fontSize=20, leading=25, textColor=HexColor(theme.accent), spaceBefore=0, spaceAfter=16)
    contents = TableOfContents()
    contents.levelStyles = [
        ParagraphStyle("Toc0", parent=styles["body"], fontName=_BOLD_FONT, fontSize=11, leading=17, spaceBefore=9, textColor=HexColor(_INK)),
        ParagraphStyle("Toc1", parent=styles["small"], fontSize=9.5, leading=15, leftIndent=18, textColor=HexColor(_MUTED)),
    ]
    contents.dotsMinLevel = 0
    # No trailing PageBreak: every module opener starts with one, and two in a row leaves a
    # blank page between the contents and the first module.
    return [Paragraph("Contents", heading), contents]


def _lesson_story(
    concept,
    detail: ConceptDetailResponse | None,
    theme: _Theme,
    styles: dict[str, ParagraphStyle],
    reference_numbers: dict[str, int],
    key: str,
) -> list:
    story: list = [
        # Keeps a lesson heading from stranding at the foot of a page ahead of its body.
        CondPageBreak(1.4 * inch),
        _TocMark(1, concept.title, key),
    ]
    kind = getattr(concept, "kind", "conceptual")
    kind_color = _KIND_COLORS.get(kind, theme.accent)
    kind_style = ParagraphStyle("Kind", parent=styles["small"], fontName=_BOLD_FONT, fontSize=7.6, textColor=HexColor(kind_color), spaceAfter=3)
    title_style = ParagraphStyle("LessonTitle", parent=styles["section"], spaceBefore=0, spaceAfter=3, keepWithNext=0)

    summary = (detail.summary_markdown if detail else "") or concept.summary_markdown
    header = [
        Paragraph(_KIND_LABELS.get(kind, "LESSON"), kind_style),
        Paragraph(f'<a name="{key}"/>{_inline(concept.title)}', title_style),
    ]
    if summary:
        header.append(Paragraph(_inline(summary, reference_numbers), styles["small"]))
    padding = 14
    story.append(_card(header, "#ffffff", width=_CONTENT_WIDTH, padding=padding, border=_HAIRLINE, radius=14))
    story.append(Spacer(1, 10))

    if detail and detail.lesson:
        explanation = _LESSON_MARKER.sub("", detail.lesson.explanation_markdown)
        story.extend(_markdown_flowables(explanation, styles, theme, _CONTENT_WIDTH, reference_numbers))

        for example in detail.lesson.worked_examples:
            example_padding = 14
            inner = _inner_width(_CONTENT_WIDTH, example_padding)
            example_title = ParagraphStyle("ExampleTitle", parent=styles["body"], fontName=_BOLD_FONT, textColor=HexColor(theme.accent), spaceAfter=5)
            story.append(Spacer(1, 6))
            story.append(_card(
                [Paragraph(_inline(example.title, reference_numbers), example_title), *_markdown_flowables(example.body_markdown, styles, theme, inner, reference_numbers)],
                theme.tint,
                width=_CONTENT_WIDTH,
                padding=example_padding,
                border=None,
                radius=14,
            ))
            story.append(Spacer(1, 6))

        if detail.lesson.quiz_items:
            quiz_padding = 14
            prompt_style = ParagraphStyle("QuizPrompt", parent=styles["body"], spaceAfter=3)
            option_style = ParagraphStyle("QuizOption", parent=styles["small"], leftIndent=16, firstLineIndent=-10, spaceAfter=2)
            heading = ParagraphStyle("QuizHeading", parent=styles["body"], fontName=_BOLD_FONT, textColor=HexColor("#92400e"), spaceAfter=7)
            content = [Paragraph("Check your understanding", heading)]
            for position, quiz in enumerate(detail.lesson.quiz_items, start=1):
                content.append(Paragraph(f"{position}. {_inline(quiz.prompt_markdown, reference_numbers)}", prompt_style))
                for option in quiz.options or []:
                    content.append(Paragraph(f"{escape(_BULLETS[0])}&nbsp;&nbsp;{_inline(option.text)}", option_style))
                content.append(Spacer(1, 5))
            story.append(Spacer(1, 4))
            story.append(_card(content, "#fffbeb", width=_CONTENT_WIDTH, padding=quiz_padding, border="#fde68a", radius=14))

    if detail:
        cited = [reference_numbers[citation] for citation in detail.citations if citation in reference_numbers]
        if cited:
            links = ", ".join(f'<a href="#ref-{number}" color="{_LINK}">[{number}]</a>' for number in cited)
            story.append(Spacer(1, 7))
            story.append(Paragraph(f"Sources: {links}", styles["small"]))
    story.append(Spacer(1, 16))
    return story


def _references_story(references: list[CitationExcerptResponse], theme: _Theme, styles: dict[str, ParagraphStyle]) -> list:
    if not references:
        return []
    heading = ParagraphStyle("RefHeading", parent=styles["section"], fontSize=20, leading=25, textColor=HexColor(theme.accent), spaceBefore=0, spaceAfter=14)
    label = ParagraphStyle("RefLabel", parent=styles["body"], fontName=_BOLD_FONT, fontSize=10, spaceBefore=10, spaceAfter=3, textColor=HexColor(_INK), keepWithNext=1)
    # Deliberately not a card: a source excerpt has no length bound, and a card cannot split
    # mid-paragraph, so long excerpts would overflow the page.
    excerpt = ParagraphStyle("RefExcerpt", parent=styles["small"], leftIndent=13, textColor=HexColor(_MUTED), spaceAfter=6)
    story: list = [PageBreak(), _TocMark(0, "References", "references"), Paragraph('<a name="references"/>References', heading)]
    for index, reference in enumerate(references, start=1):
        location = ", ".join(
            part for part in [reference.filename, reference.section, f"p. {reference.page_number}" if reference.page_number else None] if part
        )
        story.append(Paragraph(f'<a name="ref-{index}"/>[{index}] {_inline(location)}', label))
        story.append(Paragraph(_inline(reference.content), excerpt))
        story.append(_Rule(_CONTENT_WIDTH))
    return story


def render_textbook_pdf(
    course: CourseSummary,
    course_map: CourseMapResponse,
    details: dict[str, ConceptDetailResponse],
    references: list[CitationExcerptResponse],
) -> bytes:
    """Produce learner-visible prose only; never include hidden tests or solutions."""
    accent, tint = accent_colors_for(course.title, course.goal)
    theme = _Theme(accent=accent, tint=tint)
    styles = _build_styles(theme)
    output = BytesIO()
    document = _Coursebook(
        output,
        pagesize=_PAGE_SIZE,
        leftMargin=_MARGIN_X,
        rightMargin=_MARGIN_X,
        topMargin=_MARGIN_TOP,
        bottomMargin=_MARGIN_BOTTOM,
        title=f"{course.title} -- Canopy coursebook",
        author="Canopy",
        subject=course.goal,
    )

    reference_numbers = {str(reference.id): index for index, reference in enumerate(references, start=1)}
    story: list = []
    story.extend(_cover_story(course, course_map, theme, styles))
    story.extend(_contents_story(theme, styles))

    module_label = ParagraphStyle("ModuleLabel", parent=styles["small"], fontName=_BOLD_FONT, fontSize=8.5, textColor=HexColor(theme.accent), alignment=TA_CENTER, spaceAfter=0)
    module_title = ParagraphStyle("ModuleTitle", parent=styles["section"], fontSize=21, leading=26, textColor=HexColor(theme.accent), alignment=TA_CENTER, spaceBefore=0, spaceAfter=0, keepWithNext=0)

    for module in course_map.modules:
        key = f"module-{module.position}"
        story.append(PageBreak())
        story.append(_TocMark(0, f"{module.position}. {module.title}", key))
        story.append(_card(
            [
                Paragraph(f"MODULE {module.position}", module_label),
                Spacer(1, 7),
                Paragraph(f'<a name="{key}"/>{_inline(module.title)}', module_title),
            ],
            theme.tint,
            width=_CONTENT_WIDTH,
            padding=24,
            border=None,
            radius=18,
        ))
        story.append(Spacer(1, 16))
        for concept in module.concepts:
            story.extend(
                _lesson_story(concept, details.get(concept.slug), theme, styles, reference_numbers, f"concept-{module.position}-{concept.slug}")
            )

    story.extend(_references_story(references, theme, styles))

    # multiBuild resolves the contents page's forward references to real page numbers.
    document.multiBuild(story, onFirstPage=_cover_page, onLaterPages=_page_furniture)
    return output.getvalue()
