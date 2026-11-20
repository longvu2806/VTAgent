// Shared cover page, styles, header and footer for the doc/sdlc/ phase documents.
const fs = require("fs");
const { d, table, FONT, NAVY, PAGE } = require("./lib");

function build(out, { phase, subtitle, headerText, info, body }) {
  const front = [
    new d.Paragraph({ children: [], spacing: { before: 2600 } }),
    new d.Paragraph({ children: [new d.TextRun({ text: "VTAgent", bold: true, size: 56, color: NAVY })], alignment: d.AlignmentType.CENTER, spacing: { after: 200 } }),
    new d.Paragraph({ children: [new d.TextRun({ text: "Trợ lý hỏi đáp tài liệu nội bộ đa thể loại, chạy hoàn toàn cục bộ", size: 28, color: "44546A" })], alignment: d.AlignmentType.CENTER, spacing: { after: 600 } }),
    new d.Paragraph({ children: [new d.TextRun({ text: phase, bold: true, size: 36 })], alignment: d.AlignmentType.CENTER, spacing: { after: 160 } }),
    new d.Paragraph({ children: [new d.TextRun({ text: subtitle, size: 28 })], alignment: d.AlignmentType.CENTER, spacing: { after: 1400 } }),
    table(["Thuộc tính", "Nội dung"], info, [0.28, 0.72]),
    new d.Paragraph({ children: [new d.PageBreak()] }),
    new d.Paragraph({ children: [new d.TextRun({ text: "Mục lục", bold: true, size: 30, color: NAVY })], spacing: { after: 200 } }),
    new d.TableOfContents("Mục lục", { hyperlink: true, headingStyleRange: "1-2" }),
  ];
  const styles = {
    default: { document: { run: { font: FONT, size: 26 } } },
    paragraphStyles: [1, 2, 3].map((n) => ({
      id: `Heading${n}`, name: `Heading ${n}`, basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: [30, 26, 24][n - 1], bold: true, color: n < 3 ? NAVY : "2C3E50" },
      paragraph: { spacing: { before: 240, after: n === 1 ? 160 : 100 }, keepNext: true, keepLines: true, outlineLevel: n - 1 },
    })),
  };
  const numbering = { config: [
    { reference: "bullets", levels: [{ level: 0, format: d.LevelFormat.BULLET, text: "•", alignment: d.AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: d.LevelFormat.DECIMAL, text: "%1.", alignment: d.AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] };
  const header = new d.Header({ children: [new d.Paragraph({ alignment: d.AlignmentType.RIGHT, children: [new d.TextRun({ text: headerText, size: 18, color: "808080" })] })] });
  const footer = new d.Footer({ children: [new d.Paragraph({ alignment: d.AlignmentType.CENTER, children: [new d.TextRun({ children: ["Trang ", d.PageNumber.CURRENT], size: 20, color: "606060" })] })] });
  const margin = { top: PAGE.margin, bottom: PAGE.margin, left: PAGE.margin, right: PAGE.margin };
  const page = { page: { size: { width: PAGE.width, height: PAGE.height }, margin } };
  const wide = { page: { size: { width: PAGE.width, height: PAGE.height, orientation: d.PageOrientation.LANDSCAPE }, margin } };
  // A body item {landscape: [...]} gets a landscape section of its own (wide figures).
  const sections = [];
  let run = [];
  const flush = (props, children) => children.length && sections.push(
    { properties: { ...props, type: d.SectionType.NEXT_PAGE }, headers: { default: header }, footers: { default: footer }, children: children.flat(2) });
  for (const item of body) {
    if (item && item.landscape) { flush(page, run); run = []; flush(wide, item.landscape); } else run.push(item);
  }
  flush(page, run);
  const doc = new d.Document({
    creator: "VTAgent", title: `VTAgent – ${phase}`, styles, numbering,
    sections: [{ properties: page, children: front.flat(2) }, ...sections],
  });
  return d.Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("wrote", out, buf.length); });
}

module.exports = { build };
