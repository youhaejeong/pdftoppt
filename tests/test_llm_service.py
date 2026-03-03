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

    # fallback일 때는 슬라이드별 포인트가 동일 고정 문구가 아니어야 함
    if meta.mode == "fallback":
        slide1 = result.ppt_outline[0].key_points
        slide2 = result.ppt_outline[1].key_points
        assert slide1 != slide2
