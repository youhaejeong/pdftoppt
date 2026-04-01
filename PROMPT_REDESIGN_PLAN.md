# Prompt Redesign Plan (Project Applied)

## 1) 목적
이 문서는 `PDF → 과업추출 → 요구사항 → 대응전략 틀 → 2~3줄 제안요약 → PPT` 파이프라인의 프롬프트 품질을 안정화하기 위한 실행 계획이다.

핵심 목표:
- RFP 원문에서 행정/배경 정보가 섞이지 않도록 단계별 책임을 분리한다.
- 중간 산출물(JSON 계약)을 고정해 단계 간 품질 저하를 방지한다.
- 최종 PPT가 "요구 나열"이 아니라 "제안 메시지" 중심으로 생성되도록 강제한다.

---

## 2) 현재 파이프라인(적용 대상)
현재 코드 기준 단계:
1. Task Scope Extraction
2. Requirements Structuring
3. Proposal Framework
4. Proposal Summary (2~3 lines)
5. PPT Outline

본 계획은 위 5단계를 유지하되, 각 단계의 입력/출력/금지사항/품질게이트를 명시적으로 운영한다.

---

## 3) 단계별 운영 계약

### Stage 1. Task Scope Extraction
- **입력**: RFP 원문 텍스트
- **출력**: `task_scope: string[]`
- **포함**: 과제사항, 주요업무, 수행범위
- **제외**:
  - 제안서 제출일자/입찰 일정
  - 사업개요/목적/배경
  - 일반 안내/목차성 문구
- **예외 규칙**:
  - 동사가 없어도 과업성 명사구(예: 채널 최적화, 콘텐츠 현행화, 랜딩페이지 제작)는 포함
- **품질게이트**:
  - 중복 항목 통합
  - 추출 항목 0개면 `"과제사항 추출 결과 없음"` 표기 후 downstream 경고

### Stage 2. Requirements Structuring
- **입력**: Stage1의 `task_scope[]`
- **출력**: `requirements[]`
- **카테고리**:
  - functional
  - non_functional
  - operations
  - integrations
  - security
  - constraints
- **제외**:
  - KPI/정량목표, 프로젝트 일정, 리스크(이 단계 기본 제외)
- **품질게이트**:
  - 항목별 `evidence` 필수
  - `priority`는 `high|medium|low`

### Stage 3. Proposal Framework
- **입력**: Stage2 `requirements[]`
- **출력**: `proposal_framework[]`
- **필수 구조**:
  - id/category/requirement/priority/evidence 유지
  - `strategy_points[]`에 아래 중 2개 이상 반영
    - How (수행방법)
    - Who (투입조직/역할)
    - When (적용단계)
    - How well (SLA/KPI)
- **품질게이트**:
  - requirement와 무관한 strategy_points 금지

### Stage 4. Proposal Summary (2~3 lines)
- **입력**: Stage3 `proposal_framework[]`
- **출력**: `requirements[]` (proposal 채움)
- **규칙**:
  - `proposal`은 2~3줄
  - 세부 항목 나열 대신 상위 메시지 요약
  - 구현방식 + 운영/인력 + 성과/품질 중 2개 이상 반영
- **품질게이트**:
  - 1줄짜리 proposal 금지
  - 추상표현만 있는 문장 금지

### Stage 5. PPT Outline
- **입력**: proposal이 채워진 `requirements[]`
- **출력**: `ppt_outline[]`
- **규칙**:
  - slide_count: 10~50
  - key_points/visual_type/layout/speaker_note 필수
  - proposal의 핵심 메시지를 슬라이드 메시지로 변환
- **품질게이트**:
  - key_points에 단순 요구 나열 금지
  - 운영/보안/연계는 실제 수행체계가 보이게 구성

---

## 4) JSON 계약(Contract)

### Stage1 Output
```json
{ "task_scope": ["..."] }
```

### Stage2 Output
```json
{
  "requirements": [
    {
      "id": "",
      "category": "",
      "requirement": "",
      "proposal": "",
      "priority": "",
      "evidence": ""
    }
  ]
}
```

### Stage3 Output
```json
{
  "proposal_framework": [
    {
      "id": "",
      "category": "",
      "requirement": "",
      "priority": "",
      "evidence": "",
      "strategy_points": ["", "", ""]
    }
  ]
}
```

### Stage4 Output
```json
{
  "requirements": [
    {
      "id": "",
      "category": "",
      "requirement": "",
      "proposal": "",
      "priority": "",
      "evidence": ""
    }
  ]
}
```

### Stage5 Output
```json
{
  "ppt_outline": [
    {
      "slide_no": 1,
      "title": "",
      "objective": "",
      "key_points": [],
      "visual_type": "",
      "layout": {},
      "speaker_note": ""
    }
  ]
}
```

---

## 5) 운영 체크리스트

### 프롬프트 변경 전
- 변경 대상 stage 명시
- JSON 계약 변경 여부 확인
- 하위 stage 영향도 확인

### 프롬프트 변경 후
- `tests/test_llm_service.py` 수행
- 샘플 RFP 3종 수동 점검
  1) 운영 중심
  2) 마케팅/채널 중심
  3) AI Agent 중심

### 실패 판단 기준
- Stage1에 일정/사업개요가 포함되면 실패
- Stage3에 strategy_points 빈 값이면 실패
- Stage4 proposal이 1줄이면 실패
- Stage5 key_points가 원문 복붙이면 실패

---

## 6) 단계별 소유권(Owner)
- Stage1~2: 요구사항 분석 담당
- Stage3~4: 제안 PM 담당
- Stage5: 발표자료 설계 담당
- 품질게이트 승인: PM 리드

---

## 7) 즉시 실행 액션 (이번 스프린트)
1. 샘플 RFP 3종 기준으로 stage별 기대 출력 예시 문서화
2. Stage4(2~3줄 요약) 실패 케이스 수집 및 금지 패턴 목록화
3. Stage5 슬라이드 메시지 품질 기준(요약/구체성) 리뷰 체크리스트 추가
