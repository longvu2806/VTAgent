// The answer stream: AI SDK UI Message Stream v1 plus VTAgent data parts.
// The draft streams as reasoning parts; the verified answer arrives as one text part.
import type { UIMessage, UIMessageChunk } from "ai";
import type { CitationOut, TurnStatus } from "./types";

export type StageNode =
  | "route" | "retrieve" | "answer" | "plan" | "tools" | "interpret" | "verify" | "retry" | "finalize";

export interface StageData {
  node: StageNode;
  round: number;
  detail?: string;
}

export interface SentenceCheck {
  index: number;
  supported: boolean;
  reason: string;
}

export interface VerificationData {
  sentences: SentenceCheck[];
}

export interface TurnData {
  id: string;
  status: TurnStatus;
  missing: string | null;
  latency_ms: number | null;
}

export type VTDataParts = {
  stage: StageData;
  verification: VerificationData;
  citations: CitationOut[];
  turn: TurnData;
};

export type VTMessage = UIMessage<never, VTDataParts>;
export type VTChunk = UIMessageChunk<never, VTDataParts>;
