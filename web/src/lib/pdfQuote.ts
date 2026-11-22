// Find a quoted passage in a PDF page's text layer. PDF text comes in fragments that split
// lines and words anywhere, so the page is joined and every fragment overlapping a match is a
// hit. Only letters and digits are compared: the quote is Markdown from the parser
// ("**Điều 8.**", table pipes), the text layer is plain. The quote is matched line by line and
// sentence by sentence, because a chunk may run onto the next page or carry the page footer,
// which the text layer puts elsewhere.

const compact = (s: string) => s.normalize("NFC").replace(/[^\p{L}\p{N}]+/gu, "");
// Shorter pieces ("Điều 5.", "1.") would match all over the page.
const MIN_PIECE = 12;

/** Indexes of the text items holding the parts of the quote found on this page. */
export function quoteItems(items: readonly object[], quote: string): Set<number> {
  const ranges: [number, number, number][] = []; // item index, start, end in the joined text
  let joined = "";
  items.forEach((item, i) => {
    if (!("str" in item) || typeof item.str !== "string") return; // marked content, not text
    const text = compact(item.str);
    if (text) ranges.push([i, joined.length, joined.length + text.length]);
    joined += text;
  });
  const hits = new Set<number>();
  for (const piece of quote.split(/\n+|(?<=[.;:!?])\s+/)) {
    const target = compact(piece);
    const at = target.length >= MIN_PIECE ? joined.indexOf(target) : -1;
    if (at < 0) continue;
    const end = at + target.length;
    for (const [i, start, stop] of ranges) if (start < end && stop > at) hits.add(i);
  }
  return hits;
}
