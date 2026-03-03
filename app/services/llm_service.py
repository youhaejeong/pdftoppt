import json
import os
from typing import Optional

from openai import OpenAI

from app.schemas import (
    DocumentSummary,
    PipelineResult,
    RequirementItem,
    Requirements,
    SlideOutline,
)

SYSTEM_PROMPT_PATH = "app/prompts/system_prompt.txt"


class LLMService:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.client: Optional[OpenAI] = OpenAI(api_key=api_key) if api_key else None

    def build_result(
        self,
        text: str,
        purpose: str,
        audience: str,
        tone: str,
        slide_count: int,
    ) -> PipelineResult:
        if self.client:
            try:
                return self._call_openai(text, purpose, audience, tone, slide_count)
            except Exception:
                return self._fallback(text, purpose, audience, slide_count)
        return self._fallback(text, purpose, audience, slide_count)

    def _call_openai(
        self,
        text: str,
        purpose: str,
        audience: str,
        tone: str,
        slide_count: int,
    ) -> PipelineResult:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = f.read()

        user_prompt = (
            f"[발표 목적]\n{purpose}\n\n"
            f"[청중]\n{audience}\n\n"
            f"[톤앤매너]\n{tone}\n\n"
            f"[분량]\n{slide_count}\n\n"
            f"[PDF 추출 텍스트]\n{text[:120000]}"
        )

        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        return PipelineResult.model_validate(data)

    def _fallback(
        self,
        text: str,
        purpose: str,
        audience: str,
        slide_count: int,
    ) -> PipelineResult:
        trimmed = [line.strip() for line in text.splitlines() if line.strip()]
        key_takeaways = trimmed[: min(5, len(trimmed))] or ["문서 핵심 내용 파악 필요"]

        functional = [
            RequirementItem(
                id="F-1",
                text="PDF 업로드 및 텍스트 추출",
                priority="High",
                evidence="업로드 기반 분석 요구",
            ),
            RequirementItem(
                id="F-2",
                text="요구사항 자동 분류 및 PPT 아웃라인 생성",
                priority="High",
                evidence="요구사항 도출 및 PPT 제작 요청",
            ),
        ]

        non_functional = [
            RequirementItem(
                id="NF-1",
                text="응답 JSON 스키마 일관성 보장",
                priority="Med",
                evidence="자동화 파이프라인 연계 필요",
            )
        ]

        outlines = []
        for i in range(1, slide_count + 1):
            outlines.append(
                SlideOutline(
                    slide_no=i,
                    title=f"슬라이드 {i}",
                    objective="핵심 내용 전달",
                    key_points=[
                        "핵심 요구사항 요약",
                        "근거 기반 메시지",
                        "실행 항목 제안",
                    ],
                    visual_type="bullet",
                    speaker_note="필요 시 문서 원문 근거를 함께 설명",
                )
            )

        return PipelineResult(
            document_summary=DocumentSummary(
                title="PDF 기반 요구사항 분석",
                type="report",
                purpose=purpose,
                audience=audience,
                key_takeaways=key_takeaways,
            ),
            requirements=Requirements(
                functional=functional,
                non_functional=non_functional,
                constraints=[],
                timeline=[],
                risks=[
                    RequirementItem(
                        id="R-1",
                        text="원문 데이터 품질이 낮으면 분석 정확도 저하",
                        priority="Med",
                        evidence="스캔 PDF/OCR 품질 의존",
                    )
                ],
            ),
            ppt_outline=outlines,
            open_questions=[
                "최종 발표 대상의 의사결정 포인트는 무엇인가?",
                "필수 포함해야 할 KPI/정량 지표가 있는가?",
                "디자인 템플릿/브랜드 가이드가 있는가?",
            ],
        )
