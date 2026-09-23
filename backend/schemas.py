from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    field_errors: dict[str, str] | None = None


class Identity(BaseModel):
    id: str
    name: str
    role: Literal["business", "team"]
    team_id: str | None = None


class TaskFields(BaseModel):
    title: str = ""
    topic: str = ""
    context: str = ""
    need: str = ""
    users: str = ""
    data_materials: str = ""
    constraints: str = ""
    expected_result: str = ""
    success_criteria: str = ""
    contact: str = ""
    consultation: str = ""


class TaskCreate(TaskFields):
    pass


class TaskPatch(TaskFields):
    pass


class Answer(BaseModel):
    question: str
    answer: str = ""


class ComposeRequest(BaseModel):
    answers: list[Answer] = Field(default_factory=list)


class QuestionResponse(BaseModel):
    questions: list[str]


class RatingCategory(BaseModel):
    key: str
    label: str
    points: int
    max_points: int
    basis: list[str]


class Rating(BaseModel):
    total: int
    level: Literal["draft", "working", "ready", "priority"]
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


class ProposalCreate(BaseModel):
    idea: str = Field(min_length=1)
    plan: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    prototype_url: str = ""


class DecisionRequest(BaseModel):
    decision: Literal["selected", "rejected"]


class MilestoneRequest(BaseModel):
    description: str = Field(min_length=1)
    result_url: str = ""

class ReviewRequest(BaseModel):
    decision: Literal["confirmed", "changes_requested"]
    comment: str = ""
