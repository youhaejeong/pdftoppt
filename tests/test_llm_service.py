from app.services.llm_service import LLMService


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

    # fallback일 때는 슬라이드별 포인트가 동일 고정 문구가 아니어야 함
    if meta.mode == "fallback":
        slide1 = result.ppt_outline[0].key_points
        slide2 = result.ppt_outline[1].key_points
        assert slide1 != slide2


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


def test_openai_call_uses_user_prompt_template_file():
    class DummyResponse:
        class Choice:
            class Message:
                content = '{"document_summary":{"title":"t","type":"report","purpose":"p","audience":"a","key_takeaways":["k"]},"requirements":{"functional":[],"non_functional":[],"constraints":[],"timeline":[],"risks":[]},"ppt_outline":[],"open_questions":[]}'

            message = Message()

        choices = [Choice()]

    captured = {}

    class DummyCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return DummyResponse()

    class DummyChat:
        completions = DummyCompletions()

    class DummyClient:
        chat = DummyChat()

    svc = LLMService()
    svc.client = DummyClient()

    svc._call_openai(
        text="본문 텍스트",
        purpose="의사결정",
        audience="임원",
        tone="데이터 중심",
        slide_count=7,
    )

    user_message = captured["messages"][1]["content"]
    assert "[발표 목적]" in user_message
    assert "의사결정" in user_message
    assert "[청중]" in user_message
    assert "임원" in user_message
    assert "[톤앤매너]" in user_message
    assert "데이터 중심" in user_message
    assert "[분량]" in user_message
    assert "7" in user_message
