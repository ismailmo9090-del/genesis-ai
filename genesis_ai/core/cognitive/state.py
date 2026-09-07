"""CognitiveState — structured internal state passed between all cognitive engines.

This is the single source of truth for what Genesis "knows" and "thinks" about
a given interaction at any point in the pipeline. Every engine reads from and
writes to this state. It is NEVER exposed to the user.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GoalType(str, Enum):
    CONVERSATION = "conversation"
    FACTUAL = "factual"
    CODE = "code"
    RESEARCH = "research"
    CREATIVE = "creative"
    FIX = "fix"
    EXPLAIN = "explain"
    COMPARE = "compare"
    IDENTITY = "identity"
    UNKNOWN = "unknown"


class Complexity(str, Enum):
    TRIVIAL = "trivial"      # greetings, acks — minimal cognition
    SIMPLE = "simple"        # single-fact lookup, basic code
    MODERATE = "moderate"    # multi-step, some reasoning
    COMPLEX = "complex"      # research + reasoning + verification
    EVOLVING = "evolving"    # topic changes over time, needs update detection


class KnowledgeStatus(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    UNCERTAIN = "uncertain"
    OUTDATED = "outdated"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"


class DecisionAction(str, Enum):
    RESPOND = "respond"
    RECALL = "recall"
    REASON = "reason"
    SEARCH = "search"
    DEEP_RESEARCH = "deep_research"
    USE_TOOL = "use_tool"
    ASK_CLARIFICATION = "ask_clarification"
    REFLECT = "reflect"
    LEARN = "learn"
    SKIP = "skip"


class Confidence(str, Enum):
    VERY_LOW = "very_low"    # 0.0 - 0.2
    LOW = "low"              # 0.2 - 0.4
    MEDIUM = "medium"        # 0.4 - 0.6
    HIGH = "high"            # 0.6 - 0.8
    VERY_HIGH = "very_high"  # 0.8 - 1.0


@dataclass
class CognitiveState:
    """Structured internal state for a single interaction.

    This object flows through the entire cognitive pipeline. Each engine
    reads relevant fields and writes its findings back. The state is
    NEVER exposed to the user — only the final response is.
    """

    # ── Input ──
    raw_input: str = ""
    user_id: str = ""
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # ── Perception ──
    cleaned_input: str = ""
    detected_language: str = "english"
    word_count: int = 0
    is_question: bool = False
    is_command: bool = False
    is_greeting: bool = False
    is_followup: bool = False
    contains_code: bool = False
    contains_entities: bool = False

    # ── Understanding ──
    goal_type: GoalType = GoalType.UNKNOWN
    intent: str = ""
    complexity: Complexity = Complexity.SIMPLE
    domain: str = "general"
    entities: dict = field(default_factory=dict)
    concepts: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    output_type: str = "text"
    sub_goals: list[str] = field(default_factory=list)

    # ── Context ──
    conversation_history: list[dict] = field(default_factory=list)
    previous_entity: Optional[str] = None
    context_entity: Optional[str] = None
    active_topic: str = ""

    # ── Phase 2: Conversation State ──
    resolved_references: dict = field(default_factory=dict)
    user_goal: str = "unknown"
    previous_goal: str = "unknown"
    topic_changed: bool = False
    context_relevant_turns: list = field(default_factory=list)
    context_relevance_score: float = 0.0
    clarification_needed: bool = False
    correction_pending: bool = False
    short_term_summary: dict = field(default_factory=dict)

    # ── Knowledge State ──
    known_information: list[dict] = field(default_factory=list)
    unknown_information: list[str] = field(default_factory=list)
    uncertain_information: list[str] = field(default_factory=list)
    knowledge_gaps: list[str] = field(default_factory=list)
    knowledge_status: KnowledgeStatus = KnowledgeStatus.UNKNOWN
    relevant_memories: list[dict] = field(default_factory=list)
    relevant_experiences: list[dict] = field(default_factory=list)
    local_knowledge: list[dict] = field(default_factory=list)

    # ── Learned Knowledge (from Learning → Inference Bridge) ──
    learned_knowledge: list = field(default_factory=list)
    learned_generalizations: list = field(default_factory=list)
    learned_skills: list = field(default_factory=list)
    learned_intent_patterns: list = field(default_factory=list)
    learning_retrieval_ms: float = 0.0
    learned_intent_source: str = ""  # "static", "learned", "learned_override"
    learned_intent_confidence: float = 0.0

    # ── Reasoning ──
    assumptions: list[str] = field(default_factory=list)
    candidate_actions: list[DecisionAction] = field(default_factory=list)
    selected_action: DecisionAction = DecisionAction.RESPOND
    reasoning_result: Optional[dict] = None
    plan_steps: list[str] = field(default_factory=list)

    # ── Research ──
    research_needed: bool = False
    research_queries: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    comparison_result: Optional[dict] = None
    contradictions: list[dict] = field(default_factory=list)

    # ── Response ──
    response_text: str = ""
    response_confidence: float = 0.0
    response_sources: list[str] = field(default_factory=list)
    response_evaluated: bool = False
    evaluation_issues: list[str] = field(default_factory=list)
    needs_revision: bool = False

    # ── Learning ──
    experience_recorded: bool = False
    lessons_learned: list[str] = field(default_factory=list)
    generalizations: list[str] = field(default_factory=list)
    knowledge_updated: bool = False
    skills_used: list[str] = field(default_factory=list)
    skills_created: list[str] = field(default_factory=list)

    # ── Performance ──
    start_time: float = field(default_factory=time.time)
    stages_completed: list[str] = field(default_factory=list)
    total_duration: float = 0.0

    # ── Metadata ──
    msg_type: str = "FACTUAL"
    confidence_score: float = 0.9
    error: Optional[str] = None

    def mark_stage(self, stage_name: str):
        """Record that a pipeline stage has been completed."""
        self.stages_completed.append(stage_name)

    def set_confidence(self, score: float):
        """Set confidence and update the enum label."""
        self.confidence_score = max(0.0, min(1.0, score))
        if score >= 0.8:
            self.response_confidence = score
        elif score >= 0.6:
            self.response_confidence = score
        else:
            self.response_confidence = score

    def add_knowledge_gap(self, gap: str):
        """Record a knowledge gap that needs research."""
        if gap not in self.knowledge_gaps:
            self.knowledge_gaps.append(gap)
            self.unknown_information.append(gap)

    def is_trivial(self) -> bool:
        """Check if this input needs minimal cognition."""
        return self.complexity == Complexity.TRIVIAL

    def is_research_task(self) -> bool:
        """Check if this requires web research."""
        return self.selected_action in (
            DecisionAction.SEARCH,
            DecisionAction.DEEP_RESEARCH,
        )

    def to_dict(self) -> dict:
        """Serialize state for logging (never exposed to user)."""
        return {
            "goal_type": self.goal_type.value,
            "intent": self.intent,
            "complexity": self.complexity.value,
            "domain": self.domain,
            "entities": self.entities,
            "knowledge_status": self.knowledge_status.value,
            "selected_action": self.selected_action.value,
            "confidence": self.confidence_score,
            "stages": self.stages_completed,
            "duration": self.total_duration,
        }
