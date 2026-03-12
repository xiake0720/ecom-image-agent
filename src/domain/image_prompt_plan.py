from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ImagePrompt(BaseModel):
    shot_id: str
    shot_type: str = ""
    prompt: str
    negative_prompt: list[str] = Field(default_factory=list)
    output_size: str
    preserve_rules: list[str] = Field(default_factory=list)
    text_space_hint: str = ""
    composition_notes: list[str] = Field(default_factory=list)
    style_notes: list[str] = Field(default_factory=list)

    @field_validator("negative_prompt", "preserve_rules", "composition_notes", "style_notes", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            normalized = value.replace("\r", "\n")
            chunks = []
            for part in normalized.replace("，", ",").split("\n"):
                for inner in part.split(","):
                    item = inner.strip()
                    if item:
                        chunks.append(item)
            return chunks
        return value


class ImagePromptPlan(BaseModel):
    prompts: list[ImagePrompt] = Field(default_factory=list)
