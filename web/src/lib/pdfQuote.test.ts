import { describe, expect, it } from "vitest";
import { quoteItems } from "./pdfQuote";

// Fragments as a PDF export splits a justified paragraph.
const items = [
  { str: "1. Bên vi phạm phải chịu " },
  { str: "nghĩa vụ" },
  { str: "" },
  { str: "2. Trường hợ" },
  { str: "p Bên B giao hàng chậm, " },
  {}, // marked content
  { str: "Bên B chịu phạt." },
  { str: "3. Việc trả tiền phạt không miễn trừ nghĩa vụ" },
];

describe("quoteItems", () => {
  it("marks every fragment of the quote, across lines and split words", () => {
    expect(quoteItems(items, "2. Trường hợp Bên B giao hàng chậm,\nBên B chịu phạt.")).toEqual(new Set([3, 4, 6]));
  });

  it("does not mark the same words elsewhere on the page", () => {
    expect(quoteItems(items, "2. Trường hợp Bên B giao hàng chậm,").has(7)).toBe(false);
  });

  it("finds nothing when the quote is not on the page", () => {
    expect(quoteItems(items, "Điều khoản trọng tài")).toEqual(new Set());
  });
});
