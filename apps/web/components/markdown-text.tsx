import { Fragment, ReactNode } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";
import katex from "katex";
import "katex/dist/katex.min.css";

const CITATION_PATTERN = /\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]/gi;

// Inline math delimiters, longest/most-specific first so `$$` wins over `$`. The bare-`$`
// arm is deliberately conservative to avoid eating prose currency ("$5 for $10"): the
// opening `$` may not be followed by whitespace or another `$`, and the closing `$` may not
// be followed by a digit. `\(...\)`/`\[...\]` are unambiguous and always treated as math.
const INLINE_MATH_PATTERN = /(\$\$[\s\S]+?\$\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]|\$(?![\s$])(?:\\[\s\S]|[^\\$])+?\$(?!\d))/g;
const HAS_MATH = /\$|\\\(|\\\[/;

/** Split a math token into its LaTeX body and display mode, or null when it is not one. */
function mathToken(token: string): { tex: string; display: boolean } | null {
  if (token.startsWith("$$") && token.endsWith("$$") && token.length >= 4) return { tex: token.slice(2, -2), display: true };
  if (token.startsWith("\\[") && token.endsWith("\\]")) return { tex: token.slice(2, -2), display: true };
  if (token.startsWith("\\(") && token.endsWith("\\)")) return { tex: token.slice(2, -2), display: false };
  if (token.startsWith("$") && token.endsWith("$") && token.length >= 2) return { tex: token.slice(1, -1), display: false };
  return null;
}

/** Render one span of LaTeX with KaTeX. `throwOnError: false` keeps a malformed formula
 *  (common in LLM output) from taking down the whole lesson -- it shows in red instead. */
function MathSpan({ tex, display }: { tex: string; display: boolean }) {
  const html = katex.renderToString(tex.trim(), { throwOnError: false, displayMode: display, output: "htmlAndMathml" });
  return (
    <Box
      component="span"
      sx={{
        display: display ? "block" : "inline",
        maxWidth: "100%",
        overflowX: display ? "auto" : "visible",
        overflowY: "hidden",
        textAlign: display ? "center" : "inherit",
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function formatted(text: string, keyPrefix: string): ReactNode[] {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]\n]+\]\([^)\s]+\))/g);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**")) return <strong key={`${keyPrefix}-${index}`}>{token.slice(2, -2)}</strong>;
    if (token.startsWith("`") && token.endsWith("`")) {
      return (
        <Box component="code" key={`${keyPrefix}-${index}`} sx={{ px: "4px", py: "1px", borderRadius: 0.5, bgcolor: "action.hover", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.9em" }}>
          {token.slice(1, -1)}
        </Box>
      );
    }
    const link = token.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
    if (link) {
      return (
        <Box component="a" href={link[2]} target="_blank" rel="noopener noreferrer" key={`${keyPrefix}-${index}`} sx={{ color: "primary.main", textDecoration: "underline", textUnderlineOffset: "2px" }}>
          {link[1]}
        </Box>
      );
    }
    return <Fragment key={`${keyPrefix}-${index}`}>{token}</Fragment>;
  });
}

/** Find learner-selected visible text in Markdown source while ignoring the small set of
 * formatting markers this renderer supports. This keeps selection highlighting stable
 * when a selected sentence includes bold or inline-code text. */
function findVisibleHighlight(text: string, selected: string, occurrence = 0): { start: number; end: number } | undefined {
  const visible: string[] = [];
  const sourceOffsets: number[] = [];
  for (let index = 0; index < text.length; index += 1) {
    if (text.startsWith("**", index)) {
      index += 1;
      continue;
    }
    if (text[index] === "`") continue;
    visible.push(text[index]);
    sourceOffsets.push(index);
  }
  const visibleText = visible.join("");
  let matchIndex = -1;
  let searchFrom = 0;
  for (let index = 0; index <= occurrence; index += 1) {
    matchIndex = visibleText.indexOf(selected, searchFrom);
    if (matchIndex < 0) return undefined;
    searchFrom = matchIndex + selected.length;
  }
  if (matchIndex < 0) return undefined;
  const endIndex = matchIndex + selected.length - 1;
  return { start: sourceOffsets[matchIndex], end: sourceOffsets[endIndex] + 1 };
}

/** Inline chunk citations ([uuid]) become numbered superscripts when the citation list is
 *  known, and disappear entirely when it is not; learners never see raw UUIDs. */
function inlineText(
  text: string,
  citations?: string[],
  highlightText?: string,
  highlightFlash = false,
  highlightOccurrence = 0,
  onCitationClick?: (citationId: string) => void
): ReactNode[] {
  const parts = text.split(CITATION_PATTERN);
  const nodes: ReactNode[] = [];
  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    if (index % 2 === 0) {
      // Collapse the whitespace left behind when adjacent citations are removed.
      const cleaned = part.replace(/\s{2,}/g, " ");
      if (!cleaned) continue;
      const activeHighlight = highlightText ?? "";
      const highlightRange = activeHighlight ? findVisibleHighlight(cleaned, activeHighlight, highlightOccurrence) : undefined;
      if (!highlightRange) {
        nodes.push(...formatted(cleaned, `t-${index}`));
      } else {
        const before = cleaned.slice(0, highlightRange.start);
        const match = cleaned.slice(highlightRange.start, highlightRange.end);
        const after = cleaned.slice(highlightRange.end);
        if (before) nodes.push(...formatted(before, `t-${index}-before`));
        nodes.push(
          <Box
            component="mark"
            key={`highlight-${index}`}
            data-testid="lesson-selection-highlight"
            data-highlight-kind={highlightFlash ? "updated" : "selected"}
            sx={{
              px: "2px",
              borderRadius: 0.5,
              bgcolor: highlightFlash ? "rgba(46, 125, 50, 0.28)" : "rgba(25, 118, 210, 0.13)",
              transition: "background-color 1.2s ease-out",
              color: "inherit",
              display: "inline",
              boxDecorationBreak: "clone",
              WebkitBoxDecorationBreak: "clone"
            }}
          >
            {formatted(match, `t-${index}-highlight`)}
          </Box>
        );
        if (after) nodes.push(...formatted(after, `t-${index}-after`));
      }
      continue;
    }
    const citationNumber = citations ? citations.findIndex((id) => id.toLowerCase() === part.toLowerCase()) + 1 : 0;
    if (citationNumber > 0) {
      const clickable = Boolean(onCitationClick);
      nodes.push(
        <Tooltip title={clickable ? "View source excerpt" : `Source excerpt ${citationNumber}`} key={`c-${index}`}>
          <Box
            component="sup"
            role={clickable ? "button" : undefined}
            tabIndex={clickable ? 0 : undefined}
            onClick={
              clickable
                ? (event) => {
                    event.stopPropagation();
                    onCitationClick?.(part);
                  }
                : undefined
            }
            onKeyDown={
              clickable
                ? (event) => {
                    if (event.key !== "Enter" && event.key !== " ") return;
                    event.stopPropagation();
                    event.preventDefault();
                    onCitationClick?.(part);
                  }
                : undefined
            }
            sx={{ color: "text.secondary", fontSize: "0.72em", fontWeight: 600, ml: "2px", whiteSpace: "nowrap", cursor: clickable ? "pointer" : "default" }}
          >
            [{citationNumber}]
          </Box>
        </Tooltip>
      );
    }
  }
  return nodes;
}

/** Inline rendering with LaTeX math awareness. When a span has no math delimiters this is a
 *  no-op wrapper over inlineText, so existing citation/highlight behavior is byte-for-byte
 *  unchanged; math spans are pulled out first and rendered with KaTeX so the emphasis and
 *  citation passes never see their contents. */
function inline(
  text: string,
  citations?: string[],
  highlightText?: string,
  highlightFlash = false,
  highlightOccurrence = 0,
  onCitationClick?: (citationId: string) => void
): ReactNode[] {
  if (!HAS_MATH.test(text)) {
    return inlineText(text, citations, highlightText, highlightFlash, highlightOccurrence, onCitationClick);
  }
  const nodes: ReactNode[] = [];
  text.split(INLINE_MATH_PATTERN).forEach((part, index) => {
    if (!part) return;
    const math = mathToken(part);
    if (math) {
      nodes.push(<MathSpan key={`math-${index}`} tex={math.tex} display={math.display} />);
    } else {
      // Each inlineText() call restarts its own local key counter, so wrap every text segment
      // in a keyed Fragment -- that scopes those inner keys to this segment and keeps sibling
      // keys unique across the split.
      nodes.push(<Fragment key={`seg-${index}`}>{inlineText(part, citations, highlightText, highlightFlash, highlightOccurrence, onCitationClick)}</Fragment>);
    }
  });
  return nodes;
}

// Body headings need real hierarchy or the prose reads flat: MUI's default subtitle1/h6
// land at ~body weight and size. These map each markdown level to a distinct size + bold
// weight + tighter leading, with extra top margin so a heading signals a new section.
const HEADING_STYLES = {
  1: { component: "h2" as const, fontSize: "1.3rem", fontWeight: 700, lineHeight: 1.3, mt: 2 },
  2: { component: "h3" as const, fontSize: "1.1rem", fontWeight: 700, lineHeight: 1.35, mt: 1.75 },
  3: { component: "h4" as const, fontSize: "0.95rem", fontWeight: 700, lineHeight: 1.4, mt: 1.25 }
};

/** A deliberately small, safe Markdown renderer for LLM-authored lesson text. */
export function MarkdownText({ children, citations, highlightText, highlightParagraphId, highlightOccurrence = 0, highlightFlash = false, paragraphGroup = "lesson", onCitationClick, variant, color }: { children: string; citations?: string[]; highlightText?: string; highlightParagraphId?: string; highlightOccurrence?: number; highlightFlash?: boolean; paragraphGroup?: string; onCitationClick?: (citationId: string) => void; variant?: "body1" | "body2" | "caption"; color?: string }) {
  // Some older generated lessons put list markers directly after a sentence. Make those readable too.
  const lines = children.replace(/(?<=\S)\s+- (?=\*\*|[A-Za-z0-9])/g, "\n- ").split("\n");
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | undefined;
  let codeLines: string[] | undefined;
  let mathBlock: { close: string; lines: string[] } | undefined;
  let paragraphNumber = 0;

  const flushParagraph = () => {
    if (paragraph.length) {
      paragraphNumber += 1;
      const source = paragraph.join("\n");
      const paragraphId = `${paragraphGroup}-${paragraphNumber}`;
      blocks.push(<Typography variant={variant} color={color} key={`p-${blocks.length}`} data-lesson-paragraph={paragraphId} data-lesson-source={source}>{inline(paragraph.join(" "), citations, paragraphId === highlightParagraphId ? highlightText : undefined, highlightFlash, highlightOccurrence, onCitationClick)}</Typography>);
    }
    paragraph = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((item, index) => (
      <Typography component="li" variant={variant} color={color} key={index}>{inline(item, citations, highlightText, highlightFlash, 0, onCitationClick)}</Typography>
    ));
    const ListTag = list.ordered ? "ol" : "ul";
    paragraphNumber += 1;
    blocks.push(
      <Box key={`l-${blocks.length}`} data-lesson-paragraph={`${paragraphGroup}-${paragraphNumber}`} data-lesson-source={list.items.join("\n")}>
        <Box component={ListTag} sx={{ m: 0, pl: 3, display: "grid", gap: 0.5 }}>
          {items}
        </Box>
      </Box>
    );
    list = undefined;
  };
  const flushMathBlock = (tex: string) => {
    paragraphNumber += 1;
    blocks.push(
      <Box
        key={`math-${blocks.length}`}
        data-lesson-paragraph={`${paragraphGroup}-${paragraphNumber}`}
        data-lesson-source={`$$${tex.trim()}$$`}
        sx={{ my: 0.5, overflowX: "auto" }}
      >
        <MathSpan tex={tex} display />
      </Box>
    );
  };

  for (const line of lines) {
    if (line.trimStart().startsWith("```")) {
      flushParagraph(); flushList();
      if (codeLines) {
        blocks.push(
          <Box
            component="pre"
            key={`code-${blocks.length}`}
            sx={{ m: 0, p: 1.75, overflowX: "auto", border: 1, borderColor: "divider", borderRadius: 1.5, bgcolor: "action.hover", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.9rem" }}
          >
            <code>{codeLines.join("\n")}</code>
          </Box>
        );
        codeLines = undefined;
      } else {
        codeLines = [];
      }
      continue;
    }
    if (codeLines) {
      codeLines.push(line);
      continue;
    }
    // Multi-line display equation ($$...$$ or \[...\]) started on an earlier line.
    if (mathBlock) {
      const closeIndex = line.indexOf(mathBlock.close);
      if (closeIndex >= 0) {
        mathBlock.lines.push(line.slice(0, closeIndex));
        flushMathBlock(mathBlock.lines.join("\n"));
        mathBlock = undefined;
      } else {
        mathBlock.lines.push(line);
      }
      continue;
    }
    const trimmedStart = line.trimStart();
    const mathOpen = trimmedStart.startsWith("$$") ? "$$" : trimmedStart.startsWith("\\[") ? "\\[" : undefined;
    if (mathOpen) {
      flushParagraph(); flushList();
      const close = mathOpen === "$$" ? "$$" : "\\]";
      const afterOpen = trimmedStart.slice(mathOpen.length);
      const closeIndex = afterOpen.indexOf(close);
      if (closeIndex >= 0) {
        flushMathBlock(afterOpen.slice(0, closeIndex));
      } else {
        mathBlock = { close, lines: afterOpen.trim() ? [afterOpen] : [] };
      }
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    const unordered = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (heading) {
      flushParagraph(); flushList();
      paragraphNumber += 1;
      const headingId = `${paragraphGroup}-${paragraphNumber}`;
      const text = inline(heading[2], citations, undefined, false, 0, onCitationClick);
      const style = HEADING_STYLES[heading[1].length as 1 | 2 | 3];
      blocks.push(
        <Typography
          component={style.component}
          key={`h-${blocks.length}`}
          data-lesson-paragraph={headingId}
          data-lesson-source={line}
          sx={{ mt: style.mt, fontSize: style.fontSize, fontWeight: style.fontWeight, lineHeight: style.lineHeight, letterSpacing: "-0.01em", "&:first-of-type": { mt: 0 } }}
        >
          {text}
        </Typography>
      );
    } else if (unordered || ordered) {
      flushParagraph();
      const isOrdered = Boolean(ordered);
      if (!list || list.ordered !== isOrdered) { flushList(); list = { ordered: isOrdered, items: [] }; }
      list.items.push((unordered ?? ordered)?.[1] ?? "");
    } else if (line.trim()) {
      flushList();
      paragraph.push(line.trim());
    } else {
      flushParagraph(); flushList();
    }
  }
  flushParagraph(); flushList();
  if (mathBlock) flushMathBlock(mathBlock.lines.join("\n"));
  if (codeLines) {
    blocks.push(
      <Box
        component="pre"
        key={`code-${blocks.length}`}
        sx={{ m: 0, p: 1.75, overflowX: "auto", border: 1, borderColor: "divider", borderRadius: 1.5, bgcolor: "action.hover", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.9rem" }}
      >
        <code>{codeLines.join("\n")}</code>
      </Box>
    );
  }
  return (
    <Box sx={{ display: "grid", gap: 1.5 }}>
      {blocks}
    </Box>
  );
}
