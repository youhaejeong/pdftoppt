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
