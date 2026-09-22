import type { ReactNode } from "react";

/** Safe subset markdown → React (no HTML injection). */

function isSafeUrl(url: string): boolean {
  const t = url.trim();
  if (!t) return false;
  if (t.startsWith("/media/")) return true;
  try {
    const u = new URL(t);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function resolveSrc(
  url: string,
  resolveUrl?: (u: string) => string,
): string {
  return resolveUrl ? resolveUrl(url) : url;
}

/** Heading / image lines become blocks even without blank lines around them. */
export function partitionColumnBlocks(source: string): string[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let buf: string[] = [];
  const flush = () => {
    const t = buf.join("\n").trim();
    if (t) out.push(t);
    buf = [];
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^#{1,3} /.test(trimmed)) {
      flush();
      out.push(trimmed);
      continue;
    }
    if (/^!\[[^\]]*\]\([^)]+\)$/.test(trimmed)) {
      flush();
      out.push(trimmed);
      continue;
    }
    if (trimmed === "") {
      flush();
      continue;
    }
    buf.push(line);
  }
  flush();
  return out;
}

function renderInline(
  text: string,
  keyPrefix: string,
  resolveUrl?: (u: string) => string,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  // ***bold+italic*** before **bold** before *italic* so both can stack.
  const re =
    /!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      nodes.push(text.slice(last, m.index));
    }
    const k = `${keyPrefix}-${i++}`;
    if (m[1] !== undefined && m[2] !== undefined) {
      const src = m[2].trim();
      if (isSafeUrl(src)) {
        nodes.push(
          <img
            key={k}
            className="column-md__inline-img"
            src={resolveSrc(src, resolveUrl)}
            alt={m[1]}
          />,
        );
      } else {
        nodes.push(m[0]);
      }
    } else if (m[3] !== undefined && m[4] !== undefined) {
      const href = m[4].trim();
      if (isSafeUrl(href)) {
        nodes.push(
          <a key={k} href={href} target="_blank" rel="noreferrer">
            {m[3]}
          </a>,
        );
      } else {
        nodes.push(m[3]);
      }
    } else if (m[5] !== undefined) {
      nodes.push(
        <strong key={k}>
          <em>{renderInline(m[5], `${k}-bi`, resolveUrl)}</em>
        </strong>,
      );
    } else if (m[6] !== undefined) {
      nodes.push(
        <strong key={k}>{renderInline(m[6], `${k}-b`, resolveUrl)}</strong>,
      );
    } else if (m[7] !== undefined) {
      nodes.push(
        <em key={k}>{renderInline(m[7], `${k}-i`, resolveUrl)}</em>,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function ColumnMarkdownView({
  source,
  resolveUrl,
  emptyText = "아직 칼럼 본문이 없어요.",
  className = "column-md",
}: {
  source: string;
  resolveUrl?: (url: string) => string;
  emptyText?: string;
  className?: string;
}) {
  const text = (source || "").trim();
  if (!text) {
    return <p className="column-md__muted">{emptyText}</p>;
  }

  const blocks = partitionColumnBlocks(text);
  return (
    <div className={className}>
      {blocks.map((block, bi) => {
        if (!block) return null;
        const imgOnly = /^!\[([^\]]*)\]\(([^)]+)\)$/.exec(block);
        if (imgOnly) {
          const src = imgOnly[2].trim();
          if (!isSafeUrl(src)) return null;
          return (
            <figure key={`b-${bi}`} className="column-md__figure">
              <img
                src={resolveSrc(src, resolveUrl)}
                alt={imgOnly[1]}
                className="column-md__img"
              />
            </figure>
          );
        }
        if (block.startsWith("### ")) {
          return (
            <h3 key={`b-${bi}`} className="column-md__h">
              {renderInline(block.slice(4), `h-${bi}`, resolveUrl)}
            </h3>
          );
        }
        if (block.startsWith("## ")) {
          return (
            <h3 key={`b-${bi}`} className="column-md__h">
              {renderInline(block.slice(3), `h-${bi}`, resolveUrl)}
            </h3>
          );
        }
        if (block.startsWith("# ")) {
          return (
            <h2 key={`b-${bi}`} className="column-md__h">
              {renderInline(block.slice(2), `h-${bi}`, resolveUrl)}
            </h2>
          );
        }
        const lines = block.split("\n");
        return (
          <p key={`b-${bi}`} className="column-md__p">
            {lines.map((line, li) => (
              <span key={`l-${bi}-${li}`}>
                {li > 0 ? <br /> : null}
                {renderInline(line, `p-${bi}-${li}`, resolveUrl)}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}
