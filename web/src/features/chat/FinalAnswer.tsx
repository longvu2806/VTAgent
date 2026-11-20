// The verified answer: Markdown with inline citation chips and a mark after each
// sentence the Validator could not support (BR07).
import { TriangleAlertIcon } from "lucide-react";
import { type ComponentProps, useMemo } from "react";
import { type Components, Streamdown } from "streamdown";
import type { VerificationData } from "@/api/stream";
import type { CitationOut } from "@/api/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ANSWER_TAGS, answerMarkdown } from "@/lib/answer";
import { CitationChip } from "./CitationChip";

interface Props {
  text: string;
  citations: CitationOut[];
  verification: VerificationData | undefined;
}

export function FinalAnswer({ text, citations, verification }: Props) {
  const unsupported = useMemo(
    () => new Map((verification?.sentences ?? []).filter((s) => !s.supported).map((s) => [s.index, s.reason])),
    [verification],
  );
  const markdown = useMemo(
    () => answerMarkdown(text, new Set(citations.map((c) => c.label)), new Set(unsupported.keys())),
    [text, citations, unsupported],
  );
  const components = useMemo(
    () =>
      ({
        vtcite: ({ label }: { label?: string }) => {
          const citation = citations.find((c) => c.label === label);
          return citation ? <CitationChip citation={citation} all={citations} /> : null;
        },
        vtwarn: ({ index }: { index?: string }) => <UnsupportedMark reason={unsupported.get(Number(index)) ?? ""} />,
        a: ({ children }: ComponentProps<"a">) => <span>{children}</span>, // no outbound links from answers
      }) as Components,
    [citations, unsupported],
  );
  return (
    <Streamdown
      mode="static"
      allowedTags={ANSWER_TAGS}
      components={components}
      className="answer text-[1.02rem] leading-[1.75]"
    >
      {markdown}
    </Streamdown>
  );
}

function UnsupportedMark({ reason }: { reason: string }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            className="mx-0.5 inline-flex -translate-y-px items-center rounded-[5px] bg-caution-soft px-1 align-baseline text-caution"
            aria-label={`Câu này chưa đủ căn cứ: ${reason}`}
          />
        }
      >
        <TriangleAlertIcon className="size-3.5" />
      </TooltipTrigger>
      <TooltipContent className="max-w-72">Chưa đủ căn cứ trong nguồn được trích. {reason}</TooltipContent>
    </Tooltip>
  );
}
