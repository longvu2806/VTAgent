// Turns a verified answer into Markdown the renderer can decorate: [S#] labels become
// <vtcite> tags and a <vtwarn> tag follows every sentence the Validator flagged.

const LABELS = /\[(S\d+(?:\s*,\s*S\d+)*)\]/g;
// A sentence ends at . ! ? or … followed by whitespace and an uppercase letter, a quote,
// a bracket or emphasis; "0,05%." inside a sentence does not match because no space follows.
const SENTENCE_END = /(?<=[.!?…])\s+(?=[\p{Lu}"“(*\[])/u;

/** Tags the renderer maps to components, with their permitted attributes. */
export const ANSWER_TAGS = { vtcite: ["label"], vtwarn: ["index"] };

export function splitSentences(text: string): string[] {
  return text
    .split(/\n+/)
    .flatMap((line) => line.split(SENTENCE_END))
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Replace "[S1, S3]" with citation tags; labels that are not among the citations are dropped (BR08). */
export function tagCitations(text: string, known: ReadonlySet<string>): string {
  return text.replace(LABELS, (_, group: string) =>
    group
      .split(",")
      .map((l) => l.trim())
      .filter((l) => known.has(l))
      .map((l) => `<vtcite label="${l}"></vtcite>`)
      .join(""),
  );
}

/** Markdown for display: citation tags, and a warning tag after each flagged sentence. */
export function answerMarkdown(text: string, known: ReadonlySet<string>, flagged: ReadonlySet<number>): string {
  let index = 0;
  return text
    .split(/(\n+)/)
    .map((chunk) => {
      if (/^\n+$/.test(chunk)) return chunk;
      return chunk
        .split(SENTENCE_END)
        .map((sentence) => {
          const tagged = tagCitations(sentence, known);
          const i = index++;
          return flagged.has(i) ? `${tagged}<vtwarn index="${i}"></vtwarn>` : tagged;
        })
        .join(" ");
    })
    .join("");
}
