import { describe, expect, it } from "vitest";
import { answerMarkdown, splitSentences, tagCitations } from "./answer";

const known = new Set(["S1", "S2", "S3"]);
const cite = (l: string) => `<vtcite label="${l}"></vtcite>`;

describe("tagCitations", () => {
  it("tags single and grouped labels", () => {
    expect(tagCitations("Phạt 0,05% [S1].", known)).toBe(`Phạt 0,05% ${cite("S1")}.`);
    expect(tagCitations("Hai nguồn [S1, S3].", known)).toBe(`Hai nguồn ${cite("S1")}${cite("S3")}.`);
  });

  it("drops labels that point to no citation", () => {
    expect(tagCitations("Sai nhãn [S9].", known)).toBe("Sai nhãn .");
    expect(tagCitations("Một đúng [S2, S9].", known)).toBe(`Một đúng ${cite("S2")}.`);
  });
});

describe("splitSentences", () => {
  it("keeps decimals and percentages inside a sentence", () => {
    expect(splitSentences("Phạt 0,05% mỗi ngày [S1]. Tối đa 8% [S1]. Trùng với luật [S2].")).toHaveLength(3);
  });

  it("splits on line breaks", () => {
    expect(splitSentences("Dòng một.\n\nDòng hai.")).toEqual(["Dòng một.", "Dòng hai."]);
  });
});

describe("answerMarkdown", () => {
  it("adds a warning tag after flagged sentences only", () => {
    const md = answerMarkdown("Câu một [S1]. Câu hai [S2]. Câu ba.", known, new Set([1]));
    expect(md).toBe(`Câu một ${cite("S1")}. Câu hai ${cite("S2")}.<vtwarn index="1"></vtwarn> Câu ba.`);
  });
});
