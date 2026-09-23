from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, TypeAdapter, field_validator, model_validator

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Level = Literal['draft', 'working', 'ready', 'priority']


class ApiModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ErrorResponse(ApiModel):
    code: str
    message: str
    field_errors: dict[str, str] | None = None


class Identity(ApiModel):
    id: str
    name: str
    role: Literal['business', 'team']
    team_id: str | None = None
    interests: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class TaskFields(ApiModel):
    title: str = ''
    topic: str = ''
    context: str = ''
    need: str = ''
    users: str = ''
    data_materials: str = ''
    constraints: str = ''
    expected_result: str = ''
    success_criteria: str = ''
    contact: str = ''
    consultation: str = ''


class TaskCreate(TaskFields):
    pass


class TaskPatch(TaskFields):
    pass


class Answer(ApiModel):
    question: NonBlank
    answer: str = ''


class ComposeRequest(ApiModel):
    answers: list[Answer] = Field(default_factory=list)


class QuestionResponse(ApiModel):
    questions: list[NonBlank] = Field(min_length=3, max_length=5)


class RatingCategory(ApiModel):
    key: str
    label: str
    points: int = Field(ge=0)
    max_points: int
    basis: list[str]


class Rating(ApiModel):
    total: int = Field(ge=0, le=100)
    level: Level
    categories: list[RatingCategory]
    missing: list[str]


class TaskResponse(TaskFields):
    id: str
    owner_id: str
    confirmed: bool
    published: bool
    version: int
    rating: Rating
    published_rating: Rating | None
    created_at: str
    updated_at: str


class TaskList(ApiModel):
    items: list[TaskResponse]


class ProposalCreate(ApiModel):
    idea: NonBlank
    plan: NonBlank
    duration: NonBlank
    prototype_url: str = ''

    @field_validator('prototype_url')
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if value:
            TypeAdapter(HttpUrl).validate_python(value)
        return value


class DecisionRequest(ApiModel):
    decision: Literal['selected', 'rejected']


class MilestoneRequest(ApiModel):
    description: NonBlank
    result_url: NonBlank

    @field_validator('result_url')
    @classmethod
    def validate_url(cls, value: str) -> str:
        TypeAdapter(HttpUrl).validate_python(value)
        return value


class ReviewRequest(ApiModel):
    decision: Literal['confirmed', 'changes_requested']
    comment: str = ''

    @model_validator(mode='after')
    def require_return_comment(self):
        self.comment = self.comment.strip()
        if self.decision == 'changes_requested' and not self.comment:
            raise ValueError('Для возврата на доработку нужен комментарий')
        return self


class MilestoneResponse(ApiModel):
    id: str
    proposal_id: str
    description: str
    result_url: str
    status: Literal['submitted', 'confirmed', 'changes_requested']
    comment: str
    points_awarded: int = Field(ge=0, le=10)


class ProposalResponse(ApiModel):
    idea: str
    plan: str
    duration: str
    prototype_url: str
    id: str
    task_id: str
    team_id: str
    status: Literal['pending', 'selected', 'rejected']
    created_at: str
    milestone: MilestoneResponse | None = None


class ProposalList(ApiModel):
    items: list[ProposalResponse]


class TeamProposalList(ProposalList):
    team_points: int = Field(ge=0)
