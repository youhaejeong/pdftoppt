from typing import List, Literal

from pydantic import BaseModel, Field


Priority = Literal["High", "Med", "Low"]


class RequirementItem(BaseModel):
    id: str
    text: str
    priority: Priority
    evidence: str = ""


class Requirements(BaseModel):
    functional: List[RequirementItem] = Field(default_factory=list)
    non_functional: List[RequirementItem] = Field(default_factory=list)
    constraints: List[RequirementItem] = Field(default_factory=list)
    timeline: List[RequirementItem] = Field(default_factory=list)
    risks: List[RequirementItem] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    title: str
    type: str
    purpose: str
    audience: str
    key_takeaways: List[str] = Field(default_factory=list)


class SlideOutline(BaseModel):
    slide_no: int
    title: str
    objective: str
    key_points: List[str]
    visual_type: str
    speaker_note: str


class PipelineResult(BaseModel):
    document_summary: DocumentSummary
    requirements: Requirements
    ppt_outline: List[SlideOutline]
    open_questions: List[str]


class ProcessResponse(BaseModel):
    result: PipelineResult
    output_ppt_path: str
