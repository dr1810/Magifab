"""User and companion preferences shared by retrieval and reasoning."""
from pydantic import BaseModel, ConfigDict, Field


class AccessibilityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accessibility_needs: list[str] = Field(default_factory=list)
    detail_level: str = "brief"
    preferred_prompt_types: list[str] = Field(default_factory=list)
    conversation_simplification: bool = True
    vocabulary_assistance: bool = True


class CompanionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "Companion"
    personality: str = "warm"
    conversation_style: str = "simple"
