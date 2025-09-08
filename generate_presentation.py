#!/usr/bin/env python3
"""
Generate a one-page PDF presentation for the MetaHuman Streamer GUI prototype
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os
from datetime import datetime

def create_presentation():
    """Create a one-page PDF presentation"""
    
    # Create PDF document
    filename = "MetaHuman_Streamer_Prototype_Presentation.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter, 
                          rightMargin=0.5*inch, leftMargin=0.5*inch,
                          topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=HexColor('#2E86AB')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=15,
        alignment=TA_CENTER,
        textColor=HexColor('#A23B72')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        textColor=HexColor('#2E86AB')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        leading=14
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4,
        leftIndent=20,
        leading=12
    )
    
    # Content
    story = []
    
    # Title
    story.append(Paragraph("MetaHuman Steering Streamer GUI", title_style))
    story.append(Paragraph("Working Prototype - Real-time OSC Control System", subtitle_style))
    story.append(Spacer(1, 10))
    
    # Executive Summary
    story.append(Paragraph("EXECUTIVE SUMMARY", heading_style))
    story.append(Paragraph(
        "Successfully developed a working desktop GUI prototype that enables real-time control of MetaHuman characters in Unreal Engine through OSC (Open Sound Control) messaging. The system provides intuitive steering controls with smooth animations and real-time connection monitoring.",
        body_style
    ))
    story.append(Spacer(1, 10))
    
    # Key Features Table
    story.append(Paragraph("KEY FEATURES & CAPABILITIES", heading_style))
    
    features_data = [
        ['Feature', 'Description', 'Status'],
        ['Real-time OSC Streaming', '60 FPS continuous data streaming to Unreal', '✅ Working'],
        ['Multi-channel Control', '16 synchronized steering channels', '✅ Working'],
        ['Smooth Animations', 'Cubic ease-in-out ramping system', '✅ Working'],
        ['Connection Monitoring', 'Live status indicator & error tracking', '✅ Working'],
        ['Configurable Parameters', 'IP, Port, FPS, Duration, Hold settings', '✅ Working'],
        ['Keyboard Shortcuts', 'Hotkeys for rapid control (Ctrl+S, R, L, B, X)', '✅ Working'],
        ['Settings Persistence', 'Auto-saves configuration to user profile', '✅ Working'],
        ['Error Handling', 'Graceful error recovery & logging', '✅ Working']
    ]
    
    features_table = Table(features_data, colWidths=[1.8*inch, 2.2*inch, 0.8*inch])
    features_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('GRID', (0, 0), (-1, -1), 1, black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F8F9FA')])
    ]))
    
    story.append(features_table)
    story.append(Spacer(1, 10))
    
    # Technical Implementation
    story.append(Paragraph("TECHNICAL IMPLEMENTATION", heading_style))
    
    tech_data = [
        ['Component', 'Technology', 'Purpose'],
        ['GUI Framework', 'Tkinter (Python)', 'Cross-platform desktop interface'],
        ['OSC Communication', 'python-osc library', 'Real-time data streaming'],
        ['Animation Engine', 'NumPy + custom easing', 'Smooth motion curves'],
        ['Threading', 'Python threading', 'Non-blocking GUI + background processing'],
        ['Configuration', 'JSON format', 'Flexible channel mapping'],
        ['Error Handling', 'Exception management', 'Robust error recovery']
    ]
    
    tech_table = Table(tech_data, colWidths=[1.5*inch, 1.5*inch, 2.0*inch])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#A23B72')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('GRID', (0, 0), (-1, -1), 1, black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#F8F9FA')])
    ]))
    
    story.append(tech_table)
    story.append(Spacer(1, 10))
    
    # Business Value
    story.append(Paragraph("BUSINESS VALUE & IMPACT", heading_style))
    
    value_points = [
        "• <b>Rapid Prototyping:</b> Enables quick testing of MetaHuman steering concepts",
        "• <b>Real-time Control:</b> Provides immediate feedback for animation development",
        "• <b>Scalable Architecture:</b> Easy to extend with additional channels or features",
        "• <b>User-Friendly Interface:</b> Intuitive controls accessible to non-technical users",
        "• <b>Production Ready:</b> Robust error handling and connection monitoring",
        "• <b>Cost Effective:</b> Single-file solution with minimal dependencies"
    ]
    
    for point in value_points:
        story.append(Paragraph(point, bullet_style))
    
    story.append(Spacer(1, 10))
    
    # Next Steps
    story.append(Paragraph("NEXT STEPS & RECOMMENDATIONS", heading_style))
    story.append(Paragraph(
        "The prototype is ready for integration testing with Unreal Engine MetaHuman projects. Recommended next phase includes user acceptance testing, performance optimization, and potential integration with existing motion capture workflows.",
        body_style
    ))
    
    # Footer
    story.append(Spacer(1, 20))
    footer_text = f"Generated: {datetime.now().strftime('%B %d, %Y')} | Status: Working Prototype | Ready for Testing"
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], 
                                                      fontSize=9, alignment=TA_CENTER, 
                                                      textColor=HexColor('#666666'))))
    
    # Build PDF
    doc.build(story)
    return filename

if __name__ == "__main__":
    try:
        filename = create_presentation()
        print(f"✅ Presentation PDF generated successfully: {filename}")
        print(f"📁 Location: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        print("Make sure you have reportlab installed: pip install reportlab")
