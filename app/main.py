from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.schemas import ProcessResponse
from app.services.llm_service import LLMService
from app.services.pdf_parser import PDFParser
from app.services.ppt_builder import PPTBuilder

app = FastAPI(title="PDF to PPT MVP", version="0.2.0")

llm_service = LLMService()
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    html = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PDF → PPT 생성기</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 16px; }
    h1 { margin-bottom: 8px; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 20px; }
    label { display: block; margin: 12px 0 6px; font-weight: 600; }
    input, button { width: 100%; padding: 10px; box-sizing: border-box; }
    button { margin-top: 16px; cursor: pointer; }
    .muted { color: #666; font-size: 14px; }
    #result { margin-top: 16px; white-space: pre-wrap; background: #f8f8f8; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>PDF → 요구사항 → PPT</h1>
  <p class="muted">curl 없이 파일 선택으로 업로드해 PPT를 생성할 수 있습니다.</p>

  <div class="card">
    <form id="upload-form" method="post" enctype="multipart/form-data" onsubmit="event.preventDefault();">
      <label for="pdf_file">PDF 파일</label>
      <input id="pdf_file" name="pdf_file" type="file" accept="application/pdf" required />

      <label for="purpose">발표 목적</label>
      <input id="purpose" name="purpose" type="text" value="내부 공유" />

      <label for="audience">청중</label>
      <input id="audience" name="audience" type="text" value="팀 리더" />

      <label for="tone">톤앤매너</label>
      <input id="tone" name="tone" type="text" value="공식적" />

      <label for="slide_count">슬라이드 수</label>
      <input id="slide_count" name="slide_count" type="number" value="10" min="1" max="30" />

      <button id="generate-btn" type="button">PPT 생성하기</button>
    </form>

    <div id="result"></div>
  </div>

  <script>
    const form = document.getElementById('upload-form');
    const result = document.getElementById('result');
    const generateBtn = document.getElementById('generate-btn');

    const submitForm = async () => {
      result.textContent = '처리 중...';

      const formData = new FormData(form);

      try {
        const response = await fetch('/v1/process', {
          method: 'POST',
          body: formData,
        });

        const data = await response.json();
        if (!response.ok) {

          result.textContent =  "오류: " + (data.detail || "요청 실패");

          return;
        }

        const rawPath = data.output_ppt_path || '';

        const normalized = rawPath.replace(/\/g, '/');

        const fileName = normalized.split('/').pop();
        const downloadUrl = `/v1/download/${encodeURIComponent(fileName)}`;

        const modeText = data.llm_meta?.mode || 'unknown';
        const errText = data.llm_meta?.error_message ? `<br/>LLM fallback 사유: ${data.llm_meta.error_message}` : '';


        result.innerHTML =
          "<strong>완료!</strong><br/>" +
          "생성 파일: " + data.output_ppt_path + "<br/>" +
          '<a href="' + downloadUrl + '">PPT 다운로드</a>';
      } catch (err) {
        result.textContent = "오류: " + err.message;
      }
    };

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      await submitForm();
    });

    generateBtn.addEventListener('click', async () => {
      await submitForm();
    });
  </script>
</body>
</html>
    """
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools_probe() -> Response:
    return Response(status_code=204)


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

    result, llm_meta = llm_service.build_result(

        text=text,
        purpose=purpose,
        audience=audience,
        tone=tone,
        slide_count=slide_count,
    )

    output_ppt = OUTPUT_DIR / f"{file_id}.pptx"
    PPTBuilder.build(result, output_ppt)

    return ProcessResponse(result=result, output_ppt_path=output_ppt.as_posix(), llm_meta=llm_meta)


@app.get("/v1/download/{file_name:path}")
def download(file_name: str):
    safe_name = Path(file_name).name
    target = OUTPUT_DIR / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(target, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
