import { Fragment, ReactNode } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";

const CITATION_PATTERN = /\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]/gi;

function formatted(text: string, keyPrefix: string): ReactNode[] {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**")) return <strong key={`${keyPrefix}-${index}`}>{token.slice(2, -2)}</strong>;
    if (token.startsWith("`") && token.endsWith("`")) {
      return (
        <Box component="code" key={`${keyPrefix}-${index}`} sx={{ px: "4px", py: "1px", borderRadius: 0.5, bgcolor: "action.hover", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: "0.9em" }}>
          {token.slice(1, -1)}
        </Box>
      );
    }
    return <Fragment key={`${keyPrefix}-${index}`}>{token}</Fragment>;
  });
}

/** Inline chunk citations ([uuid]) become numbered superscripts when the citation list is
 *  known, and disappear entirely when it is not; learners never see raw UUIDs. */
function inline(text: string, citations?: string[]): ReactNode[] {
  const parts = text.split(CITATION_PATTERN);
  const nodes: ReactNode[] = [];
  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    if (index % 2 === 0) {
      // Collapse the whitespace left behind when adjacent citations are removed.
      const cleaned = part.replace(/\s{2,}/g, " ");
      if (cleaned) nodes.push(...formatted(cleaned, `t-${index}`));
      continue;
    }
    const citationNumber = citations ? citations.findIndex((id) => id.toLowerCase() === part.toLowerCase()) + 1 : 0;
    if (citationNumber > 0) {
      nodes.push(
        <Tooltip title={`Source excerpt ${citationNumber}`} key={`c-${index}`}>
          <Box component="sup" sx={{ color: "text.secondary", fontSize: "0.72em", fontWeight: 600, ml: "2px", whiteSpace: "nowrap", cursor: "default" }}>
            [{citationNumber}]
          </Box>
        </Tooltip>
      );
    }
  }
  return nodes;
}

/** A deliberately small, safe Markdown renderer for LLM-authored lesson text. */
export function MarkdownText({ children, citations }: { children: string; citations?: string[] }) {
  // Some older generated lessons put list markers directly after a sentence. Make those readable too.
  const lines = children.replace(/(?<=\S)\s+- (?=\*\*|[A-Za-z0-9])/g, "\n- ").split("\n");
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | undefined;
  let codeLines: string[] | undefined;

  const flushParagraph = () => {
    if (paragraph.length) blocks.push(<Typography key={`p-${blocks.length}`}>{inline(paragraph.join(" "), citations)}</Typography>);
    paragraph = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((item, index) => (
      <Typography component="li" key={index}>{inline(item, citations)}</Typography>
    ));
    const ListTag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Box component={ListTag} key={`l-${blocks.length}`} sx={{ m: 0, pl: 3, display: "grid", gap: 0.5 }}>
        {items}
      </Box>
    );
    list = undefined;
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
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    const unordered = line.match(/^[-*]\s+(.+)$/);
    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (heading) {
      flushParagraph(); flushList();
      const text = inline(heading[2], citations);
      if (heading[1].length === 1) blocks.push(<Typography variant="h6" sx={{ mt: 1, letterSpacing: "-0.01em" }} key={`h-${blocks.length}`}>{text}</Typography>);
      else blocks.push(<Typography variant="subtitle1" sx={{ mt: 1, letterSpacing: "-0.01em" }} key={`h-${blocks.length}`}>{text}</Typography>);
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
