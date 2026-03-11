from __future__ import annotations

from pydantic import BaseModel, Field


class ImagePrompt(BaseModel):
    shot_id: str
    prompt: str
    negative_prompt: str = ""
    output_size: str


class ImagePromptPlan(BaseModel):
    prompts: list[ImagePrompt] = Field(default_factory=list)

