from pathlib import Path

from pptx import Presentation

from app.schemas import PipelineResult


class PPTBuilder:
    @staticmethod
    def build(result: PipelineResult, output_path: Path) -> Path:
        prs = Presentation()

        for slide_item in result.ppt_outline:
            slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(slide_layout)
            slide.shapes.title.text = slide_item.title

            body = slide.placeholders[1].text_frame
            body.clear()
            for idx, point in enumerate(slide_item.key_points):
                if idx == 0:
                    body.text = point
                else:
                    p = body.add_paragraph()
                    p.text = point

            notes = slide.notes_slide.notes_text_frame
            notes.text = slide_item.speaker_note

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(output_path)
        return output_path
