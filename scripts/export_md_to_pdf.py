#!/usr/bin/env python3
"""Export PRISM markdown documentation to PDF."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def md_to_html(md_text: str) -> str:
    import markdown
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.toc import TocExtension

    # Mermaid diagrams are not rendered in PDF — show a readable placeholder
    def mermaid_placeholder(match):
        code = match.group(1).strip()
        preview = code[:200] + ("..." if len(code) > 200 else "")
        return (
            '<div class="diagram-note"><strong>Diagram (see online Markdown viewer for full graphic):</strong>'
            f"<pre>{preview}</pre></div>"
        )

    md_text = re.sub(
        r"```mermaid\s*\n(.*?)```",
        mermaid_placeholder,
        md_text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    body = markdown.markdown(
        md_text,
        extensions=[
            TableExtension(),
            FencedCodeExtension(),
            TocExtension(permalink=False),
            "nl2br",
        ],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>PRISM Portal Guide</title>
  <style>
    @page {{
      size: A4;
      margin: 2cm 1.8cm;
      @frame footer {{
        -pdf-frame-content: footerContent;
        bottom: 0.5cm;
        margin-left: 1.8cm;
        margin-right: 1.8cm;
        height: 1cm;
      }}
    }}
    body {{
      font-family: Helvetica, Arial, sans-serif;
      font-size: 10pt;
      line-height: 1.45;
      color: #1a1a2e;
    }}
    h1 {{ font-size: 22pt; color: #0f172a; border-bottom: 2px solid #ec4899; padding-bottom: 6px; margin-top: 0; }}
    h2 {{ font-size: 15pt; color: #1e293b; margin-top: 22px; page-break-after: avoid; }}
    h3 {{ font-size: 12pt; color: #334155; margin-top: 16px; page-break-after: avoid; }}
    h4 {{ font-size: 11pt; color: #475569; }}
    p, li {{ text-align: justify; }}
    code {{ font-family: Courier, monospace; font-size: 8.5pt; background: #f1f5f9; padding: 1px 4px; }}
    pre {{
      font-family: Courier, monospace;
      font-size: 8pt;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      padding: 8px;
      white-space: pre-wrap;
      word-wrap: break-word;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 12px 0;
      font-size: 9pt;
    }}
    th, td {{
      border: 1px solid #cbd5e1;
      padding: 6px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #f1f5f9; font-weight: bold; }}
    tr:nth-child(even) td {{ background: #fafafa; }}
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }}
    a {{ color: #be185d; text-decoration: none; }}
    .diagram-note {{
      background: #fdf2f8;
      border-left: 4px solid #ec4899;
      padding: 10px 12px;
      margin: 12px 0;
      font-size: 9pt;
    }}
    #footerContent {{
      font-size: 8pt;
      color: #64748b;
      text-align: center;
    }}
  </style>
</head>
<body>
{body}
<div id="footerContent">PRISM — Patient &amp; Admin Portal Guide · Feuji AI/ML · Sprint 3.5</div>
</body>
</html>"""


def html_to_pdf(html: str, out_path: Path) -> None:
    from xhtml2pdf import pisa

    with open(out_path, "wb") as pdf_file:
        status = pisa.CreatePDF(html, dest=pdf_file, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"PDF generation failed with {status.err} error(s)")


def main():
    if len(sys.argv) < 2:
        src = ROOT / "docs" / "PRISM_Patient_and_Admin_Portal_Complete_Guide.md"
    else:
        src = Path(sys.argv[1])
        if not src.is_absolute():
            src = ROOT / src

    if len(sys.argv) >= 3:
        dst = Path(sys.argv[2])
        if not dst.is_absolute():
            dst = ROOT / dst
    else:
        dst = src.with_suffix(".pdf")

    if not src.exists():
        print(f"[ERROR] Source not found: {src}")
        sys.exit(1)

    print(f"[INFO] Reading {src.name}...")
    md_text = src.read_text(encoding="utf-8")
    print("[INFO] Converting Markdown to HTML...")
    html = md_to_html(md_text)
    print(f"[INFO] Writing PDF: {dst}")
    html_to_pdf(html, dst)
    size_kb = dst.stat().st_size / 1024
    print(f"[SUCCESS] PDF created ({size_kb:.1f} KB)")
    print(dst)


if __name__ == "__main__":
    main()
