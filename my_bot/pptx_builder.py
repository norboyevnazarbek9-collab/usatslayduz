import io
from pptx import Presentation
from pptx.util import Inches, Pt
from prompts import clean_text

FONT_NAME = "Arial"


def create_presentation_bytes(slides_data: list[dict], topic: str, subject: str, author: str = "Slayd Bot") -> io.BytesIO:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    clean_topic = clean_text(topic)
    clean_subject = clean_text(subject)
    clean_author = clean_text(author)

    # 1. Titul slayd
    title_layout = prs.slide_layouts[0]
    slide0 = prs.slides.add_slide(title_layout)
    if slide0.shapes.title:
        slide0.shapes.title.text = clean_topic or "Taqdimot"
        for p in slide0.shapes.title.text_frame.paragraphs:
            for r in p.runs:
                r.font.name = FONT_NAME
                r.font.size = Pt(36)

    if len(slide0.placeholders) > 1:
        subtitle = slide0.placeholders[1]
        subtitle.text = f"Fan: {clean_subject}\nTayyorladi: {clean_author}"
        for p in subtitle.text_frame.paragraphs:
            for r in p.runs:
                r.font.name = FONT_NAME
                r.font.size = Pt(20)

    # 2. Asosiy slaydlar
    bullet_layout = prs.slide_layouts[1]
    for item in slides_data:
        slide = prs.slides.add_slide(bullet_layout)
        slide_title = clean_text(item.get("title", "Bo'lim"))
        bullets = [clean_text(b) for b in item.get("bullets", []) if clean_text(b)][:4]
        notes_text = clean_text(item.get("speaker_notes", ""))

        if slide.shapes.title:
            slide.shapes.title.text = slide_title
            for p in slide.shapes.title.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name = FONT_NAME
                    r.font.size = Pt(28)

        if len(slide.placeholders) > 1:
            body = slide.placeholders[1]
            tf = body.text_frame
            tf.clear()
            for idx, b_text in enumerate(bullets):
                p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                p.text = b_text
                p.level = 0
                for r in p.runs:
                    r.font.name = FONT_NAME
                    r.font.size = Pt(20)

        if notes_text:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = notes_text

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer
