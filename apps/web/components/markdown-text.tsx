import { Fragment, ReactNode } from "react";

const CITATION_PATTERN = /\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]/gi;

function formatted(text: string, keyPrefix: string): ReactNode[] {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**")) return <strong key={`${keyPrefix}-${index}`}>{token.slice(2, -2)}</strong>;
    if (token.startsWith("`") && token.endsWith("`")) return <code key={`${keyPrefix}-${index}`}>{token.slice(1, -1)}</code>;
    return <Fragment key={`${keyPrefix}-${index}`}>{token}</Fragment>;
  });
}

/** Inline chunk citations ([uuid]) become numbered chips when the citation list is
 *  known, and disappear entirely when it is not — learners never see raw UUIDs. */
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
        <sup className="citation-ref" title={`Source excerpt ${citationNumber}`} key={`c-${index}`}>
          [{citationNumber}]
        </sup>
      );
    }
  }
  return nodes;
}

/** A deliberately small, safe Markdown renderer for LLM-authored lesson text. */
export function MarkdownText({ children, className, citations }: { children: string; className?: string; citations?: string[] }) {
  // Some older generated lessons put list markers directly after a sentence. Make those readable too.
  const lines = children.replace(/(?<=\S)\s+- (?=\*\*|[A-Za-z0-9])/g, "\n- ").split("\n");
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | undefined;
  let codeLines: string[] | undefined;

  const flushParagraph = () => {
    if (paragraph.length) blocks.push(<p key={`p-${blocks.length}`}>{inline(paragraph.join(" "), citations)}</p>);
    paragraph = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((item, index) => <li key={index}>{inline(item, citations)}</li>);
    blocks.push(list.ordered ? <ol key={`o-${blocks.length}`}>{items}</ol> : <ul key={`u-${blocks.length}`}>{items}</ul>);
    list = undefined;
  };

  for (const line of lines) {
    if (line.trimStart().startsWith("```")) {
      flushParagraph(); flushList();
      if (codeLines) {
        blocks.push(<pre className="markdown-code" key={`code-${blocks.length}`}><code>{codeLines.join("\n")}</code></pre>);
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
      if (heading[1].length === 1) blocks.push(<h2 key={`h-${blocks.length}`}>{text}</h2>);
      else blocks.push(<h3 key={`h-${blocks.length}`}>{text}</h3>);
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
  if (codeLines) blocks.push(<pre className="markdown-code" key={`code-${blocks.length}`}><code>{codeLines.join("\n")}</code></pre>);
  return <div className={`markdown-text${className ? ` ${className}` : ""}`}>{blocks}</div>;
}
