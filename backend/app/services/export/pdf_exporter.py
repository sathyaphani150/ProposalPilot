from __future__ import annotations

from io import BytesIO
from typing import Any


def build_pdf_bytes(proposal: dict[str, Any]) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    x = 0.85 * inch
    y = height - 0.9 * inch

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(x, y, "Proposal")
    y -= 0.45 * inch

    pdf.setFont("Helvetica", 10)
    sections = [
        ("Executive Summary", proposal.get("executive_summary")),
        ("Problem Statement", proposal.get("client_problem_statement")),
        ("Solution", proposal.get("proposed_solution")),
        ("Architecture", proposal.get("technical_architecture")),
        ("Technology Stack", proposal.get("technology_stack")),
        ("Delivery Approach", proposal.get("delivery_approach")),
        ("Cost Estimate", proposal.get("cost_estimation")),
        ("Risks", "\n".join(proposal.get("risks") or [])),
        ("Assumptions", "\n".join(proposal.get("assumptions") or [])),
    ]

    def write_wrapped(text: str, cursor_y: float) -> float:
        for paragraph in text.splitlines() or [""]:
            words = paragraph.split()
            line = ""
            for word in words or [""]:
                candidate = f"{line} {word}".strip()
                if pdf.stringWidth(candidate, "Helvetica", 10) > width - (1.7 * inch):
                    pdf.drawString(x, cursor_y, line)
                    cursor_y -= 12
                    line = word
                else:
                    line = candidate
            if line:
                pdf.drawString(x, cursor_y, line)
                cursor_y -= 12
            cursor_y -= 2
        return cursor_y

    for title, value in sections:
        if y < 1.25 * inch:
            pdf.showPage()
            y = height - 0.9 * inch
            pdf.setFont("Helvetica", 10)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(x, y, title)
        y -= 0.22 * inch
        pdf.setFont("Helvetica", 10)
        y = write_wrapped(str(value or ""), y)
        y -= 0.2 * inch

    pdf.save()
    return buffer.getvalue()
