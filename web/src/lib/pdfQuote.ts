// Find a quoted passage in a PDF page's text layer. PDF text comes in fragments that split
// lines and words anywhere, so the page is joined without whitespace and every fragment
// overlapping the quote's span is a hit.

const compact = (s: string) => s.replace(/\s+/g, "");

/** Indexes of the text items that together hold the quote; empty when it is not on the page. */
export function quoteItems(items: readonly object[], quote: string): Set<number> {
  const ranges: [number, number, number][] = []; // item index, start, end in the joined text
  let joined = "";
  items.forEach((item, i) => {
    if (!("str" in item) || typeof item.str !== "string") return; // marked content, not text
    const text = compact(item.str);
    if (text) ranges.push([i, joined.length, joined.length + text.length]);
    joined += text;
  });
  const target = compact(quote);
  const at = target ? joined.indexOf(target) : -1;
  if (at < 0) return new Set();
  const end = at + target.length;
  return new Set(ranges.filter(([, s, e]) => s < end && e > at).map(([i]) => i));
}
