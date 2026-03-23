from app.services.llm_service import LLMService
from pathlib import Path


def test_fallback_generates_varied_slide_points():
    svc = LLMService()
    text = """프로젝트 배경 설명\n기능 요구사항: 사용자 인증\n기능 요구사항: 대시보드\n비기능 요구사항: 응답시간 1초 이내\n일정: 6월 1차 오픈\n리스크: 외부 연동 지연 가능성\n"""

    result, meta = svc.build_result(
        text=text,
        purpose="내부 공유",
        audience="팀",
        tone="공식적",
        slide_count=4,
    )

    assert meta.mode in ["openai", "fallback"]
    assert len(result.ppt_outline) == 4
    assert isinstance(result.ppt_outline[0].layout, dict)

    if meta.mode == "fallback":
        slide1 = result.ppt_outline[0].key_points
        slide2 = result.ppt_outline[1].key_points
        assert slide1 != slide2
        assert result.requirements.operations
        assert result.requirements.integrations
        assert result.requirements.security


def test_fallback_uses_prompt_visual_type_values():
    svc = LLMService()
    result, meta = svc.build_result(
        text="운영 요구사항 24x365 장애 대응",
        purpose="내부 공유",
        audience="팀",
        tone="공식적",
        slide_count=3,
    )

    if meta.mode == "fallback":
        allowed_visuals = {
            "requirements_strategy_table",
            "sla_support_table",
            "process_flow",
            "incident_response_flow",
            "operation_org_chart",
            "timeline_plan",
            "layered_blocks",
            "comparison_table",
        }
        for slide in result.ppt_outline:
            assert slide.visual_type in allowed_visuals


def test_openai_call_uses_split_prompts_and_merges_results():
    class DummyResponse:
        def __init__(self, content: str):
            class Choice:
                class Message:
                    pass

                message = Message()

            choice = Choice()
            choice.message.content = content
            self.choices = [choice]

    captured_messages = []

    class DummyCompletions:
        def create(self, **kwargs):
            captured_messages.append(kwargs["messages"])
            if len(captured_messages) == 1:
                return DummyResponse(
                    '{"requirements":[{"id":"F-1","category":"functional","requirement":"핵심 업무기능 제공","proposal":"","priority":"high","evidence":"기능 요구사항"}]}'
                )
            if len(captured_messages) == 2:
                return DummyResponse(
                    '{"requirements":[{"id":"F-1","category":"functional","requirement":"핵심 업무기능 제공","proposal":"표준 아키텍처로 구축","priority":"high","evidence":"기능 요구사항"}]}'
                )
            return DummyResponse(
                '{"ppt_outline":[{"slide_no":1,"title":"요구사항 개요","objective":"핵심 요구 정리","key_points":["핵심 업무기능 제공"],"visual_type":"table","layout":{"type":"table","columns":["항목"],"rows":[["기능"]]},"speaker_note":"요구사항 기반 설명"}]}'
            )

    class DummyChat:
        completions = DummyCompletions()

    class DummyClient:
        chat = DummyChat()

    svc = LLMService()
    svc.client = DummyClient()

    result = svc._call_openai(
        text="본문 텍스트",
        purpose="의사결정",
        audience="임원",
        tone="데이터 중심",
        slide_count=7,
    )

    assert len(captured_messages) == 3

    requirements_user_message = captured_messages[0][1]["content"]
    proposal_user_message = captured_messages[1][1]["content"]
    ppt_user_message = captured_messages[2][1]["content"]

    assert "[RFP 원문]" in requirements_user_message
    assert "본문 텍스트" in requirements_user_message
    assert "[고객 요구사항 JSON]" in proposal_user_message
    assert "[요구사항 JSON]" in ppt_user_message
    assert "핵심 업무기능 제공" in ppt_user_message
    assert "표준 아키텍처로 구축" in ppt_user_message

    assert result.requirements.functional[0].priority == "High"
    assert result.requirements.functional[0].proposal == "표준 아키텍처로 구축"
    assert result.ppt_outline[0].visual_type == "table"


def test_fallback_proposal_contains_operational_summary_lines():
    svc = LLMService()
    result, meta = svc.build_result(
        text="운영 요구사항: 홈페이지 무중단 운영 및 장애 대응 체계 필요",
        purpose="제안 발표",
        audience="발주처",
        tone="공식적",
        slide_count=10,
    )

    if meta.mode == "fallback":
        proposal = result.requirements.operations[0].proposal
        assert "\n" in proposal
        assert "24x365" in proposal
        assert "운영총괄" in proposal


def test_prompt_files_include_summary_guidance_for_grouped_messages():
    proposal_prompt = Path("app/prompts/proposal_system_prompt.txt").read_text(encoding="utf-8")
    ppt_prompt = Path("app/prompts/ppt_system_prompt.txt").read_text(encoding="utf-8")

    assert "상위 개념으로 묶어 요약" in proposal_prompt
    assert "Marketing DB" in proposal_prompt
    assert "상위 메시지로 묶어" in ppt_prompt
    assert "리드 수집-분석-세일즈 활용 체계" in ppt_prompt
