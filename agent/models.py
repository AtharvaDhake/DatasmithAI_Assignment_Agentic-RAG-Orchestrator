from enum import Enum
from typing import Optional, Any, List
from pydantic import BaseModel, Field


class IntentLabel(str, Enum):
    SUMMARIZE          = "summarize"
    SENTIMENT          = "sentiment"
    CODE_EXPLAIN       = "code_explain"
    YOUTUBE_TRANSCRIPT = "youtube_transcript"
    IMAGE_PDF_EXTRACT  = "image_pdf_extract"
    AUDIO_TRANSCRIBE   = "audio_transcribe"
    RAG_QA             = "rag_qa"
    CONVERSATIONAL     = "conversational"
    UNCLEAR            = "unclear"


class ExecutionStep(BaseModel):
    step_number: int
    total_steps: int
    action: str
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None


class ExecutionPlan(BaseModel):
    steps: List[ExecutionStep] = []
    current_step: int = 0
    plan_description: str = ""

    def add_step(self, action: str) -> ExecutionStep:
        step = ExecutionStep(
            step_number=len(self.steps) + 1,
            total_steps=len(self.steps) + 1,
            action=action
        )
        self.steps.append(step)
        return step

    def finalize(self):
        total = len(self.steps)
        for step in self.steps:
            step.total_steps = total


class IntentResult(BaseModel):
    intent: IntentLabel
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool
    clarification_question: Optional[str] = None
    reasoning: str


class ToolOutput(BaseModel):
    extracted_text: Optional[str] = None
    result: str
    execution_log: List[str] = []
    intent: IntentLabel
    metadata: dict[str, Any] = {}
    response_type: str = "answer"


class AgentResponse(BaseModel):
    response_type: str
    result: str
    extracted_text: Optional[str] = None
    execution_log: List[str] = []
    execution_plan: Optional[ExecutionPlan] = None
    intent: str = ""
    metadata: dict[str, Any] = {}


class FileValidationError(BaseModel):
    error: str
    detail: str
    max_size_mb: Optional[float] = None
