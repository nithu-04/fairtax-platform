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
        children: [new TextRun("Key Learnings From FairTax Development")]
      }),

      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 240 },
        children: [new TextRun({ text: "Insights and Best Practices Discovered", italic: true, size: 22 })]
      }),

      // Section 1
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("1. Frontend Architecture & CSS")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "CSS Grid is More Stable Than Absolute Positioning: ", bold: true }), new TextRun("Absolute positioning caused layout instability; migrating to CSS Grid provided a more robust, maintainable foundation for complex layouts")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Cache Busting is Essential: ", bold: true }), new TextRun("CSS changes require version increments for cache invalidation. Failing to bust cache can leave users with stale styles")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Premium Design Requires Iterative Refinement: ", bold: true }), new TextRun("Implementing a premium fintech aesthetic across multiple pages took several phased iterations. Each phase built upon learnings from the previous one")]
      }),

      // Section 2
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("2. JavaScript & Event Handling")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Event Listeners Are More Reliable Than Inline Handlers: ", bold: true }), new TextRun("Using addEventListener() in a separate JavaScript file is more maintainable and avoids null reference errors compared to inline onclick attributes")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Script Loading Order Matters: ", bold: true }), new TextRun("Loading app.js in the document head ensures functions are available before buttons try to call them")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Conditional Validation Prevents Unnecessary Friction: ", bold: true }), new TextRun("Document type validation should be non-blocking and context-aware; checking only required fields at appropriate steps improves UX")]
      }),

      // Section 3
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("3. Backend & Deployment")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Separate Frontend and Backend Deployments: ", bold: true }), new TextRun("Attempting to deploy both frontend and backend to Vercel created complexity. Separating them (e.g., frontend on Vercel, backend on Render) simplified deployment and scaling")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Environment-Based Configuration is Non-Negotiable: ", bold: true }), new TextRun("Using environment variables for API endpoints and credentials prevents hardcoding and makes code portable across environments")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Python Version Management Requires Explicit Configuration: ", bold: true }), new TextRun("Version mismatches between local and production environments cause unexpected failures. Always specify Python version explicitly in deployment configs")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "CORS Issues Are Common in Frontend-Backend Architecture: ", bold: true }), new TextRun("Proper CORS configuration is critical for local development and production. Testing with actual endpoints early prevents late-stage surprises")]
      }),

      // Section 4
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("4. Data Processing & Vision Extraction")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Vision-Based Extraction Outperforms Traditional OCR: ", bold: true }), new TextRun("Moving from OCR to Vision API extraction improved accuracy and robustness for document processing")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Robust Pipeline Sequencing is Critical: ", bold: true }), new TextRun("The processing pipeline (PDF conversion → image generation → vision extraction → normalization → validation → quality check) requires careful error handling at each stage")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Edge Cases Demand Specific Handling: ", bold: true }), new TextRun("Consecutive blank pages, corrupted PDFs, and unusual file formats require explicit detection and handling rather than generic error messages")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Comprehensive Error Logging is Essential: ", bold: true }), new TextRun("Minimal try-catch blocks make debugging difficult. Comprehensive logging at each stage of processing helps identify and fix issues quickly")]
      }),

      // Section 5
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("5. Authentication & Credentials")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "OAuth Scopes Must Match Use Cases: ", bold: true }), new TextRun("Google Sheets OAuth requires careful scope configuration. Too broad = security risk; too narrow = functionality breaks")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Never Hardcode Sensitive Data: ", bold: true }), new TextRun("Phone numbers, API keys, and other credentials must always come from environment variables or secure configuration files, never from source code")]
      }),

      // Section 6
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("6. Tax Calculation & Business Logic")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Multi-Layer Validation Prevents Calculation Errors: ", bold: true }), new TextRun("Tax calculations require validation at the client, server, and API layers to catch regime mismatches and incorrect recommendations")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Variant Calculations Need Independent Verification: ", bold: true }), new TextRun("Comparing Old Regime, New Regime, and other variants requires comprehensive testing against known-good results from official tax documents")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Business Logic Should Be Centralized: ", bold: true }), new TextRun("Duplicating calculation logic across frontend and backend creates maintenance nightmares. Centralize on the server with clear APIs")]
      }),

      // Section 7
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("7. Design System & UI Patterns")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Asymmetrical Overlapping Layouts Work for Premium UX: ", bold: true }), new TextRun("Breaking away from rigid grid layouts creates visual interest and conveys premium positioning, though it requires careful iteration")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Parallel Animations Enhance User Engagement: ", bold: true }), new TextRun("Scroll-based parallax and floating animations subtly guide user attention and create a more immersive experience")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Consistent Spacing and Naming Standards Reduce Bugs: ", bold: true }), new TextRun("Well-defined CSS naming conventions and spacing scales (before, after, margins) make style modifications safer and faster")]
      }),

      // Section 8
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("8. Documentation & Type Safety")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Document Type Guidance Improves Data Quality: ", bold: true }), new TextRun("Clear guidance on which document types are accepted and what each should contain reduces processing failures and user frustration")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Non-Blocking Validation Improves Conversion: ", bold: true }), new TextRun("Presenting validation issues as warnings rather than hard blocks allows users to understand constraints while maintaining control")]
      }),

      // Section 9
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("9. Testing & Verification")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Multiple Iterations Are Normal: ", bold: true }), new TextRun("The Joker button required 4+ commits and multiple approaches before stabilizing. Don't expect complex features to work perfectly on first attempt")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Cross-Browser and Cross-Device Testing is Critical: ", bold: true }), new TextRun("CSS visibility issues often vary by browser and device. Testing in production-like environments prevents surprises")]
      }),

      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun({ text: "Automated Testing Prevents Regressions: ", bold: true }), new TextRun("Manual testing works early, but automated tests become essential as the codebase grows and features interact")]
      }),

      // Section 10
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun("10. Project Management Insights")]
      }),

      new Paragraph({
        spacing: { after: 80, before: 40 },
        children: [new TextRun({ text: "Phased Rollouts Reduce Risk: ", bold: true }), new TextRun("Breaking a large redesign into phases (PHASE 1: Landing Page, PHASE 2: Choice Page, PHASE 3: All Pages) allowed validation and iteration at each step")]
      }),

      new Paragraph({
        spacing: { after: 80 },
        children: [new TextRun({ text: "Clear Naming Conventions Aid Context: ", bold: true }), new TextRun("Commit messages like 'PHASE 2: Complete premium immersive landing page redesign' clearly communicate scope and intent")]
      }),

      new Paragraph({
        spacing: { after: 240 },
        children: [new TextRun({ text: "Refactoring Takes Time: ", bold: true }), new TextRun("Moving from absolute positioning to CSS Grid, replacing OCR with Vision, or restructuring layouts is not quick. Plan accordingly and don't rush architectural changes")]
      })
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("Learnings_FairTax.docx", buffer);
  console.log("Document created: Learnings_FairTax.docx");
});
