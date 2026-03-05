# PDF → 요구사항 도출 → PPT 생성 MVP

PDF를 업로드하면 텍스트를 추출하고, 요구사항(JSON)을 생성한 뒤, PPTX까지 자동 생성하는 FastAPI 기반 MVP입니다.

## 1) 실행 가능한 MVP 폴더 구조

```text
pdftoppt/
├── app/
│   ├── main.py                    # FastAPI 엔트리포인트
│   ├── schemas.py                 # 요청/응답 및 도메인 스키마
│   ├── prompts/
│   │   ├── system_prompt.txt      # LLM 시스템 프롬프트
│   │   └── user_prompt_template.txt # LLM 유저 프롬프트 템플릿
│   └── services/
│       ├── pdf_parser.py          # PDF 텍스트 추출(PyMuPDF)
│       ├── llm_service.py         # OpenAI 호출 + fallback 생성
│       └── ppt_builder.py         # python-pptx 파일 생성
├── tests/
│   └── test_health.py             # 기본 헬스체크 테스트
├── uploads/                       # 업로드 PDF 저장 디렉터리(런타임 생성)
├── outputs/                       # 생성 PPT 저장 디렉터리(런타임 생성)
├── requirements.txt
└── README.md
```

## 2) 빠른 시작

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 2-1) Docker Compose로 한 번에 실행

```bash
docker compose up --build
```

실행 후 접속:
- 웹 업로드 화면: `http://127.0.0.1:8000`
- API 서버: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

백그라운드 실행:

```bash
docker compose up -d --build
```

중지:

```bash
docker compose down
```

OpenAI 연동(선택):

```bash
export OPENAI_API_KEY="YOUR_KEY"
```

키가 없으면 fallback 로직으로 기본 구조의 결과(JSON/PPT)를 생성합니다.

## 3) API 명세

### GET `/health`
서비스 상태 확인

**Response 200**
```json
{"status":"ok"}
```

---

### POST `/v1/process`
PDF 업로드 + 요구사항/PPT 생성 파이프라인 실행

**Content-Type**: `multipart/form-data`

**Form Fields**
- `pdf_file` (file, required): PDF 파일
- `purpose` (string, optional, default: `내부 공유`): 발표 목적
- `audience` (string, optional, default: `팀 리더`): 청중
- `tone` (string, optional, default: `공식적`): 톤앤매너
- `slide_count` (int, optional, default: `10`): 슬라이드 수

**Response 200 (요약)**
```json
{
  "result": {
    "document_summary": {
      "title": "...",
      "type": "...",
      "purpose": "...",
      "audience": "...",
      "key_takeaways": ["..."]
    },
    "requirements": {
      "functional": [{"id":"F-1","text":"...","priority":"High","evidence":"..."}],
      "non_functional": [],
      "constraints": [],
      "timeline": [],
      "risks": []
    },
    "ppt_outline": [
      {
        "slide_no": 1,
        "title": "...",
        "objective": "...",
        "key_points": ["..."],
        "visual_type": "bullet",
        "speaker_note": "..."
      }
    ],
    "open_questions": ["..."]
  },
  "output_ppt_path": "outputs/<uuid>.pptx",
  "llm_meta": {
    "mode": "openai",
    "used_fallback": false,
    "error_message": null
  }
}
```

---

응답의 `llm_meta` 필드로 OpenAI 사용 여부와 fallback 사유를 확인할 수 있습니다.

### GET `/v1/download/{file_name}`
생성된 PPT 다운로드

**Path Params**
- `file_name`: `outputs` 폴더 내 파일명 (`<uuid>.pptx`)
  - 예: `output_ppt_path`가 `outputs/abc.pptx`면 다운로드 URL은 `/v1/download/abc.pptx`

**Response 200**
- `application/vnd.openxmlformats-officedocument.presentationml.presentation`

## 4) 웹에서 파일 업로드하기

브라우저에서 `http://127.0.0.1:8000` 접속 후 파일 선택(input)으로 `의사결정.pdf`를 업로드하고, 생성 완료 후 다운로드 링크를 클릭하면 됩니다.

- 업로드 폼은 기본 페이지 이동을 막도록 구성되어, 버튼 클릭 시 `/?pdf_file=...`로 새로고침되지 않아야 정상입니다.
- 브라우저 캐시로 구버전 화면이 남는 문제를 줄이기 위해, `/` 응답은 no-cache 헤더로 제공됩니다.

> 만약 주소창에 `/?pdf_file=...` 같은 GET 쿼리가 보이면 브라우저 캐시를 비우고 새로고침 후 다시 시도하세요(최신 스크립트에서 업로드 후 링크가 바로 생성됩니다).

## 5) cURL 예시


> 윈도우 환경에서도 응답의 `output_ppt_path`는 `/` 형식으로 반환됩니다.

```bash
curl -X POST "http://127.0.0.1:8000/v1/process" \
  -F "pdf_file=@./의사결정.pdf" \
  -F "purpose=경영진 의사결정" \
  -F "audience=CEO/임원" \
  -F "tone=데이터 중심" \
  -F "slide_count=12"
```

> `의사결정.pdf`는 서버 폴더에 미리 넣지 않아도 됩니다. 위 커맨드를 실행하는 위치 기준 상대경로(또는 절대경로)로 전달하면 업로드됩니다.

## 6) 다음 확장 포인트

- OCR 파이프라인 추가 (스캔 PDF 대응)
- 벡터DB 기반 문서 chunk 검색 + 근거 추적 강화
- 템플릿 기반 디자인(theme, brand kit) 적용
- 비동기 작업 큐(Celery/RQ)로 대용량 문서 처리
