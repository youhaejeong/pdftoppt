import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from app.schemas import (
    DocumentSummary,
    LLMRunMeta,
    PipelineResult,
    RequirementItem,
    Requirements,
    SlideOutline,
)

REQUIREMENTS_SYSTEM_PROMPT_PATH = "app/prompts/requirements_system_prompt.txt"
REQUIREMENTS_USER_PROMPT_TEMPLATE_PATH = "app/prompts/requirements_user_prompt_template.txt"
PROPOSAL_SYSTEM_PROMPT_PATH = "app/prompts/proposal_system_prompt.txt"
PROPOSAL_USER_PROMPT_TEMPLATE_PATH = "app/prompts/proposal_user_prompt_template.txt"
PPT_SYSTEM_PROMPT_PATH = "app/prompts/ppt_system_prompt.txt"
PPT_USER_PROMPT_TEMPLATE_PATH = "app/prompts/ppt_user_prompt_template.txt"
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
        extracted_requirements = self._call_requirements_analysis(
            text=text,
            purpose=purpose,
            audience=audience,
            tone=tone,
        )
        analyzed_requirements = self._call_proposal_analysis(
            requirements=extracted_requirements,
            purpose=purpose,
            audience=audience,
            tone=tone,
        )
        ppt_outline = self._call_ppt_outline(
            requirements=analyzed_requirements,
            purpose=purpose,
            audience=audience,
            tone=tone,
            slide_count=slide_count,
        )

        return PipelineResult(
            document_summary=DocumentSummary(
                title="PDF 기반 요구사항 분석",
                type="report",
                purpose=purpose,
                audience=audience,
                key_takeaways=self._summarize_requirements(analyzed_requirements),
            ),
            requirements=analyzed_requirements,
            ppt_outline=ppt_outline,
            open_questions=[
                "최종 발표 대상의 의사결정 포인트는 무엇인가?",
                "필수 포함해야 할 KPI/정량 지표가 있는가?",
                "우선순위가 가장 높은 요구사항 3개는 무엇인가?",
            ],
        )

    def _call_requirements_analysis(
        self,
        text: str,
        purpose: str,
        audience: str,
        tone: str,
    ) -> Requirements:
        with open(REQUIREMENTS_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        with open(REQUIREMENTS_USER_PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            user_prompt_template = f.read()

        user_prompt = user_prompt_template.format(
            purpose=purpose,
            audience=audience,
            tone=tone,
            text=text[:120000],
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
        return self._normalize_requirements(data)

    def _call_proposal_analysis(
        self,
        requirements: Requirements,
        purpose: str,
        audience: str,
        tone: str,
    ) -> Requirements:
        with open(PROPOSAL_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        with open(PROPOSAL_USER_PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            user_prompt_template = f.read()

        requirements_payload = self._requirements_to_prompt_payload(requirements)
        user_prompt = user_prompt_template.format(
            purpose=purpose,
            audience=audience,
            tone=tone,
            requirements_json=json.dumps(requirements_payload, ensure_ascii=False, indent=2),
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
        return self._normalize_requirements(data)

    def _call_ppt_outline(
        self,
        requirements: Requirements,
        purpose: str,
        audience: str,
        tone: str,
        slide_count: int,
    ) -> List[SlideOutline]:
        with open(PPT_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_prompt = f.read()
        with open(PPT_USER_PROMPT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            user_prompt_template = f.read()

        requirements_payload = self._requirements_to_prompt_payload(requirements)
        user_prompt = user_prompt_template.format(
            purpose=purpose,
            audience=audience,
            tone=tone,
            slide_count=slide_count,
            requirements_json=json.dumps(requirements_payload, ensure_ascii=False, indent=2),
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
        outlines = data.get("ppt_outline", [])
        return [SlideOutline.model_validate(item) for item in outlines]

    def _normalize_requirements(self, data: Dict) -> Requirements:
        by_category = {
            "functional": [],
            "non_functional": [],
            "operations": [],
            "integrations": [],
            "security": [],
            "constraints": [],
            "timeline": [],
            "risks": [],
        }

        for item in data.get("requirements", []):
            category = str(item.get("category", "")).strip().lower()
            if category not in by_category:
                continue
            by_category[category].append(
                RequirementItem(
                    id=str(item.get("id", "")).strip() or f"{category[:2].upper()}-{len(by_category[category]) + 1}",
                    text=str(item.get("requirement", "")).strip() or str(item.get("text", "")).strip(),
                    proposal=str(item.get("proposal", "")).strip(),
                    priority=self._normalize_priority(str(item.get("priority", "medium"))),
                    evidence=str(item.get("evidence", "")).strip(),
                )
            )

        return Requirements(**by_category)

    def _requirements_to_prompt_payload(self, requirements: Requirements) -> Dict[str, List[Dict[str, str]]]:
        return {
            "functional": [item.model_dump() for item in requirements.functional],
            "non_functional": [item.model_dump() for item in requirements.non_functional],
            "operations": [item.model_dump() for item in requirements.operations],
            "integrations": [item.model_dump() for item in requirements.integrations],
            "security": [item.model_dump() for item in requirements.security],
            "constraints": [item.model_dump() for item in requirements.constraints],
            "timeline": [item.model_dump() for item in requirements.timeline],
            "risks": [item.model_dump() for item in requirements.risks],
        }

    def _summarize_requirements(self, requirements: Requirements) -> List[str]:
        highlights: List[str] = []
        for category_name, items in self._requirements_to_prompt_payload(requirements).items():
            if items:
                highlights.append(f"{category_name}: {items[0]['text'][:60]}")
            if len(highlights) >= 5:
                break
        return highlights or ["요구사항 분석 결과 요약 필요"]

    def _normalize_priority(self, priority: str) -> str:
        normalized = priority.strip().lower()
        if normalized in {"high", "h"}:
            return "High"
        if normalized in {"low", "l"}:
            return "Low"
        return "Med"

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
            proposal_template="핵심 기능을 표준 아키텍처로 구현하고 검증 시나리오로 품질을 보장한다: {line}",
        )
        non_functional = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["성능", "안정", "품질", "응답시간"]),
            prefix="NF",
            fallback=["비기능 요구사항(성능/운영) 정의 필요"],
            priority="Med",
            proposal_template="SLA/KPI 기준을 정의하고 운영 표준 절차로 관리한다: {line}",
        )
        operations = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["운영", "장애", "모니터링", "지원"]),
            prefix="OP",
            fallback=["운영 요구사항(관제/장애대응/SLA) 정의 필요"],
            priority="Med",
            proposal_template="24x365 운영조직과 장애대응 프로세스를 적용한다: {line}",
        )
        integrations = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["연계", "외부", "내부 시스템", "API"]),
            prefix="IN",
            fallback=["연계 시스템 요구사항 및 인터페이스 정의 필요"],
            priority="Med",
            proposal_template="연계 인터페이스 표준 및 전구간 모니터링을 적용한다: {line}",
        )
        security = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["보안", "암호화", "인증", "권한", "준수"]),
            prefix="S",
            fallback=["보안/컴플라이언스 요구사항 확인 필요"],
            priority="High",
            proposal_template="보안통제(인증/권한/감사로그)와 컴플라이언스 점검을 병행한다: {line}",
        )
        constraints = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["제약", "예산", "범위", "필수"]),
            prefix="C",
            fallback=["예산/범위/정책 제약사항 확인 필요"],
            priority="Med",
            proposal_template="제약조건을 반영한 단계별 범위/변경 통제 계획을 수립한다: {line}",
        )
        timeline = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["일정", "기간", "단계", "마감", "월", "주"]),
            prefix="T",
            fallback=["주요 마일스톤 일정 정의 필요"],
            priority="Med",
            proposal_template="마일스톤 중심 수행계획과 점검 게이트를 운영한다: {line}",
        )
        risks = self._build_requirement_items(
            lines=self._pick_lines(source_lines, ["리스크", "위험", "문제", "이슈", "지연"]),
            prefix="R",
            fallback=["핵심 리스크 식별 및 대응 계획 수립 필요"],
            priority="Med",
            proposal_template="리스크별 예방/대응/복구 시나리오를 수립한다: {line}",
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
                operations=operations,
                integrations=integrations,
                security=security,
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
        proposal_template: str,
    ) -> List[RequirementItem]:
        base = lines if lines else fallback
        items: List[RequirementItem] = []
        for idx, line in enumerate(base, start=1):
            items.append(
                RequirementItem(
                    id=f"{prefix}-{idx}",
                    text=line,
                    proposal=proposal_template.format(line=line),
                    priority=priority,
                    evidence=line,
                )
            )
        return items

    def _build_outline_from_source(self, lines: List[str], slide_count: int) -> List[SlideOutline]:
        if not lines:
            lines = ["문서에서 유의미한 본문을 찾지 못했습니다."]

        proposal_sections = [
            ("사업/과업 이해", "고객 배경과 제안 목적 정리", "comparison_table"),
            ("요구사항-대응전략 매핑", "핵심 요구사항과 대응을 연결", "requirements_strategy_table"),
            ("요구사항 상세 분석", "기능/비기능/제약 사항을 구조화", "sla_support_table"),
            ("시스템 운영 및 개발운영 방안", "24x365 운영체계 제시", "layered_blocks"),
            ("장애 접수/대응 프로세스 및 SLA", "장애처리 절차와 SLA 제시", "incident_response_flow"),
            ("변경관리 대응 체계", "정책/보안/환경 변화 대응", "comparison_table"),
            ("연계 시스템 운영 및 모니터링", "외부/내부 연계 안정성 확보", "sla_support_table"),
            ("운영 조직 및 역할(R&R)", "운영 조직의 책임과 역할 정리", "operation_org_chart"),
            ("단계별 수행계획", "일정 및 마일스톤 제시", "timeline_plan"),
            ("기대효과/KPI 및 결론", "성과지표와 실행 결론 제시", "comparison_table"),
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

            layout = {}
            if section_title == "운영 조직 및 역할(R&R)":
                points = capabilities[:3]
                layout = {
                    "type": "org_chart",
                    "nodes": [
                        {"name": "운영총괄", "children": ["관제", "기술지원", "고객센터"]},
                    ],
                }
            elif section_title == "시스템 운영 및 개발운영 방안":
                points = [
                    "24x365 운영조직으로 상시 모니터링 및 장애예방",
                    "정기 점검/패치/성능관리의 운영 표준화",
                    "운영 이슈의 주간/월간 리포팅 체계 운영",
                ]
                layout = {
                    "type": "layers",
                    "layers": ["관제", "장애대응", "변경관리", "지속개선"],
                }
            elif section_title == "단계별 수행계획":
                points = [
                    "1단계: 요구사항 상세화 및 범위 확정",
                    "2단계: 설계/개발/연동 및 품질 검증",
                    "3단계: 안정화/교육/운영 이관",
                ]
                layout = {
                    "type": "timeline",
                    "phases": [
                        {"name": "착수/분석", "detail": "요구사항 확정"},
                        {"name": "구현/검증", "detail": "개발·연동·테스트"},
                        {"name": "전환/안정화", "detail": "운영 이관 및 모니터링"},
                    ],
                }
            elif section_title == "요구사항-대응전략 매핑":
                for j in range(3):
                    idx = (start_idx + j) % len(lines)
                    points.append(lines[idx][:80])
                layout = {
                    "type": "table",
                    "columns": ["요구사항", "우선순위", "대응전략"],
                    "rows": [[points[0], "High", "전담 조직 배치 및 SLA 운영"], [points[1], "Med", "변경관리 프로세스 적용"], [points[2], "Med", "모니터링 자동화 적용"]],
                }
            elif section_title == "요구사항 상세 분석":
                for j in range(3):
                    idx = (start_idx + j) % len(lines)
                    points.append(lines[idx][:80])
                layout = {
                    "type": "table",
                    "columns": ["구분", "요구사항", "대응방안"],
                    "rows": [["기능", points[0], "표준 아키텍처 기반 구현"], ["비기능", points[1], "SLA/모니터링 체계 적용"], ["운영", points[2], "24x365 운영 프로세스 적용"]],
                }
            elif section_title == "장애 접수/대응 프로세스 및 SLA":
                points = [
                    "장애 접수 즉시 영향도 분류 및 우선순위 지정",
                    "접수→분석→조치→검증→보고 표준 절차 운영",
                    "SLA 기준 복구 목표시간 관리",
                ]
                layout = {
                    "type": "process_flow",
                    "steps": ["접수", "영향도 분석", "조치", "검증", "재발방지"],
                }
            elif section_title == "기대효과/KPI 및 결론":
                points = [
                    "우선순위 요구사항부터 단계적 착수 제안",
                    "착수 전 워크숍으로 범위·일정·KPI 확정",
                    "의사결정 후 즉시 실행 가능한 준비 완료",
                ]
                layout = {
                    "type": "layers",
                    "layers": ["요구정의", "구현", "운영", "고도화"],
                }
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
                    layout=layout,
                    speaker_note=f"문서 근거 기반 제안. 참고 문장: {note_evidence}",
                )
            )

        return outlines
