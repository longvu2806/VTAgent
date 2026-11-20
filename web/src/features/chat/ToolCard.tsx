// A step of the Analyst (SDD §7.6): the calculation it ran, with where each number came
// from, so the user can check the arithmetic as well as the sources.
import type { DynamicToolUIPart } from "ai";
import { CalculatorIcon } from "lucide-react";
import type { CitationOut } from "@/api/types";
import { CitationChip } from "./CitationChip";

interface Operand {
  value: string;
  sid: string; // citation label, or "user" when the number is in the question
}

interface CalculateInput {
  expression: string;
  operands: Record<string, Operand>;
}

const number = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 6 });

export function ToolCard({ part, citations }: { part: DynamicToolUIPart; citations: CitationOut[] }) {
  const done = part.state === "output-available";
  const input = part.input as CalculateInput | undefined;
  const output = part.output as { value: string } | undefined;
  return (
    <section className="flex flex-col gap-2.5 rounded-lg border bg-card px-4 py-3 text-sm" aria-label="Phép tính">
      <header className="flex items-center gap-2 text-muted-foreground">
        <CalculatorIcon className="size-4 text-ink" />
        <span className="font-medium text-foreground">Phép tính</span>
        <span className="ml-auto">{done ? "Đã tính" : part.state === "output-error" ? "Lỗi khi tính" : "Đang tính…"}</span>
      </header>
      {input?.operands && (
        <>
          <code className="font-mono text-[0.82rem] text-muted-foreground">{input.expression.replaceAll("*", "×")}</code>
          <dl className="grid grid-cols-[auto_1fr_auto] items-center gap-x-4 gap-y-1">
            {Object.entries(input.operands).map(([name, o]) => (
              <div key={name} className="contents">
                <dt className="font-mono text-[0.82rem] text-muted-foreground">{name}</dt>
                <dd className="text-right tabular-nums">{number.format(Number(o.value))}</dd>
                <dd>
                  <Source sid={o.sid} citations={citations} />
                </dd>
              </div>
            ))}
          </dl>
        </>
      )}
      {done && output && (
        <p className="flex items-baseline gap-2 border-t pt-2.5">
          <span className="text-muted-foreground">Kết quả</span>
          <span className="ml-auto text-base font-semibold tabular-nums text-ink">{number.format(Number(output.value))}</span>
        </p>
      )}
      {part.state === "output-error" && <p className="text-destructive">{part.errorText}</p>}
    </section>
  );
}

function Source({ sid, citations }: { sid: string; citations: CitationOut[] }) {
  if (sid === "user") return <span className="text-xs text-muted-foreground">từ câu hỏi</span>;
  const citation = citations.find((c) => c.label === sid);
  // The answer's citations arrive after the calculation; until then show the bare label.
  return citation ? (
    <CitationChip citation={citation} all={citations} />
  ) : (
    <span className="text-xs text-muted-foreground tabular-nums">nguồn {sid.slice(1)}</span>
  );
}
