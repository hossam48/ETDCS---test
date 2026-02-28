# =============================================================================
# pdf_generator.py - PDF Report Generation with Arabic Support
# Task 11 - Phase 3 Architecture
# =============================================================================
# Generates PDF reports for ETDCS projects with proper Arabic text rendering.
#
# Dependencies:
#   - reportlab: PDF generation
#   - arabic-reshaper: Fix Arabic letter shapes (connect letters)
#   - python-bidi: Handle RTL text direction
#
# Usage:
#   from pdf_generator import generate_project_report
#
#   path = generate_project_report(
#       project_name="محطة قوى مرجان",
#       stats=stats_dict,
#       deliverables_df=df,
#   )
# =============================================================================

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Dict, Any

import pandas as pd

# =============================================================================
# OPTIONAL DEPENDENCIES - Arabic Support
# =============================================================================

# Try to import Arabic support libraries
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _ARABIC_SUPPORT = True
except ImportError:
    _ARABIC_SUPPORT = False
    # Will use fallback (text as-is)

# ReportLab imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================

REPORTS_DIR = "files/reports"

# Try to register Arabic fonts
_ARABIC_FONT_NAME = "Helvetica"  # Default fallback
_FONT_WARNING_PRINTED = False


def _register_arabic_font() -> str:
    """
    Try to register an Arabic-supporting font.
    
    Returns:
        Font name to use (Arabic font if available, else Helvetica)
    """
    global _ARABIC_FONT_NAME, _FONT_WARNING_PRINTED
    
    if not _REPORTLAB_AVAILABLE:
        return "Helvetica"
    
    # Common Arabic font paths to try
    font_paths = [
        # Linux system fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        # macOS fonts
        "/System/Library/Fonts/GeezaPro.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Windows fonts
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
        # Project-local fonts
        os.path.join(os.path.dirname(__file__), "fonts", "Amiri-Regular.ttf"),
        os.path.join(os.path.dirname(__file__), "fonts", "Cairo-Regular.ttf"),
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                font_name = os.path.basename(path).split('.')[0]
                pdfmetrics.registerFont(TTFont(font_name, path))
                _ARABIC_FONT_NAME = font_name
                return font_name
            except Exception:
                continue
    
    # No Arabic font found - print warning once
    if not _FONT_WARNING_PRINTED:
        print("⚠️ Warning: No Arabic font found. PDF reports will use Helvetica.")
        print("   For proper Arabic support, install: apt-get install fonts-noto")
        _FONT_WARNING_PRINTED = True
    
    return "Helvetica"


# =============================================================================
# ARABIC TEXT FIXER
# =============================================================================

def fix_arabic(text: str) -> str:
    """
    Fix Arabic text for correct PDF rendering (RTL + proper letter shapes).
    
    This function:
    1. Reshapes Arabic letters to connect them properly
    2. Reverses the text for RTL display
    
    Args:
        text: Input text (may contain Arabic)
    
    Returns:
        Fixed text ready for PDF rendering
    """
    if not text:
        return text
    
    # If no Arabic support, return as-is (may not render correctly)
    if not _ARABIC_SUPPORT:
        return text
    
    # Check if text contains Arabic characters
    has_arabic = any('\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F' for c in text)
    
    if not has_arabic:
        return text  # No Arabic, return as-is
    
    try:
        # Step 1: Reshape Arabic letters (connect them)
        reshaped = arabic_reshaper.reshape(text)
        
        # Step 2: Apply BiDi algorithm for RTL display
        fixed = get_display(reshaped)
        
        return fixed
    except Exception:
        return text  # Fallback: return original


# =============================================================================
# PDF GENERATION
# =============================================================================

def generate_project_report(
    project_name: str,
    stats: Dict[str, Any],
    deliverables_df: pd.DataFrame,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate a PDF report for a project with Arabic text support.
    
    Args:
        project_name:   Project name (may be in Arabic)
        stats:          Statistics dict with keys:
                        - total_deliverables, total_tasks, overdue_tasks, avg_progress
        deliverables_df: DataFrame with deliverables data
        output_path:    Optional output path. If None, saves to files/reports/
    
    Returns:
        Path to the generated PDF file
    
    Raises:
        ImportError: If reportlab is not installed
        RuntimeError: If PDF generation fails
    """
    if not _REPORTLAB_AVAILABLE:
        raise ImportError(
            "reportlab is required for PDF generation.\n"
            "Install with: pip install reportlab"
        )
    
    # Ensure reports directory exists
    os.makedirs(REPORTS_DIR, exist_ok=True)
    
    # Generate output path if not provided
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = project_name.replace(" ", "_").replace("/", "-")[:50]
        output_path = os.path.join(REPORTS_DIR, f"report_{safe_name}_{timestamp}.pdf")
    
    # Register Arabic font
    font_name = _register_arabic_font()
    
    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    
    # Build styles
    styles = getSampleStyleSheet()
    
    # Title style (large, centered)
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=20,
        alignment=1,  # Center
        spaceAfter=12,
    )
    
    # Heading style
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=14,
        spaceAfter=8,
        spaceBefore=16,
    )
    
    # Normal text style
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
    )
    
    # Build document content
    elements = []
    
    # ── HEADER ─────────────────────────────────────────────────────────────
    # Project name (Arabic supported)
    project_name_fixed = fix_arabic(project_name)
    elements.append(Paragraph(project_name_fixed, title_style))
    
    # Report date
    report_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    elements.append(Paragraph(f"Report Date: {report_date}", normal_style))
    elements.append(Spacer(1, 20))
    
    # ── KPI SECTION ────────────────────────────────────────────────────────
    elements.append(Paragraph("Project Statistics", heading_style))
    
    # KPI table data
    kpi_data = [
        ["Metric", "Value"],
        ["Total Deliverables", str(stats.get("total_deliverables", 0))],
        ["Total Tasks", str(stats.get("total_tasks", 0))],
        ["Overdue Tasks", str(stats.get("overdue_tasks", 0))],
        ["Average Progress", f"{stats.get('avg_progress', 0)}%"],
    ]
    
    kpi_table = Table(kpi_data, colWidths=[3 * inch, 2 * inch])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTNAME', (0, 1), (-1, -1), font_name),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    
    elements.append(kpi_table)
    elements.append(Spacer(1, 20))
    
    # ── DELIVERABLES TABLE ─────────────────────────────────────────────────
    elements.append(Paragraph("Deliverables", heading_style))
    
    if deliverables_df.empty:
        elements.append(Paragraph("No deliverables found.", normal_style))
    else:
        # Prepare table data with fixed Arabic text
        table_data = [["Name", "Station", "Discipline", "Status"]]
        
        for _, row in deliverables_df.iterrows():
            name = fix_arabic(str(row.get("name", "")))
            station = fix_arabic(str(row.get("station", "")))
            discipline = fix_arabic(str(row.get("discipline", "")))
            status = fix_arabic(str(row.get("status", "")))
            
            table_data.append([name, station, discipline, status])
        
        # Limit to first 50 rows to avoid huge PDFs
        if len(table_data) > 51:
            table_data = table_data[:51]
            table_data.append(["...", "...", "...", "..."])
        
        # Create table
        deliv_table = Table(table_data, colWidths=[2.5 * inch, 1 * inch, 1 * inch, 1.2 * inch])
        deliv_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(deliv_table)
    
    # ── FOOTER ─────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 30))
    footer_text = f"Generated by ETDCS - Elsewedy Technical Document Control System"
    elements.append(Paragraph(footer_text, normal_style))
    
    # Build PDF
    try:
        doc.build(elements)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Failed to generate PDF: {e}")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_arabic_support() -> Dict[str, bool]:
    """
    Check if Arabic PDF support is available.
    
    Returns:
        Dict with status of each component:
        - reportlab: bool
        - arabic_reshaper: bool
        - python_bidi: bool
        - arabic_font: bool
    """
    global _ARABIC_FONT_NAME
    
    return {
        "reportlab": _REPORTLAB_AVAILABLE,
        "arabic_reshaper": _ARABIC_SUPPORT,
        "python_bidi": _ARABIC_SUPPORT,
        "arabic_font": _ARABIC_FONT_NAME != "Helvetica",
    }


def get_font_name() -> str:
    """
    Get the currently registered font name.
    
    Returns:
        Font name being used for PDF generation
    """
    return _ARABIC_FONT_NAME


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Try to register font on import
if _REPORTLAB_AVAILABLE:
    _register_arabic_font()
