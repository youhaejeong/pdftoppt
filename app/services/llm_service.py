import json
import logging
import os
from typing import List, Optional, Tuple

from openai import OpenAI

from app.schemas import (
    DocumentSummary,
    LLMRunMeta,
    PipelineResult,
    RequirementItem,
    Requirements,
    SlideOutline,
)

SYSTEM_PROMPT_PATH = "app/prompts/system_prompt.txt"
logger = logging.getLogger(__name__)


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
    ) -> Tuple[PipelineResult, LLMRunMeta]:
        if self.client:
            try:
                result = self._call_openai(text, purpose, audience, tone, slide_count)
                return result, LLMRunMeta(mode="openai", used_fallback=False)
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"
                logger.exception("OpenAI call failed. Falling back to deterministic mode")
                return (
                    self._fallback(text, purpose, audience, slide_count),
                    LLMRunMeta(
                        mode="fallback",
                        used_fallback=True,
                        error_message=error_message[:400],
                    ),
                )

        logger.warning("OPENAI_API_KEY is not set. Using fallback mode")
        return (
            self._fallback(text, purpose, audience, slide_count),
            LLMRunMeta(
                mode="fallback",
                used_fallback=True,
                error_message="OPENAI_API_KEY is not set",
            ),
        )

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
        source_lines = self._extract_source_lines(text)
        key_takeaways = source_lines[: min(5, len(source_lines))] or ["문서 핵심 내용 파악 필요"]

        functional = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["요구", "기능", "서비스", "구축", "지원"]),
            prefix="F",
            fallback=["문서 기반 기능 요구사항 상세 정의 필요"],
            priority="High",
        )
        non_functional = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["성능", "보안", "안정", "품질", "응답시간"]),
            prefix="NF",
            fallback=["비기능 요구사항(성능/보안/운영) 정의 필요"],
            priority="Med",
        )
        constraints = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["제약", "예산", "범위", "필수", "준수"]),
            prefix="C",
            fallback=["예산/범위/정책 제약사항 확인 필요"],
            priority="Med",
        )
        timeline = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["일정", "기간", "단계", "마감", "월", "주"]),
            prefix="T",
            fallback=["주요 마일스톤 일정 정의 필요"],
            priority="Med",
        )
        risks = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["리스크", "위험", "문제", "이슈", "지연"]),
            prefix="R",
            fallback=["핵심 리스크 식별 및 대응 계획 수립 필요"],
            priority="Med",
        )

        outlines = self._build_outline_from_source(source_lines, slide_count)

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
                constraints=constraints,
                timeline=timeline,
                risks=risks,
            ),
            ppt_outline=outlines,
            open_questions=[
                "최종 발표 대상의 의사결정 포인트는 무엇인가?",
                "필수 포함해야 할 KPI/정량 지표가 있는가?",
                "우선순위가 가장 높은 요구사항 3개는 무엇인가?",
            ],
        )

    def _extract_source_lines(self, text: str) -> List[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        compact = []
        for line in lines:
            normalized = " ".join(line.split())
            if len(normalized) >= 8:
                compact.append(normalized)
        return compact[:200]

    def _pick_lines(self, lines: List[str], keywords: List[str], limit: int = 3) -> List[str]:
        picked = [line for line in lines if any(k in line for k in keywords)]
        return picked[:limit]

    def _build_requirement_items(
        self,
        lines: List[str],
        prefix: str,
        fallback: List[str],
        priority: str,
    ) -> List[RequirementItem]:
        base = lines if lines else fallback
        items: List[RequirementItem] = []
        for idx, line in enumerate(base, start=1):
            items.append(
                RequirementItem(
                    id=f"{prefix}-{idx}",
                    text=line,
                    priority=priority,
                    evidence=line,
                )
            )
        return items

    def _build_outline_from_source(self, lines: List[str], slide_count: int) -> List[SlideOutline]:
        if not lines:
            lines = ["문서에서 유의미한 본문을 찾지 못했습니다."]

        proposal_sections = [
            ("제안 개요", "고객 배경과 제안 목적 정리", "비교"),
            ("클라이언트 요구사항 요약", "핵심 요구사항을 우선순위로 정리", "표"),
            ("요구사항 상세 분석", "기능/비기능/제약 사항을 구조화", "표"),
            ("우리 회사 수행 역량", "SI 관점에서 수행 가능한 범위 제시", "아이콘"),
            ("구현/운영 접근 방안", "기술 아키텍처와 실행 방법 제시", "프로세스"),
            ("단계별 수행 계획", "일정 및 마일스톤 제시", "타임라인"),
            ("투입 인력 및 역할", "역할과 책임(R&R) 정리", "표"),
            ("리스크 및 대응 전략", "리스크 식별과 대응 방안 제시", "비교"),
            ("기대효과 및 KPI", "정량/정성 효과와 KPI 제시", "표"),
            ("결론 및 요청사항", "의사결정 포인트와 다음 액션 정리", "bullet"),
        ]

        capabilities = [
            "요구사항 정의~개발~운영까지 End-to-End 수행",
            "웹/모바일/백엔드/데이터 연계 통합 구축",
            "레거시 연동 및 단계적 전환(무중단/저위험) 지원",
            "운영 안정화·고도화 및 SLA 기반 기술지원",
        ]

        outlines: List[SlideOutline] = []
        for i in range(1, slide_count + 1):
            section_title, objective, visual = proposal_sections[(i - 1) % len(proposal_sections)]
            start_idx = (i - 1) * 3
            points: List[str] = []

            if section_title == "우리 회사 수행 역량":
                points = capabilities[:3]
            elif section_title == "단계별 수행 계획":
                points = [
                    "1단계: 요구사항 상세화 및 범위 확정",
                    "2단계: 설계/개발/연동 및 품질 검증",
                    "3단계: 안정화/교육/운영 이관",
                ]
            elif section_title == "결론 및 요청사항":
                points = [
                    "우선순위 요구사항부터 단계적 착수 제안",
                    "착수 전 워크숍으로 범위·일정·KPI 확정",
                    "의사결정 후 즉시 실행 가능한 준비 완료",
                ]
            else:
                for j in range(3):
                    idx = (start_idx + j) % len(lines)
                    points.append(lines[idx][:80])

            note_evidence = lines[(i - 1) % len(lines)][:120]
            outlines.append(
                SlideOutline(
                    slide_no=i,
                    title=section_title,
                    objective=objective,
                    key_points=points,
                    visual_type=visual,
                    speaker_note=f"문서 근거 기반 제안. 참고 문장: {note_evidence}",
                )
            )

        return outlines
