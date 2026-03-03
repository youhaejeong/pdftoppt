from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas import ProcessResponse
from app.services.llm_service import LLMService
from app.services.pdf_parser import PDFParser
from app.services.ppt_builder import PPTBuilder

app = FastAPI(title="PDF to PPT MVP", version="0.1.0")

llm_service = LLMService()
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/process", response_model=ProcessResponse)
async def process_pdf(
    pdf_file: UploadFile = File(...),
    purpose: str = Form("내부 공유"),
    audience: str = Form("팀 리더"),
    tone: str = Form("공식적"),
    slide_count: int = Form(10),
) -> ProcessResponse:
    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid4().hex
    pdf_path = UPLOAD_DIR / f"{file_id}.pdf"

    with open(pdf_path, "wb") as f:
        f.write(await pdf_file.read())

    text = PDFParser.extract_text(pdf_path)
    if not text:
        raise HTTPException(status_code=400, detail="PDF에서 텍스트를 추출하지 못했습니다.")

    result = llm_service.build_result(
        text=text,
        purpose=purpose,
        audience=audience,
        tone=tone,
        slide_count=slide_count,
    )

    output_ppt = OUTPUT_DIR / f"{file_id}.pptx"
    PPTBuilder.build(result, output_ppt)

    return ProcessResponse(result=result, output_ppt_path=str(output_ppt))


@app.get("/v1/download/{file_name}")
def download(file_name: str):
    target = OUTPUT_DIR / file_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(target, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
