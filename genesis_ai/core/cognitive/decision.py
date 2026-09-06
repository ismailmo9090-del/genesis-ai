"""DecisionOrchestrator — dynamically decides what action Genesis should take.

Replaces hardcoded if/elif routing with dynamic decision-making based on:
- goal type
- context
- knowledge state
- confidence
- uncertainty
- complexity
- available tools
- user requirements

NEVER creates question-specific routing. All decisions are structural.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import CognitiveState

from .state import (
    CognitiveState,
    Complexity,
    DecisionAction,
    GoalType,
    KnowledgeStatus,
)

logger = logging.getLogger(__name__)


class DecisionOrchestrator:
    """Decides the next action based on the current cognitive state.

    The orchestrator does NOT hardcode question→action mappings.
    It evaluates the state structurally and chooses the best action.
    """

    def decide(self, state: CognitiveState) -> CognitiveState:
        """Analyze the cognitive state and select the best action.

        This is the core decision function. It runs AFTER understanding
        and BEFORE any action. It determines the entire downstream path.
        """
        state.candidate_actions = self._generate_candidates(state)
        state.selected_action = self._select_best(state)
        state.mark_stage("DECISION_MADE")
        return state

    def _generate_candidates(self, state: CognitiveState) -> list[DecisionAction]:
        """Generate all plausible actions for this state."""
        candidates = []

        # ── Trivial inputs: respond immediately ──
        if state.complexity == Complexity.TRIVIAL:
            return [DecisionAction.RESPOND]

        # ── Identity questions: respond from knowledge ──
        if state.goal_type == GoalType.IDENTITY:
            return [DecisionAction.RESPOND]

        # ── Conversational: respond from conversation skills ──
        if state.goal_type == GoalType.CONVERSATION:
            return [DecisionAction.RESPOND]

        # ── Code tasks: generate or search ──
        if state.goal_type == GoalType.CODE:
            candidates.append(DecisionAction.RESPOND)
            if state.knowledge_status in (
                KnowledgeStatus.UNKNOWN,
                KnowledgeStatus.UNVERIFIED,
            ):
                candidates.append(DecisionAction.SEARCH)
            return candidates

        # ── Factual: recall or search ──
        if state.goal_type == GoalType.FACTUAL:
            candidates.append(DecisionAction.RECALL)
            if state.knowledge_status in (
                KnowledgeStatus.UNKNOWN,
                KnowledgeStatus.OUTDATED,
                KnowledgeStatus.CONTRADICTED,
            ):
                candidates.append(DecisionAction.SEARCH)
            if state.complexity in (Complexity.MODERATE, Complexity.COMPLEX):
                candidates.append(DecisionAction.REASON)
            return candidates

        # ── Research: deep research ──
        if state.goal_type == GoalType.RESEARCH:
            candidates.append(DecisionAction.RECALL)
            candidates.append(DecisionAction.DEEP_RESEARCH)
            candidates.append(DecisionAction.REASON)
            return candidates

        # ── Fix tasks: reason + search ──
        if state.goal_type == GoalType.FIX:
            candidates.append(DecisionAction.REASON)
            candidates.append(DecisionAction.SEARCH)
            candidates.append(DecisionAction.RESPOND)
            return candidates

        # ── Explain: recall + respond ──
        if state.goal_type == GoalType.EXPLAIN:
            candidates.append(DecisionAction.RECALL)
            candidates.append(DecisionAction.RESPOND)
            return candidates

        # ── Compare: reason + respond ──
        if state.goal_type == GoalType.COMPARE:
            candidates.append(DecisionAction.REASON)
            candidates.append(DecisionAction.SEARCH)
            candidates.append(DecisionAction.RESPOND)
            return candidates

        # ── Creative: respond with generation ──
        if state.goal_type == GoalType.CREATIVE:
            candidates.append(DecisionAction.RESPOND)
            if state.knowledge_status == KnowledgeStatus.UNKNOWN:
                candidates.append(DecisionAction.SEARCH)
            return candidates

        # ── Unknown: try to figure out ──
        candidates.append(DecisionAction.RECALL)
        candidates.append(DecisionAction.REASON)
        candidates.append(DecisionAction.ASK_CLARIFICATION)
        return candidates

    def _select_best(self, state: CognitiveState) -> DecisionAction:
        """Select the best action from candidates based on state evaluation.

        Priority logic (structural, NOT question-specific):
        1. If knowledge is sufficient → RESPOND
        2. If knowledge is missing → SEARCH or RECALL
        3. If complexity requires reasoning → REASON
        4. If nothing works → ASK_CLARIFICATION
        """
        candidates = state.candidate_actions
        if not candidates:
            return DecisionAction.RESPOND

        # Score each candidate
        scores = {}
        for action in candidates:
            scores[action] = self._score_action(action, state)

        # Select highest scoring action
        best = max(scores, key=scores.get)
        logger.debug(
            "Decision: %s (score=%.2f) from %s",
            best.value,
            scores[best],
            [a.value for a in candidates],
        )
        return best

    def _score_action(self, action: DecisionAction, state: CognitiveState) -> float:
        """Score an action based on the current state. Higher = better."""
        score = 0.5  # baseline

        if action == DecisionAction.RESPOND:
            # Prefer respond when we have enough knowledge
            if state.knowledge_status == KnowledgeStatus.KNOWN:
                score += 0.4
            elif state.knowledge_status == KnowledgeStatus.UNCERTAIN:
                score += 0.1
            elif state.knowledge_status == KnowledgeStatus.UNKNOWN:
                score -= 0.2
            # Prefer respond for simple tasks
            if state.complexity in (Complexity.TRIVIAL, Complexity.SIMPLE):
                score += 0.2
            # Penalize respond if we haven't verified
            if not state.response_evaluated and state.complexity != Complexity.TRIVIAL:
                score -= 0.1

        elif action == DecisionAction.RECALL:
            # Prefer recall when local knowledge might exist
            if state.local_knowledge:
                score += 0.3
            if state.relevant_memories:
                score += 0.2
            if state.relevant_experiences:
                score += 0.2

        elif action == DecisionAction.SEARCH:
            # Prefer search when knowledge is missing
            if state.knowledge_status == KnowledgeStatus.UNKNOWN:
                score += 0.3
            if state.knowledge_gaps:
                score += 0.2
            # Don't search for trivial things
            if state.complexity == Complexity.TRIVIAL:
                score -= 0.5

        elif action == DecisionAction.DEEP_RESEARCH:
            # Prefer deep research for complex research tasks
            if state.goal_type == GoalType.RESEARCH:
                score += 0.3
            if state.complexity in (Complexity.MODERATE, Complexity.COMPLEX):
                score += 0.2

        elif action == DecisionAction.REASON:
            # Prefer reasoning for complex tasks
            if state.complexity in (Complexity.MODERATE, Complexity.COMPLEX):
                score += 0.3
            if state.contradictions:
                score += 0.2
            if len(state.sub_goals) > 2:
                score += 0.1

        elif action == DecisionAction.ASK_CLARIFICATION:
            # Last resort
            score -= 0.3
            if state.knowledge_status == KnowledgeStatus.UNKNOWN:
                score += 0.1

        elif action == DecisionAction.USE_TOOL:
            # Use tools when specific capabilities needed
            if state.contains_code:
                score += 0.2

        elif action == DecisionAction.REFLECT:
            # Reflect after failures
            if state.error:
                score += 0.3

        elif action == DecisionAction.LEARN:
            # Learn after significant tasks
            if state.complexity in (Complexity.MODERATE, Complexity.COMPLEX):
                score += 0.2

        return score
