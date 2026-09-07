"""CognitiveEngine — central cognitive orchestrator.

Replaces the hardcoded if/elif routing in main.py with a dynamic
cognitive pipeline. This is the "brain" that coordinates all other engines.

Flow:
  INPUT → PERCEIVE → UNDERSTAND → DECIDE → ACT → VERIFY → RESPOND → LEARN

Each step reads from and writes to the CognitiveState. The state is
NEVER exposed to the user — only the final response is.
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Optional

from .state import (
    CognitiveState,
    Complexity,
    DecisionAction,
    GoalType,
    KnowledgeStatus,
)
from .decision import DecisionOrchestrator

if TYPE_CHECKING:
    from genesis_ai.database.db import DatabaseManager

logger = logging.getLogger(__name__)


class CognitiveEngine:
    """Central cognitive orchestrator.

    This engine does NOT generate text. It:
    1. Builds a CognitiveState from the input
    2. Decides what action to take
    3. Coordinates other engines to execute that action
    4. Verifies the result
    5. Triggers learning

    It replaces the hardcoded routing in main.py with dynamic decisions.

    Phase 3: Integrates web research pipeline with:
    - ResearchDecisionEngine (WHEN to research)
    - KnowledgeGapDetector (WHAT is missing)
    - WebResearchEngine (HOW to research)
    - ResponseComposer (HOW to present)
    - FreshnessManager (WHEN to re-verify)
    """

    def __init__(self, db: "DatabaseManager"):
        self.db = db
        self.decision_orchestrator = DecisionOrchestrator()
        self._ensure_cognitive_state_table()
        # Phase 2: Context management
        from .context_manager import ContextManager
        self.context_manager = ContextManager()
        # Phase 3: Research pipeline components
        self._research_decision = None
        self._gap_detector = None
        self._research_engine = None
        self._response_composer = None
        self._freshness_manager = None
        self._init_research_pipeline()

    def _ensure_cognitive_state_table(self):
        """Store cognitive states for debugging and learning."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS cognitive_states (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                duration REAL DEFAULT 0.0
            )
        """)

    def _init_research_pipeline(self):
        """Initialize Phase 3 research pipeline components."""
        try:
            from genesis_ai.research.decision.engine import ResearchDecisionEngine
            self._research_decision = ResearchDecisionEngine(self.db)
        except Exception as e:
            logger.warning(f"Failed to init ResearchDecisionEngine: {e}")

        try:
            from genesis_ai.research.gaps.engine import KnowledgeGapDetector
            self._gap_detector = KnowledgeGapDetector(self.db)
        except Exception as e:
            logger.warning(f"Failed to init KnowledgeGapDetector: {e}")

        try:
            from genesis_ai.research.web.engine import WebResearchEngine
            self._research_engine = WebResearchEngine(self.db)
        except Exception as e:
            logger.warning(f"Failed to init WebResearchEngine: {e}")

        try:
            from genesis_ai.research.response.composer import ResponseComposer
            self._response_composer = ResponseComposer()
        except Exception as e:
            logger.warning(f"Failed to init ResponseComposer: {e}")

        try:
            from genesis_ai.research.freshness.manager import FreshnessManager
            self._freshness_manager = FreshnessManager()
        except Exception as e:
            logger.warning(f"Failed to init FreshnessManager: {e}")

    def perceive(self, state: CognitiveState) -> CognitiveState:
        """Stage 1: PERCEIVE — extract raw signals from input.

        This is the lightest stage. No reasoning, just signal extraction.
        Retrieves ALL learned intent patterns for downstream use.
        """
        msg = state.raw_input.strip()
        state.cleaned_input = msg
        state.word_count = len(msg.split())
        state.detected_language = self._detect_language(msg)

        # Structural signal detection (NOT content-based)
        state.is_question = "?" in msg or any(
            w in msg.lower()
            for w in ["who", "what", "when", "where", "why", "how",
                       "kaun", "kya", "kab", "kahan", "kyun", "kaise"]
        )
        state.is_command = any(
            w in msg.lower()
            for w in ["make", "create", "write", "build", "generate",
                       "banao", "bana", "likho", "fix", "debug"]
        )
        state.is_greeting = state.word_count <= 5 and any(
            re.search(r'\b' + re.escape(w) + r'\b', msg.lower())
            for w in ["hi", "hello", "hey", "namaste", "bye",
                       "kya haal", "kaise ho", "kaise hain", "sup", "yo"]
        )
        state.contains_code = any(
            w in msg.lower()
            for w in ["code", "program", "function", "class", "api",
                       "python", "javascript", "java", "html", "css"]
        )
        state.contains_entities = bool(
            __import__("re").search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", msg)
        )

        # ── LEARNED INTENT PATTERN RETRIEVAL ──
        # Retrieve ALL matching patterns for downstream intent ranking
        import time as _time
        _t0 = _time.time()
        try:
            from genesis_ai.core.learning.retrieval import LearningRetrieval
            lr = LearningRetrieval(self.db)
            lr_result = lr.retrieve(msg, limit=5, include_candidates=False)
            state.learned_intent_patterns = lr_result.intent_patterns or []
            state.learned_knowledge = lr_result.knowledge or []
            state.learned_generalizations = lr_result.generalizations or []
            state.learned_skills = lr_result.skills or []
        except Exception:
            state.learned_intent_patterns = []
        state.learning_retrieval_ms = (_time.time() - _t0) * 1000

        # Check greeting override from learned patterns
        if not state.is_greeting and state.learned_intent_patterns:
            best = state.learned_intent_patterns[0]
            if best.intent in ("greeting", "conversation") and best.confidence >= 0.4:
                state.is_greeting = True

        # ── PHASE 2: CONTEXT RESOLUTION ──
        # Resolve references, detect topic, detect user goal
        try:
            from .context_manager import ContextManager, _ALL_PRONOUNS
            ctx = self.context_manager.get_context(state.user_id)

            # Resolve pronouns/references
            state.resolved_references = self.context_manager.resolve_references(
                state.user_id, msg
            )

            # Detect topic
            detected_topic = self.context_manager.detect_topic(
                state.user_id, msg, state.entities
            )
            if detected_topic and detected_topic != ctx.current_topic:
                state.topic_changed = True
            state.active_topic = detected_topic

            # Detect user goal (before static classification, using context)
            state.user_goal = self.context_manager.detect_user_goal(
                state.user_id, msg, "", state.resolved_references
            )

            # Check if clarification is needed
            state.clarification_needed = self.context_manager.should_ask_clarification(
                state.user_id, msg, 0.5
            )

            # Get relevant context turns
            state.context_relevant_turns = self.context_manager.get_relevant_context(
                state.user_id, msg, max_turns=5
            )
            state.context_relevance_score = (
                sum(t.relevance_score for t in state.context_relevant_turns) /
                max(len(state.context_relevant_turns), 1)
            )

            # Store short-term summary
            state.short_term_summary = self.context_manager.get_short_term_summary(
                state.user_id
            )

            # Detect topic switch
            state.topic_changed = self.context_manager.detect_topic_switch(
                state.user_id, msg
            )

        except Exception:
            state.resolved_references = {}
            state.user_goal = "unknown"
            state.clarification_needed = False

        state.mark_stage("PERCEIVE")
        return state

    def understand(self, state: CognitiveState) -> CognitiveState:
        """Stage 2: UNDERSTAND — classify intent, extract entities, assess complexity.

        Uses UnderstandingEngine for static intent/entity extraction, then
        combines with learned intent patterns for final classification.
        """
        # Import here to avoid circular dependency
        from genesis_ai.core.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine(self.db)
        understanding = engine.understand(state.cleaned_input)

        # Map understanding to cognitive state (static classification)
        state.intent = understanding.intent
        state.domain = understanding.domain
        state.entities = understanding.entities
        state.constraints = understanding.constraints
        state.output_type = understanding.output_type
        state.sub_goals = understanding.sub_tasks

        # Map task_type to GoalType (static)
        task_goal_map = {
            "conversation": GoalType.CONVERSATION,
            "factual": GoalType.FACTUAL,
            "code": GoalType.CODE,
            "creative": GoalType.CREATIVE,
            "analysis": GoalType.RESEARCH,
            "math": GoalType.FACTUAL,
        }
        static_goal = task_goal_map.get(understanding.task_type, GoalType.UNKNOWN)

        # Map complexity
        complexity_map = {
            "simple": Complexity.SIMPLE,
            "moderate": Complexity.MODERATE,
            "complex": Complexity.COMPLEX,
        }
        state.complexity = complexity_map.get(understanding.complexity, Complexity.SIMPLE)

        # ── LEARNED INTENT RANKING ──
        # Combine static evidence with learned evidence from intent patterns
        learned_goal = None
        learned_confidence = 0.0
        learned_source = "static"
        best_structure_match = 0.0

        if state.learned_intent_patterns:
            # Map learned intent strings to GoalType
            intent_goal_map = {
                "greeting": GoalType.CONVERSATION,
                "conversation": GoalType.CONVERSATION,
                "casual": GoalType.CONVERSATION,
                "factual": GoalType.FACTUAL,
                "informational": GoalType.FACTUAL,
                "task": GoalType.FACTUAL,
                "technical": GoalType.FACTUAL,
                "code": GoalType.CODE,
                "creative": GoalType.CREATIVE,
                "research": GoalType.RESEARCH,
            }

            # MULTI-DIMENSIONAL EVIDENCE SCORING
            # Find the best learned pattern considering:
            # 1. Confidence (how reliable is this pattern)
            # 2. Relevance (how much topic overlap)
            # 3. Structure match (does the query structure match the intent)
            for pattern in state.learned_intent_patterns:
                mapped = intent_goal_map.get(pattern.intent)
                if not mapped:
                    continue
                # Calibrate confidence by structure match
                # A pattern with high confidence but structure mismatch gets penalized
                structure = getattr(pattern, 'structure_match', 1.0)
                calibrated = pattern.confidence * (0.3 + 0.7 * structure)
                if calibrated > learned_confidence:
                    learned_goal = mapped
                    learned_confidence = calibrated
                    learned_source = "learned"
                    best_structure_match = structure

            # Decision logic: multi-dimensional evidence competition
            if learned_goal:
                # Compute static evidence strength
                static_strength = 0.5  # base static confidence
                if static_goal in (GoalType.FACTUAL, GoalType.CODE):
                    static_strength = 0.7  # strong static for clear patterns
                elif static_goal == GoalType.CREATIVE:
                    static_strength = 0.6
                elif static_goal == GoalType.CONVERSATION:
                    static_strength = 0.8  # greetings are usually clear
                elif static_goal == GoalType.UNKNOWN:
                    static_strength = 0.0

                # Learned overrides static ONLY when:
                # 1. Learned evidence is genuinely strong (calibrated >= 0.6)
                # 2. Structure match is decent (>= 0.4)
                # 3. Static is not strongly contradictory
                learned_wins = (
                    learned_confidence >= 0.6
                    and best_structure_match >= 0.4
                    and not (static_strength >= 0.8 and learned_goal != static_goal)
                )

                if learned_wins and learned_goal != static_goal:
                    state.goal_type = learned_goal
                    state.learned_intent_source = "learned_override"
                    state.learned_intent_confidence = learned_confidence
                elif learned_goal == static_goal:
                    # Agree: boost confidence
                    state.goal_type = static_goal
                    state.learned_intent_source = "learned_confirm"
                    state.learned_intent_confidence = max(learned_confidence, static_strength)
                else:
                    # Static wins
                    state.goal_type = static_goal
                    state.learned_intent_source = "static"
            else:
                state.goal_type = static_goal
                state.learned_intent_source = "static"
        else:
            state.goal_type = static_goal
            state.learned_intent_source = "static"

        # Override: greetings are always trivial
        if state.is_greeting or state.goal_type == GoalType.CONVERSATION:
            state.complexity = Complexity.TRIVIAL
            state.goal_type = GoalType.CONVERSATION

        # Override: identity questions
        if self._is_identity_question(state.raw_input):
            state.goal_type = GoalType.IDENTITY
            state.complexity = Complexity.TRIVIAL

        # ── PHASE 2: CONTEXTUAL INTENT OVERRIDE ──
        # Use conversation context to refine intent when static/learned are ambiguous
        try:
            state.goal_type = self._contextual_intent_override(state)
        except Exception:
            pass

        state.mark_stage("UNDERSTAND")
        return state

    def assess_knowledge(self, state: CognitiveState) -> CognitiveState:
        """Stage 3: ASSESS_KNOWLEDGE — determine what is known vs unknown.

        Checks local memory, knowledge base, experience, AND learned knowledge
        to determine the knowledge status for this specific query.
        """
        # Check local knowledge
        from genesis_ai.knowledge.retrieval.engine import KnowledgeRetrieval
        retrieval = KnowledgeRetrieval(self.db)
        state.local_knowledge = retrieval.retrieve(
            state.cleaned_input,
            {"topic": state.domain},
        ) or []

        # Check memory for relevant past interactions
        from genesis_ai.core.memory.engine import MemoryEngine
        memory = MemoryEngine(self.db)
        state.relevant_memories = memory.search_memories(
            state.cleaned_input, limit=5
        )

        # Check experience for similar past tasks
        from genesis_ai.core.experience.engine import ExperienceEngine
        exp_engine = ExperienceEngine(self.db)
        state.relevant_experiences = exp_engine.find_similar_experiences(
            state.cleaned_input, limit=5
        )

        # ── LEARNING → INFERENCE BRIDGE ──
        from genesis_ai.core.learning.retrieval import LearningRetrieval
        lr_start = time.time()
        learning_retrieval = LearningRetrieval(self.db)
        lr_result = learning_retrieval.retrieve(
            state.cleaned_input,
            context=state.conversation_history,
            limit=5,
            include_candidates=False,
        )
        state.learned_knowledge = lr_result.knowledge
        state.learned_generalizations = lr_result.generalizations
        state.learned_skills = lr_result.skills
        state.learned_intent_patterns = lr_result.intent_patterns
        state.learning_retrieval_ms = lr_result.retrieval_time_ms

        # Determine knowledge status — include learned knowledge
        if state.local_knowledge or state.learned_knowledge:
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_memories:
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_experiences:
            state.knowledge_status = KnowledgeStatus.KNOWN
        else:
            state.knowledge_status = KnowledgeStatus.UNKNOWN

        # Check if knowledge might be outdated
        if state.knowledge_status == KnowledgeStatus.KNOWN:
            # If oldest knowledge is > 24h old and topic is time-sensitive
            # (structural check, not content-specific)
            if self._is_time_sensitive(state):
                state.knowledge_status = KnowledgeStatus.OUTDATED

        # ── PHASE 3: KNOWLEDGE GAP DETECTION ──
        if self._gap_detector:
            try:
                gap_analysis = self._gap_detector.analyze(
                    question=state.cleaned_input,
                    local_knowledge=state.local_knowledge,
                    learned_knowledge=state.learned_knowledge,
                    context={"topic": state.domain, "goal": state.goal_type.value},
                    knowledge_status=state.knowledge_status.value,
                    knowledge_confidence=state.confidence_score,
                )
                state.knowledge_gaps = [g.missing_information for g in gap_analysis.gaps]
                if gap_analysis.primary_gap:
                    state.knowledge_status = KnowledgeStatus.UNKNOWN
            except Exception as e:
                logger.debug(f"Gap detection failed: {e}")

        state.mark_stage("ASSESS_KNOWLEDGE")
        return state

    def decide(self, state: CognitiveState) -> CognitiveState:
        """Stage 4: DECIDE — choose the best action.

        Delegates to DecisionOrchestrator for dynamic decision-making.
        Phase 3: Uses ResearchDecisionEngine for research decisions.
        """
        # Phase 3: Research decision — but NOT for creative/code tasks
        if (self._research_decision
            and state.knowledge_status in (
                KnowledgeStatus.UNKNOWN, KnowledgeStatus.OUTDATED, KnowledgeStatus.CONTRADICTED
            )
            and state.goal_type not in (GoalType.CREATIVE, GoalType.CODE, GoalType.CONVERSATION)):
            try:
                research_decision = self._research_decision.decide(
                    question=state.cleaned_input,
                    knowledge_status=state.knowledge_status.value,
                    knowledge_confidence=state.confidence_score,
                    user_goal=state.goal_type.value,
                    context={"topic": state.domain},
                    detected_language=state.detected_language,
                    user_id=state.user_id,
                )
                state.research_needed = research_decision.should_research
                if research_decision.should_research:
                    state.selected_action = DecisionAction.DEEP_RESEARCH
                    state.mark_stage("DECISION_MADE")
                    return state
            except Exception as e:
                logger.debug(f"Research decision failed: {e}")

        state = self.decision_orchestrator.decide(state)
        state.mark_stage("DECISION_MADE")
        return state

    def act(self, state: CognitiveState) -> CognitiveState:
        """Stage 5: ACT — execute the decided action.

        Routes to the appropriate handler based on the decision,
        NOT based on hardcoded question patterns.
        """
        action = state.selected_action

        if action == DecisionAction.RESPOND:
            state = self._act_respond(state)
        elif action == DecisionAction.RECALL:
            state = self._act_recall(state)
        elif action == DecisionAction.SEARCH:
            state = self._act_search(state)
        elif action == DecisionAction.DEEP_RESEARCH:
            state = self._act_deep_research(state)
        elif action == DecisionAction.REASON:
            state = self._act_reason(state)
        elif action == DecisionAction.ASK_CLARIFICATION:
            state = self._act_clarify(state)
        elif action == DecisionAction.USE_TOOL:
            state = self._act_tool(state)
        else:
            state = self._act_respond(state)

        state.mark_stage("ACT")
        return state

    def verify(self, state: CognitiveState) -> CognitiveState:
        """Stage 6: VERIFY — check if response is good enough.

        Uses CriticEngine to evaluate the response quality.
        If issues found, triggers revision.
        """
        if not state.response_text:
            state.needs_revision = True
            state.evaluation_issues.append("No response generated")
            return state

        # Evaluate response quality
        from genesis_ai.core.critic.engine import CriticEngine
        critic = CriticEngine(self.db)

        # Build research context for critic
        research_ctx = [
            {"text": e.get("claim", ""), "source_name": e.get("source", ""),
             "url": e.get("url", "")}
            for e in state.evidence[:5]
        ]

        critique = critic.critique(
            answer=state.response_text,
            question=state.raw_input,
            research=research_ctx,
            understanding={
                "intent": state.intent,
                "requirements": state.constraints,
            },
        )

        state.response_confidence = critique.score / 10.0  # normalize to 0-1

        # Check for issues
        if critique.score < 50:
            state.needs_revision = True
            state.evaluation_issues.extend(
                [str(issue) for issue in critique.issues[:3]]
            )

        # Check for copied research text
        if self._has_raw_research_text(state):
            state.needs_revision = True
            state.evaluation_issues.append("Response contains raw research text")

        state.mark_stage("VERIFY")
        return state

    def learn(self, state: CognitiveState) -> CognitiveState:
        """Stage 7: LEARN — extract experience and update knowledge.

        Records the task outcome, extracts lessons, and triggers
        generalization for future reuse.
        """
        if state.complexity == Complexity.TRIVIAL:
            # Don't learn from trivial interactions
            state.mark_stage("LEARN")
            return state

        # Build experience for learning pipeline
        from genesis_ai.learning.experience_memory import Experience
        from genesis_ai.learning.pipeline import LearningPipeline

        result = "success" if not state.needs_revision else "partial"
        if state.error:
            result = "failure"

        experience = Experience(
            task=state.raw_input[:200],
            goal=state.intent,
            context={
                "goal_type": state.goal_type.value,
                "complexity": state.complexity.value,
                "domain": state.domain,
                "entities": state.entities,
            },
            observations=state.stages_completed,
            actions=[state.selected_action.value],
            tools_used=[],
            errors=[state.error] if state.error else [],
            attempts=[],
            result={"response": state.response_text[:200], "outcome": result},
            success=not state.needs_revision and not state.error,
            evidence=state.evidence[:5],
            reflection=state.raw_input[:100],
            metadata={"user_id": state.user_id, "session_id": state.session_id},
        )

        # Process through learning pipeline
        pipeline = LearningPipeline(self.db)
        learning_result = pipeline.process_experience(experience)

        # Also record in legacy experience engine for backward compatibility
        from genesis_ai.core.experience.engine import ExperienceEngine, ExperienceRecord
        exp_engine = ExperienceEngine(self.db)
        legacy_exp = ExperienceRecord(
            task_id=state.session_id,
            task_description=state.raw_input[:200],
            approach=state.selected_action.value,
            knowledge_used=[m.get("content", "")[:100] for m in state.relevant_memories[:3]],
            research_used=state.sources_used,
            errors=[state.error] if state.error else [],
            solution_summary=state.response_text[:200],
            result=result,
            lessons=learning_result.lessons_learned,
            duration=time.time() - state.start_time,
        )
        exp_engine.create_experience(legacy_exp)

        state.experience_recorded = True
        state.lessons_learned = learning_result.lessons_learned
        state.generalizations = learning_result.generalizations
        state.skills_created = [s.get("name", "") for s in learning_result.skills_created]

        # Store in memory (only if useful)
        if self._should_store_in_memory(state):
            from genesis_ai.core.memory.engine import MemoryEngine
            memory = MemoryEngine(self.db)
            memory.store_memory(
                f"User: {state.raw_input[:200]}",
                "SHORT_TERM",
                {"user_id": state.user_id, "intent": state.msg_type, "role": "user"},
            )
            memory.store_memory(
                f"Assistant: {state.response_text[:200]}",
                "SHORT_TERM",
                {"user_id": state.user_id, "intent": state.msg_type, "role": "assistant"},
            )

        state.mark_stage("LEARN")
        return state

    def run_full_pipeline(self, state: CognitiveState) -> CognitiveState:
        """Run the complete cognitive pipeline.

        This is the main entry point that replaces the hardcoded routing
        in main.py. Each stage is optional based on complexity.
        """
        # Stage 1: PERCEIVE (always)
        state = self.perceive(state)

        # Progressive complexity: skip heavy stages for trivial inputs
        if state.complexity == Complexity.TRIVIAL:
            state = self.understand(state)
            state = self.decide(state)
            state = self.act(state)
            # Record outcome for feedback loop
            self._record_inference_outcome(state, "success")
            state.total_duration = time.time() - state.start_time
            return state

        # Stage 2: UNDERSTAND
        state = self.understand(state)

        # Stage 3: ASSESS KNOWLEDGE
        state = self.assess_knowledge(state)

        # Stage 4: DECIDE
        state = self.decide(state)

        # Stage 5: ACT
        state = self.act(state)

        # Stage 6: VERIFY (skip for simple tasks)
        if state.complexity in (Complexity.MODERATE, Complexity.COMPLEX):
            state = self.verify(state)

            # Revision loop (max 1 revision)
            if state.needs_revision and state.response_text:
                state.needs_revision = False
                state.evaluation_issues.clear()
                state = self.act(state)  # try again with different approach
                state = self.verify(state)

        # Stage 7: LEARN (always for non-trivial)
        state = self.learn(state)

        # Record outcome for feedback loop
        outcome = "success" if not state.needs_revision and not state.error else "failure"
        self._record_inference_outcome(state, outcome)

        state.total_duration = time.time() - state.start_time
        return state

    # ── Action Handlers ────────────────────────────────────────────────

    def _act_respond(self, state: CognitiveState) -> CognitiveState:
        """Generate a response based on current knowledge, including learned knowledge."""
        if state.response_text:
            return state  # already have a response

        # For conversation/casual: use conversation engine
        if state.goal_type == GoalType.CONVERSATION:
            from genesis_ai.core.ai_responder import get_casual_response
            state.response_text = get_casual_response(
                state.raw_input, state.detected_language, state.conversation_history
            )
            state.msg_type = "CASUAL"
            state.confidence_score = 1.0
            return state

        # For identity: use identity response
        if state.goal_type == GoalType.IDENTITY:
            state.response_text = self._identity_response(state.detected_language)
            state.msg_type = "IDENTITY"
            state.confidence_score = 1.0
            return state

        # For code: try local generation
        if state.goal_type == GoalType.CODE:
            from genesis_ai.core.code.generator import CodeGenerator
            gen = CodeGenerator()
            code = gen.generate(state.raw_input)
            if code:
                lang_name = state.entities.get("languages", ["python"])[0]
                topic = state.raw_input.title()
                state.response_text = f"Here is the code for {topic}:\n\n```\n{code}\n```"
                state.msg_type = "CODE"
                state.confidence_score = 0.9
                return state
            # If no code generated, try learned knowledge
            if state.learned_knowledge:
                state.response_text = self._synthesize_from_learned_knowledge(state)
                if state.response_text:
                    state.msg_type = "CODE"
                    state.confidence_score = 0.85
                    return state

        # For creative/suggestion: generate a creative response
        if state.goal_type == GoalType.CREATIVE:
            state.response_text = self._creative_response(state)
            state.msg_type = "CREATIVE"
            state.confidence_score = 0.85
            return state

        # ── LEARNED KNOWLEDGE: Synthesize from learned facts ──
        if state.learned_knowledge:
            state.response_text = self._synthesize_from_learned_knowledge(state)
            if state.response_text:
                state.msg_type = "FACTUAL"
                state.confidence_score = 0.85
                return state

        # ── LEARNED SKILLS: Execute learned procedure ──
        if state.learned_skills and state.goal_type in (GoalType.CODE, GoalType.RESEARCH):
            state.response_text = self._synthesize_from_learned_skills(state)
            if state.response_text:
                state.msg_type = state.goal_type.value.upper()
                state.confidence_score = 0.8
                return state

        # For factual/research with known knowledge: synthesize
        if state.knowledge_status == KnowledgeStatus.KNOWN and state.local_knowledge:
            state.response_text = self._synthesize_from_knowledge(state)
            state.msg_type = "FACTUAL"
            return state

        # Default: generate from evidence if available
        if state.evidence:
            state.response_text = self._synthesize_from_evidence(state)
            state.msg_type = "FACTUAL"
            return state

        # Fallback
        state.response_text = self._fallback_response(state)
        return state

    def _creative_response(self, state: CognitiveState) -> str:
        """Generate a creative/suggestion response via fallback chain.

        Chain: learned skills → learned knowledge → web research → graceful fallback.
        No hardcoded domain content.
        """
        # STEP 1: Check learned skills for creative response guidance
        if hasattr(state, 'learned_skills') and state.learned_skills:
            for skill in state.learned_skills:
                procedure = getattr(skill, 'procedure', [])
                if procedure:
                    # Use skill procedure to generate response
                    steps_text = " → ".join(
                        s if isinstance(s, str) else s.get("action", str(s))
                        for s in procedure[:5]
                    )
                    return steps_text

        # STEP 2: Check learned knowledge for suggestion-related content
        if state.learned_knowledge:
            for k in state.learned_knowledge:
                claim = str(getattr(k, "claim", "") or "")
                if claim and len(claim) > 20:
                    return claim

        # STEP 3: Attempt web research for the creative topic
        if self._research_engine:
            try:
                research_result = self._research_engine.research(
                    question=state.raw_input,
                    user_goal="creative_response",
                    freshness="stable",
                    verification_level="basic",
                )
                if research_result.success and research_result.verified_knowledge:
                    best = max(research_result.verified_knowledge, key=lambda k: k.confidence)
                    return best.claim
            except Exception:
                pass

        # STEP 4: Graceful fallback — no hardcoded content
        return ("I'd be happy to help with that! "
                "Tell me more about what you're looking for — "
                "the topic, your preferences, and I'll try to assist.")

    def _act_recall(self, state: CognitiveState) -> CognitiveState:
        """Recall from local knowledge, memory, AND learned knowledge."""
        # Already assessed in assess_knowledge
        if state.local_knowledge:
            state.response_text = self._synthesize_from_knowledge(state)
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.learned_knowledge:
            state.response_text = self._synthesize_from_learned_knowledge(state)
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_memories:
            state.response_text = self._synthesize_from_memories(state)
            state.knowledge_status = KnowledgeStatus.KNOWN
        elif state.relevant_experiences:
            state.response_text = self._synthesize_from_experiences(state)
            state.knowledge_status = KnowledgeStatus.KNOWN
        else:
            # Nothing found locally — need to search
            state.selected_action = DecisionAction.SEARCH
            state = self._act_search(state)
        return state

    def _act_search(self, state: CognitiveState) -> CognitiveState:
        """Search the web for information.
        Phase 3: Uses WebResearchEngine for comprehensive research.
        """
        # Phase 3: Use WebResearchEngine if available
        if self._research_engine:
            try:
                research_result = self._research_engine.research(
                    question=state.cleaned_input,
                    knowledge_gap=state.knowledge_gaps[0] if state.knowledge_gaps else "",
                    user_goal=state.goal_type.value,
                    freshness=self._freshness_manager.determine_freshness_requirement(
                        state.cleaned_input
                    ) if self._freshness_manager else "stable",
                    verification_level="standard",
                )

                if research_result.success:
                    state.sources_used = [
                        s.publisher or s.domain for s in research_result.sources[:5]
                    ]
                    state.evidence = [
                        {
                            "claim": c.statement,
                            "source": next(
                                (s.publisher for s in research_result.sources
                                 if s.source_id == c.source_id), ""
                            ),
                            "url": next(
                                (s.url for s in research_result.sources
                                 if s.source_id == c.source_id), ""
                            ),
                            "title": next(
                                (s.title for s in research_result.sources
                                 if s.source_id == c.source_id), ""
                            ),
                        }
                        for c in research_result.claims[:5]
                    ]
                    state.knowledge_status = KnowledgeStatus.UNVERIFIED
                    state.confidence_score = research_result.confidence

                    # Use ResponseComposer for synthesis
                    if self._response_composer:
                        state.response_text = self._response_composer.compose(
                            question=state.cleaned_input,
                            evidence=state.evidence,
                            language=state.detected_language,
                            detail_level="normal",
                            contradictions=research_result.contradictions,
                            confidence=research_result.confidence,
                        )
                    else:
                        state.response_text = self._fallback_response(state)

                    # Record research for history
                    if self._research_decision:
                        self._research_decision.record_research(
                            state.user_id, state.cleaned_input[:100]
                        )

                    return state
            except Exception as e:
                logger.warning(f"Phase 3 research failed, falling back: {e}")

        # Fallback: Legacy search
        from genesis_ai.research.search.engine import WebSearchEngine
        from genesis_ai.core.ai_responder import build_search_queries, synthesize_response

        search = WebSearchEngine()
        queries = build_search_queries(state.raw_input, state.goal_type.value.upper())
        state.research_queries = queries

        all_results = []
        for q in queries[:3]:
            results = search.search(q, max_results=3)
            if results:
                all_results.extend(results)

        if all_results:
            state.sources_used = [
                r.source_name for r in all_results if r.source_name
            ]
            state.evidence = [
                {
                    "claim": r.snippet,
                    "source": r.source_name,
                    "url": r.url,
                    "title": r.title,
                }
                for r in all_results if r.snippet
            ]
            state.knowledge_status = KnowledgeStatus.UNVERIFIED
            state.response_text = synthesize_response(
                state.raw_input,
                all_results,
                state.detected_language,
                state.goal_type.value.upper(),
            )
        else:
            state.knowledge_status = KnowledgeStatus.UNKNOWN
            state.response_text = self._fallback_response(state)

        return state

    def _act_deep_research(self, state: CognitiveState) -> CognitiveState:
        """Deep research with multi-source verification.
        Phase 3: Uses WebResearchEngine with rigorous verification.
        """
        # Phase 3: Use WebResearchEngine with rigorous verification
        if self._research_engine:
            try:
                research_result = self._research_engine.research(
                    question=state.cleaned_input,
                    knowledge_gap=state.knowledge_gaps[0] if state.knowledge_gaps else "",
                    user_goal=state.goal_type.value,
                    freshness=self._freshness_manager.determine_freshness_requirement(
                        state.cleaned_input
                    ) if self._freshness_manager else "stable",
                    verification_level="rigorous",
                )

                if research_result.success:
                    state.sources_used = [
                        s.publisher or s.domain for s in research_result.sources[:7]
                    ]
                    state.evidence = [
                        {
                            "claim": c.statement,
                            "source": next(
                                (s.publisher for s in research_result.sources
                                 if s.source_id == c.source_id), ""
                            ),
                            "url": next(
                                (s.url for s in research_result.sources
                                 if s.source_id == c.source_id), ""
                            ),
                            "title": next(
                                (s.title for s in research_result.sources
                                 if s.source_id == c.source_id), ""
                            ),
                            "confidence": c.confidence,
                            "status": c.status,
                        }
                        for c in research_result.claims[:7]
                    ]
                    state.knowledge_status = KnowledgeStatus.UNVERIFIED
                    state.confidence_score = research_result.confidence
                    state.contradictions = research_result.contradictions

                    # Use ResponseComposer for synthesis
                    if self._response_composer:
                        state.response_text = self._response_composer.compose(
                            question=state.cleaned_input,
                            evidence=state.evidence,
                            language=state.detected_language,
                            detail_level="detailed",
                            contradictions=research_result.contradictions,
                            confidence=research_result.confidence,
                        )
                    else:
                        state.response_text = self._fallback_response(state)

                    # If composer produced empty/insufficient response, fall back
                    if not state.response_text or len(state.response_text) < 30:
                        logger.info("ResponseComposer produced short response, falling back to legacy search")
                        state = self._act_search(state)
                        if not state.response_text or len(state.response_text) < 30:
                            state.response_text = self._fallback_response(state)

                    # Record research for history
                    if self._research_decision:
                        self._research_decision.record_research(
                            state.user_id, state.cleaned_input[:100]
                        )

                    return state
            except Exception as e:
                logger.warning(f"Phase 3 deep research failed, falling back: {e}")

        # Fallback: Legacy deep research
        state = self._act_search(state)

        # If we got evidence, try to verify
        if state.evidence and len(state.evidence) > 1:
            from genesis_ai.core.contradiction.engine import ContradictionEngine
            from genesis_ai.core.comparison.engine import ComparisonEngine

            claims = [
                {"text": e["claim"], "source_name": e.get("source", "")}
                for e in state.evidence
            ]

            # Check contradictions
            contra = ContradictionEngine()
            contra_result = contra.detect(claims)
            state.contradictions = [
                {"severity": c.severity, "resolution": c.resolution}
                for c in (contra_result.contradictions if contra_result else [])
            ]

            # Compare sources
            comp = ComparisonEngine()
            comp_result = comp.compare(state.evidence)
            state.comparison_result = {
                "best": comp_result.best_approach if comp_result else None,
                "approaches": len(comp_result.approaches) if comp_result else 0,
            }

        return state

    def _act_reason(self, state: CognitiveState) -> CognitiveState:
        """Apply reasoning to the problem."""
        from genesis_ai.core.reasoning.engine import ReasoningEngine
        reasoning = ReasoningEngine(self.db)

        result = reasoning.reason(
            state.raw_input,
            context={"constraints": state.constraints},
        )
        state.reasoning_result = {
            "reasoning": "\n".join(result.steps) if result else "",
            "conclusions": [c.get("text", str(c)) if isinstance(c, dict) else str(c) for c in (result.conclusions if result else [])],
            "confidence": result.confidence if result else 0.0,
        }

        # If reasoning produced a conclusion, use it
        if result and result.conclusions:
            state.response_text = "\n".join(result.conclusions)
            state.knowledge_status = KnowledgeStatus.KNOWN

        return state

    def _act_clarify(self, state: CognitiveState) -> CognitiveState:
        """Ask for clarification when information is insufficient."""
        lang = state.detected_language
        clarify_msgs = {
            "hindi": "मुझे आपके प्रश्न को समझने के लिए थोड़ी और जानकारी चाहिए। कृपया और विस्तार से बताइए।",
            "hinglish": "Mujhe thoda aur detail chahiye. Kya aap aur bata sakte hain?",
            "english": "I need a bit more information to help you. Could you provide more details?",
        }
        state.response_text = clarify_msgs.get(lang, clarify_msgs["english"])
        state.msg_type = "CLARIFICATION"
        state.confidence_score = 0.3
        return state

    def _act_tool(self, state: CognitiveState) -> CognitiveState:
        """Use a tool (calculator, code execution, etc.)."""
        # Delegate to tool engine
        return state

    # ── Helper Methods ────────────────────────────────────────────────

    def _detect_language(self, msg: str) -> str:
        """Detect language using structural patterns."""
        import re
        hindi_chars = len(re.findall(r"[\u0900-\u097F]", msg))
        total_chars = len(re.findall(r"\w", msg))
        if total_chars == 0:
            return "english"
        hindi_ratio = hindi_chars / total_chars
        if hindi_ratio > 0.5:
            return "hindi"
        elif hindi_ratio > 0.2:
            return "hinglish"
        return "english"

    def _is_identity_question(self, msg: str) -> bool:
        """Detect identity questions using structural patterns."""
        msg_lower = msg.lower().strip()
        self_refs = ["genesis", "yourself", "tum", "aap", "tera", "tumhara",
                      "apna", "your", "you"]
        id_q_words = ["who", "what", "kaun", "kya", "name", "naam"]
        has_self = any(w in msg_lower for w in self_refs)
        has_q = any(w in msg_lower for w in id_q_words)
        return has_self and has_q

    def _contextual_intent_override(self, state: CognitiveState) -> GoalType:
        """Phase 2: Use conversation context to refine intent classification.

        Handles cases where:
        - Short follow-ups inherit topic from context
        - Pronouns change meaning based on context
        - User corrections override previous intent
        - Goal transitions happen mid-conversation
        """
        from .context_manager import UserGoal, _ALL_PRONOUNS, _CORRECTION_MARKERS
        import re

        msg = state.raw_input.lower().strip()
        words = set(re.findall(r'\b\w+\b', msg))
        ctx_summary = state.short_term_summary
        current_goal = state.user_goal
        prev_goal = ctx_summary.get("active_goal", "unknown")
        prev_topic = ctx_summary.get("current_topic", "")
        prev_request = ctx_summary.get("previous_request", "")

        # ── 1. Correction handling ──
        # If user is correcting, override goal to CORRECTION
        for marker in _CORRECTION_MARKERS:
            if marker in msg:
                state.correction_pending = True
                # Extract new topic from correction
                import re as _re
                correction_patterns = [
                    r'i meant\s+(.+?)(?:\.|$)',
                    r'maine kaha\s+(.+?)(?:\.|$)',
                    r'not .+?,?\s*(.+?)(?:\.|$)',
                    r'no,?\s*(.+?)(?:\.|$)',
                    r'actually\s+(.+?)(?:\.|$)',
                ]
                for cp in correction_patterns:
                    cm = _re.search(cp, msg)
                    if cm:
                        new_topic = cm.group(1).strip()
                        new_topic = _re.sub(r'\b(a|an|the|ek|ye|woh)\b', '', new_topic).strip()
                        if 2 < len(new_topic) < 40:
                            state.active_topic = new_topic
                            break
                # Determine what the correction is about
                if prev_goal == UserGoal.CREATION:
                    return GoalType.CREATIVE
                elif prev_goal == UserGoal.CODING:
                    return GoalType.CODE
                elif prev_goal in (UserGoal.INFORMATION, UserGoal.EXPLANATION):
                    return GoalType.FACTUAL
                return state.goal_type

        # ── 2. Pronoun resolution → context-dependent intent ──
        has_pronoun = any(w in _ALL_PRONOUNS for w in words)
        if has_pronoun and prev_goal != UserGoal.UNKNOWN:
            # "isko fix karo" with coding context → CODE
            if any(w in msg for w in ["fix", "debug", "repair", "theek", "solve"]):
                if prev_goal in (UserGoal.CODING, UserGoal.TROUBLESHOOTING):
                    return GoalType.CODE
            # "isko explain karo" → EXPLAIN/FACTUAL
            if any(w in msg for w in ["explain", "samjhao", "batao"]):
                return GoalType.FACTUAL
            # "isko change karo" / "modify" → depends on previous context
            if any(w in msg for w in ["change", "modify", "update", "badlo"]):
                if prev_goal == UserGoal.CREATION:
                    return GoalType.CREATIVE
                elif prev_goal == UserGoal.CODING:
                    return GoalType.CODE
                return state.goal_type
            # Generic pronoun with active goal → continue that goal
            if state.goal_type == GoalType.UNKNOWN:
                goal_type_map = {
                    UserGoal.CREATION: GoalType.CREATIVE,
                    UserGoal.CODING: GoalType.CODE,
                    UserGoal.INFORMATION: GoalType.FACTUAL,
                    UserGoal.EXPLANATION: GoalType.FACTUAL,
                    UserGoal.TROUBLESHOOTING: GoalType.CODE,
                    UserGoal.RESEARCH: GoalType.RESEARCH,
                }
                mapped = goal_type_map.get(prev_goal)
                if mapped:
                    return mapped

        # ── 3. Short follow-ups inherit topic ──
        # "example do", "aur batao", "is there more" → continue previous goal
        if state.word_count <= 5 and prev_goal != UserGoal.UNKNOWN:
            continuation_words = [
                "example", "aur", "more", "bhi", "then", "uske baad",
                "also", "plus", "continue", "aage", "next", "next step",
                "isko", "usko", "ye", "woh", "this", "that",
            ]
            if any(w in msg for w in continuation_words):
                goal_type_map = {
                    UserGoal.CREATION: GoalType.CREATIVE,
                    UserGoal.CODING: GoalType.CODE,
                    UserGoal.INFORMATION: GoalType.FACTUAL,
                    UserGoal.EXPLANATION: GoalType.FACTUAL,
                    UserGoal.TROUBLESHOOTING: GoalType.CODE,
                    UserGoal.RESEARCH: GoalType.RESEARCH,
                    UserGoal.LEARNING: GoalType.FACTUAL,
                }
                mapped = goal_type_map.get(prev_goal)
                if mapped:
                    return mapped

        # ── 4. Topic continuation for questions ──
        # "iska version kya hai?" with Python topic → FACTUAL about Python
        if state.is_question and prev_topic and prev_topic != "general":
            if has_pronoun or state.word_count <= 6:
                return GoalType.FACTUAL

        # ── 5. Goal transitions ──
        # Information → Explanation → Example → Code
        if current_goal == UserGoal.EXPLANATION and prev_goal == UserGoal.INFORMATION:
            return GoalType.FACTUAL
        if current_goal == UserGoal.CODING and prev_goal in (UserGoal.LEARNING, UserGoal.EXPLANATION):
            return GoalType.CODE
        if current_goal == UserGoal.CREATION and prev_goal in (UserGoal.INFORMATION, UserGoal.EXPLANATION):
            return GoalType.CREATIVE

        # Default: return current goal_type (no override)
        return state.goal_type

    def _is_time_sensitive(self, state: CognitiveState) -> bool:
        """Check if the topic is time-sensitive (structural, not content-based)."""
        time_words = ["latest", "current", "today", "now", "recent",
                      "2024", "2025", "2026", "aajkal", "abhi"]
        return any(w in state.raw_input.lower() for w in time_words)

    def _has_raw_research_text(self, state: CognitiveState) -> bool:
        """Check if response contains raw research text (not synthesized)."""
        if not state.evidence or not state.response_text:
            return False
        # Check if any evidence snippet appears verbatim in response
        for e in state.evidence:
            snippet = e.get("claim", "")
            if snippet and len(snippet) > 50 and snippet in state.response_text:
                return True
        return False

    def _synthesize_from_knowledge(self, state: CognitiveState) -> str:
        """Synthesize a response from local knowledge."""
        from genesis_ai.core.ai_responder import synthesize_response
        # Convert local knowledge to result-like objects
        results = []
        for k in state.local_knowledge[:3]:
            results.append(type("R", (), {
                "snippet": k.get("content", k.get("claim", "")),
                "source_name": k.get("source", "local"),
                "url": k.get("url", ""),
                "title": k.get("topic", ""),
            })())
        if results:
            return synthesize_response(
                state.raw_input, results, state.detected_language,
                state.goal_type.value.upper(),
            )
        return self._fallback_response(state)

    def _synthesize_from_memories(self, state: CognitiveState) -> str:
        """Synthesize a response from relevant memories."""
        if state.relevant_memories:
            return state.relevant_memories[0].get("content", "")
        return self._fallback_response(state)

    def _synthesize_from_experiences(self, state: CognitiveState) -> str:
        """Synthesize a response from relevant experiences."""
        if state.relevant_experiences:
            exp = state.relevant_experiences[0]
            return exp.get("solution_summary", exp.get("task_description", ""))
        return self._fallback_response(state)

    def _synthesize_from_evidence(self, state: CognitiveState) -> str:
        """Synthesize a response from web evidence."""
        from genesis_ai.core.ai_responder import synthesize_response
        results = []
        for e in state.evidence[:5]:
            results.append(type("R", (), {
                "snippet": e.get("claim", ""),
                "source_name": e.get("source", ""),
                "url": e.get("url", ""),
                "title": e.get("title", ""),
            })())
        if results:
            return synthesize_response(
                state.raw_input, results, state.detected_language,
                state.goal_type.value.upper(),
            )
        return self._fallback_response(state)

    def _fallback_response(self, state: CognitiveState) -> str:
        """Generate a fallback response when nothing else works."""
        lang = state.detected_language
        msgs = {
            "hindi": "मुझे इस विषय पर पर्याप्त जानकारी नहीं है। कृपया और विस्तार से बताइए।",
            "hinglish": "Mujhe is topic pe enough info nahi hai. Thoda aur batao?",
            "english": "I don't have enough information on this topic. Could you provide more details?",
        }
        return msgs.get(lang, msgs["english"])

    def _identity_response(self, lang: str) -> str:
        """Generate identity response."""
        msgs = {
            "hindi": "मैं **Genesis AI** हूँ — आपका personal AI assistant! मैं research, coding, aur conversation में help कर सकता हूँ।",
            "hinglish": "Main **Genesis AI** hoon — aapka personal AI assistant! Research, coding, aur conversation mein help kar sakta hoon.",
            "english": "I'm **Genesis AI** — your personal AI assistant! I can help with research, coding, and conversation.",
        }
        return msgs.get(lang, msgs["english"])

    def _extract_generalizations(self, state: CognitiveState) -> list[str]:
        """Extract generalizable lessons from this experience."""
        generalizations = []
        if state.needs_revision:
            generalizations.append(
                f"Task type '{state.goal_type.value}' with complexity '{state.complexity.value}' "
                f"required revision. Consider: {', '.join(state.evaluation_issues[:2])}"
            )
        if state.contradictions:
            generalizations.append(
                "Contradictory sources found. Always cross-verify before answering."
            )
        if state.knowledge_status == KnowledgeStatus.OUTDATED:
            generalizations.append(
                "Knowledge was outdated. Time-sensitive topics need fresh verification."
            )
        return generalizations

    def _should_store_in_memory(self, state: CognitiveState) -> bool:
        """Decide if this interaction is worth storing in memory."""
        # Don't store trivial interactions
        if state.complexity == Complexity.TRIVIAL:
            return False
        # Don't store if response was poor
        if state.needs_revision:
            return False
        # Store if it involved research or reasoning
        if state.selected_action in (
            DecisionAction.SEARCH,
            DecisionAction.DEEP_RESEARCH,
            DecisionAction.REASON,
        ):
            return True
        # Store if it was a code task
        if state.goal_type == GoalType.CODE:
            return True
        return False

    def _synthesize_from_learned_knowledge(self, state: CognitiveState) -> str:
        """Synthesize a response from learned knowledge."""
        if not state.learned_knowledge:
            return ""

        # Pick the highest-confidence learned knowledge, excluding generic observation claims
        useful = [k for k in state.learned_knowledge
                  if not k.claim.startswith("Task involved ")
                  and k.confidence >= 0.5]
        if not useful:
            # Fall back to any learned knowledge
            useful = state.learned_knowledge

        best = max(useful, key=lambda k: k.confidence)

        # Build response from the claim
        claim = best.claim
        concept = best.concept
        lang = state.detected_language

        # If the claim is a generic observation, don't use it as a response
        if claim.startswith("Task involved "):
            return ""

        if lang == "hindi":
            return f"**{concept.title()}**: {claim}"
        elif lang == "hinglish":
            return f"**{concept.title()}**: {claim}"
        else:
            return f"**{concept.title()}**: {claim}"

    def _synthesize_from_learned_skills(self, state: CognitiveState) -> str:
        """Synthesize a response from learned skills/procedures."""
        if not state.learned_skills:
            return ""

        best = max(state.learned_skills, key=lambda s: s.confidence)
        procedure = best.procedure

        if not procedure:
            return ""

        lang = state.detected_language
        steps_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(procedure))

        if lang == "hindi":
            return f"**{best.name}** का तरीका:\n\n{steps_text}"
        elif lang == "hinglish":
            return f"**{best.name}** ka tarika:\n\n{steps_text}"
        else:
            return f"**{best.name}** — here's how:\n\n{steps_text}"

    def _record_inference_outcome(self, state: CognitiveState, outcome: str):
        """Record the outcome of an inference for the feedback loop."""
        try:
            self.db.execute("""
                INSERT INTO intent_inference_outcomes
                (session_id, message, classified_intent, learned_intent, final_intent,
                 response_text, outcome, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state.session_id,
                state.raw_input[:500],
                state.goal_type.value,
                state.intent,
                state.goal_type.value,
                state.response_text[:500] if state.response_text else "",
                outcome,
                time.time(),
            ))
        except Exception as e:
            logger.warning(f"Failed to record inference outcome: {e}")
