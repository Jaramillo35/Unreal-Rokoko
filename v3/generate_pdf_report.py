#!/usr/bin/env python3
"""
Generate PDF report from markdown summary
"""

import markdown
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import re

def markdown_to_pdf():
    # Read the markdown file
    with open('V3_Summary_Report.md', 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    # Create PDF
    doc = SimpleDocTemplate("V3_Summary_Report.pdf", pagesize=letter,
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=12,
        textColor=colors.darkblue
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=8,
        spaceBefore=8,
        textColor=colors.darkgreen
    )
    
    # Parse markdown content
    story = []
    
    lines = markdown_content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('# '):
            # Main title
            title = line[2:].strip()
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 12))
            
        elif line.startswith('**') and '**' in line:
            # Bold text (project info)
            text = line.replace('**', '')
            story.append(Paragraph(f"<b>{text}</b>", styles['Normal']))
            
        elif line.startswith('---'):
            # Horizontal rule
            story.append(Spacer(1, 12))
            
        elif line.startswith('## '):
            # Section heading
            heading = line[3:].strip()
            story.append(Paragraph(heading, heading_style))
            
        elif line.startswith('### '):
            # Subsection heading
            subheading = line[4:].strip()
            story.append(Paragraph(subheading, subheading_style))
            
        elif line.startswith('|'):
            # Table - collect all table rows
            table_data = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = lines[i].strip()
                if not row.startswith('|---'):  # Skip separator rows
                    cells = [cell.strip() for cell in row.split('|')[1:-1]]
                    table_data.append(cells)
                i += 1
            i -= 1  # Adjust for the loop increment
            
            if table_data:
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(table)
                story.append(Spacer(1, 12))
        
        elif line.startswith('- '):
            # Bullet point
            text = line[2:].strip()
            story.append(Paragraph(f"• {text}", styles['Normal']))
            
        elif line.startswith('```'):
            # Code block - collect until closing ```
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                code_text = '\n'.join(code_lines)
                story.append(Paragraph(f"<font name='Courier'>{code_text}</font>", styles['Normal']))
                story.append(Spacer(1, 6))
        
        elif line and not line.startswith('*'):
            # Regular paragraph
            if line:
                # Clean up markdown formatting
                text = line.replace('**', '<b>').replace('**', '</b>')
                text = text.replace('✅', '✓').replace('⭐', '★')
                text = text.replace('🎯', '→').replace('🚀', '→')
                text = text.replace('📊', '→').replace('🎮', '→')
                text = text.replace('🔧', '→').replace('📈', '→')
                text = text.replace('📁', '→').replace('🎯', '→')
                story.append(Paragraph(text, styles['Normal']))
        
        i += 1
    
    # Build PDF
    doc.build(story)
    print("✅ PDF report generated: V3_Summary_Report.pdf")

if __name__ == "__main__":
    markdown_to_pdf()
