const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageOrientation, WidthType } = require('docx');
const fs = require('fs');

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: 22 }
      }
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1F4E78" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 }
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2E5C8A" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 }
      }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: {
          width: 12240,
          height: 15840
        },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      // Title
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [new TextRun("Problems Faced During FairTax Development")]
      }),

      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 240 },
        children: [new TextRun({ text: "Comprehensive Summary of Technical Challenges", italic: true, size: 22 })]
      }),

      // Section 1
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("1. Frontend UI/Layout Issues")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Joker Button Visibility: ", bold: true }), new TextRun("Multiple attempts needed to ensure button visibility. Required aggressive CSS with !important flags and multiple commits to resolve")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Navbar Spacing: ", bold: true }), new TextRun("Logo and button positioning required several iterations to achieve proper spacing")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Layout Conversion: ", bold: true }), new TextRun("Initial absolute positioning caused instability; required conversion to CSS Grid for better stability")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "White Space Issues: ", bold: true }), new TextRun("Extra spacing above banners on multiple pages needed removal")]
      }),

      // Section 2
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("2. Button & Component Functionality")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Reveal Code Button: ", bold: true }), new TextRun("Broken null references that required event listener implementation fixes")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Button State Management: ", bold: true }), new TextRun("WhatsApp code sending and modal messaging required debugging")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Form Validation: ", bold: true }), new TextRun("Document type validation needed careful design to avoid blocking user flow")]
      }),

      // Section 3
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("3. Backend & Deployment Issues")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Python Version Mismatch: ", bold: true }), new TextRun("Version conflicts during deployment")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "CORS Errors: ", bold: true }), new TextRun("Multiple fixes needed for frontend-backend communication")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "API Routing: ", bold: true }), new TextRun("Localhost URLs needed to be replaced with production endpoints")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Vercel Configuration: ", bold: true }), new TextRun("Backend deployment attempts on Vercel failed; required separation from frontend")]
      }),

      // Section 4
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("4. Data & Credentials Management")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Hardcoded Values: ", bold: true }), new TextRun("Phone numbers and other hardcoded data found in production code")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "OAuth Configuration: ", bold: true }), new TextRun("Google Sheets OAuth scopes required adjustment")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Error Handling: ", bold: true }), new TextRun("Minimal try-catch blocks in vision extraction and PDF processing")]
      }),

      // Section 5
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("5. HTML & Symbol Issues")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Symbol Placeholders: ", bold: true }), new TextRun("Bracket placeholders needed conversion to proper Unicode symbols")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "HTML Structure: ", bold: true }), new TextRun("Layout issues from centered max-width requiring conversion to full-width flowing sections")]
      }),

      // Section 6
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("6. Calculation & Data Processing")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Tax Calculation Accuracy: ", bold: true }), new TextRun("Issues with variant calculations (variant_b_refund, variant_c_refund) showing incorrect regime recommendations")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Vision Extraction: ", bold: true }), new TextRun("Document processing pipeline required robust error handling")]
      }),

      // Section 7
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("7. UI/UX Design Iteration")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Multiple Redesign Cycles: ", bold: true }), new TextRun("Premium fintech aesthetic required several phases of implementation")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Overlapping Layout Challenges: ", bold: true }), new TextRun("Asymmetrical overlapping card designs needed multiple revisions to achieve proper visual hierarchy")]
      }),

      // Section 8
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("8. Document Processing")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "File Conversion Pipeline: ", bold: true }), new TextRun("PDF/image → images → vision extraction → normalization → validation required careful sequencing")]
      }),

      new Paragraph({
        spacing: { after: 240 },
        children: [new TextRun({ text: "Consecutive Blank Pages: ", bold: true }), new TextRun("Edge case handling in PDF conversion needed attention")]
      })
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("Problems_Faced_FairTax.docx", buffer);
  console.log("Document created: Problems_Faced_FairTax.docx");
});
