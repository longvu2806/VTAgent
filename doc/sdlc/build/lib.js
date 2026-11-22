// Building blocks for the SDLC documents: headings, paragraphs with **bold** / `code` markup,
// tables, captions, code blocks, notes and figures. Run with NODE_PATH pointing at a folder
// where the `docx` npm package is installed.
const fs = require("fs");
const d = require("docx");

const FONT = "Times New Roman";
const MONO = "Consolas";
const NAVY = "1F3864";
const HEAD_FILL = "DCE6F1";
const PAGE = { width: 11906, height: 16838, margin: 1440 };
const CONTENT = PAGE.width - 2 * PAGE.margin;

function runs(text, base = {}) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map((part) => {
    if (part.startsWith("**")) return new d.TextRun({ text: part.slice(2, -2), bold: true, ...base });
    if (part.startsWith("`")) return new d.TextRun({ text: part.slice(1, -1), font: MONO, size: 22, ...base });
    return new d.TextRun({ text: part, ...base });
  });
}

const P = (text, opts = {}) => new d.Paragraph({
  children: runs(text, opts.run || {}),
  alignment: opts.align || d.AlignmentType.JUSTIFIED,
  spacing: { after: opts.after ?? 120, before: opts.before ?? 0, line: 276 },
  keepNext: opts.keepNext,
});
const H1 = (t) => new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, children: [new d.TextRun(t)], pageBreakBefore: true });
const H2 = (t) => new d.Paragraph({ heading: d.HeadingLevel.HEADING_2, children: [new d.TextRun(t)] });
const H3 = (t) => new d.Paragraph({ heading: d.HeadingLevel.HEADING_3, children: [new d.TextRun(t)] });

let listInstance = 0;
const bullets = (items) => items.map((t) => new d.Paragraph({
  children: runs(t), numbering: { reference: "bullets", level: 0 },
  alignment: d.AlignmentType.JUSTIFIED, spacing: { after: 60, line: 276 },
}));
function numbered(items) {
  const instance = ++listInstance;
  return items.map((t) => new d.Paragraph({
    children: runs(t), numbering: { reference: "numbers", level: 0, instance },
    alignment: d.AlignmentType.JUSTIFIED, spacing: { after: 60, line: 276 },
  }));
}

const caption = (t) => new d.Paragraph({
  children: [new d.TextRun({ text: t, italics: true, size: 24 })],
  alignment: d.AlignmentType.CENTER, spacing: { before: 60, after: 200 },
});

const border = (color = "A6A6A6") => ({ style: d.BorderStyle.SINGLE, size: 4, color });
const borders = (c) => ({ top: border(c), bottom: border(c), left: border(c), right: border(c) });

function table(headers, rows, fractions, opts = {}) {
  const total = opts.width || CONTENT;
  const widths = fractions.map((f) => Math.floor(total * f));
  widths[widths.length - 1] = total - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  const size = opts.size || 22;
  const cell = (text, i, head) => new d.TableCell({
    width: { size: widths[i], type: d.WidthType.DXA },
    borders: borders(),
    shading: head ? { fill: HEAD_FILL, type: d.ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    verticalAlign: d.VerticalAlign.CENTER,
    children: String(text).split("\n").map((line) => new d.Paragraph({
      children: runs(line, head ? { bold: true, size } : { size }),
      alignment: head || (opts.center || []).includes(i) ? d.AlignmentType.CENTER : d.AlignmentType.LEFT,
      spacing: { after: 0, line: 252 }, keepNext: true,
    })),
  });
  return new d.Table({
    width: { size: total, type: d.WidthType.DXA },
    columnWidths: widths,
    rows: [
      new d.TableRow({ tableHeader: true, cantSplit: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r) => new d.TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, i, false)) })),
    ],
  });
}

const gap = () => new d.Paragraph({ children: [], spacing: { after: 60 } });

function note(title, text, fill = "FFF8E1", color = "BF9000") {
  const paras = Array.isArray(text) ? text : [text];
  return [new d.Table({
    width: { size: CONTENT, type: d.WidthType.DXA },
    columnWidths: [CONTENT],
    rows: [new d.TableRow({ cantSplit: true, children: [new d.TableCell({
      width: { size: CONTENT, type: d.WidthType.DXA },
      borders: borders(color),
      shading: { fill, type: d.ShadingType.CLEAR, color: "auto" },
      margins: { top: 100, bottom: 100, left: 160, right: 160 },
      children: [
        new d.Paragraph({ children: [new d.TextRun({ text: title, bold: true, size: 24 })], spacing: { after: 60 } }),
        ...paras.map((t) => new d.Paragraph({ children: runs(t, { size: 24 }), alignment: d.AlignmentType.JUSTIFIED, spacing: { after: 60, line: 264 } })),
      ],
    })] })],
  }), gap()];
}

// A shaded monospace block for SQL, JSON, pseudo-code; one paragraph per line keeps indentation.
function code(text, size = 15) {
  return [new d.Table({
    width: { size: CONTENT, type: d.WidthType.DXA },
    columnWidths: [CONTENT],
    rows: [new d.TableRow({ cantSplit: true, children: [new d.TableCell({
      width: { size: CONTENT, type: d.WidthType.DXA },
      borders: borders("BFBFBF"),
      shading: { fill: "F5F5F5", type: d.ShadingType.CLEAR, color: "auto" },
      margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: text.replace(/\n$/, "").split("\n").map((line) => new d.Paragraph({
        children: [new d.TextRun({ text: line || " ", font: MONO, size })],
        spacing: { after: 0, line: 240 }, keepNext: true,
      })),
    })] })],
  }), gap()];
}

function figure(path, widthPx) {
  const b = fs.readFileSync(path);
  const w = b.readUInt32BE(16), h = b.readUInt32BE(20);
  return new d.Paragraph({
    children: [new d.ImageRun({ type: "png", data: b, transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })],
    alignment: d.AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
  });
}

module.exports = { d, P, H1, H2, H3, bullets, numbered, caption, table, note, gap, code, figure, FONT, NAVY, PAGE, CONTENT };
