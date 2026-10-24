"use client";
/* Minimal, safe reply renderer. Produces React nodes only — never
 * dangerouslySetInnerHTML — so model output cannot inject markup.
 * Supports: paragraphs, "- " bullets, **bold**, `code`, and [n] citations
 * which become clickable chips bound to the grounding sources. */
import { Fragment, type ReactNode } from "react";

export function renderInline(text: string, onCite?: (n: number) => void, max?: number): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[(\d{1,2})\])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={k++} className="font-semibold text-[var(--text)]">{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) out.push(<code key={k++} className="mono rounded bg-[var(--overlay)] px-1 text-[11px] text-[var(--secondary)]">{tok.slice(1, -1)}</code>);
    else {
      const n = Number(m[2]);
      const valid = !max || (n >= 1 && n <= max);
      out.push(
        valid ? (
          <button
            key={k++}
            type="button"
            onClick={() => onCite?.(n)}
            className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-[color-mix(in_srgb,var(--primary)_var(--tint-strong),transparent)] px-1 align-[1px] text-[10px] font-semibold tabular text-[var(--primary)] hover:bg-[var(--primary)] hover:text-[var(--on-primary)]"
            title={`Show source ${n}`}
          >
            {n}
          </button>
        ) : (
          // A citation number with no matching source is shown as plain text,
          // flagged — the model cited something it was not given.
          <span key={k++} className="text-[var(--danger)]" title="Cited source not in context">{tok}</span>
        ),
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function ReplyText({ text, onCite, sourceCount }: { text: string; onCite?: (n: number) => void; sourceCount?: number }) {
  const blocks = text.trim().split(/\n{2,}/);
  return (
    <div className="space-y-2 text-[13px] leading-relaxed text-[var(--text-secondary)]">
      {blocks.map((b, i) => {
        const lines = b.split("\n");
        const bullets = lines.every((l) => /^\s*[-*•]\s+/.test(l));
        if (bullets) {
          return (
            <ul key={i} className="space-y-1 pl-1">
              {lines.map((l, j) => (
                <li key={j} className="flex gap-2">
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[var(--text-tertiary)]" />
                  <span>{renderInline(l.replace(/^\s*[-*•]\s+/, ""), onCite, sourceCount)}</span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i}>
            {lines.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {renderInline(l.replace(/^#+\s*/, ""), onCite, sourceCount)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}
