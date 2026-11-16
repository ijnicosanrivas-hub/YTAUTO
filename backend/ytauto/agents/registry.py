"""Registro de los nueve agentes."""
from __future__ import annotations

from .base import Agent
from .chief import ChiefAgent
from .director import DirectorAgent
from .editor import EditorAgent
from .publisher import PublisherAgent
from .resources import ResourcesAgent
from .reviewer import ReviewerAgent
from .scriptwriter import ScriptwriterAgent
from .sound import SoundAgent
from .voice import VoiceAgent

AGENT_CLASSES: tuple[type[Agent], ...] = (
    ChiefAgent, DirectorAgent, ScriptwriterAgent, ResourcesAgent, VoiceAgent,
    EditorAgent, SoundAgent, ReviewerAgent, PublisherAgent,
)


def build_agents() -> dict[str, Agent]:
    return {cls.name: cls() for cls in AGENT_CLASSES}
