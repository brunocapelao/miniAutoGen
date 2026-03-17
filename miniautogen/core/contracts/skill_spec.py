"""Skill specification for the MiniAutoGen SDK.

Skills are reusable units of behavioral knowledge and operational
instruction. SkillSpec is the metadata schema; the actual skill
content lives in SKILL.md alongside the spec.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillActivation(BaseModel):
    """When this skill should be activated."""

    keywords: list[str] = Field(default_factory=list)


class SkillSpec(BaseModel):
    """Metadata for a skill definition.

    This is the canonical schema for ``skill.yaml`` files.
    The actual skill instructions live in ``SKILL.md``.
    """

    id: str
    version: str = "1.0.0"
    name: str
    description: str = ""
    activation: SkillActivation = Field(
        default_factory=SkillActivation,
    )
    tool_hints: dict[str, list[str]] = Field(
        default_factory=dict,
    )
    permissions: dict[str, str] = Field(
        default_factory=dict,
    )
