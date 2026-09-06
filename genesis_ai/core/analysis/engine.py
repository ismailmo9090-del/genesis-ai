"""Analysis engine for decomposing problems into components and identifying knowledge gaps.

Takes an UnderstandingResult and breaks it into actionable components,
checks existing knowledge, and identifies what needs to be researched.
"""

from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.knowledge.graph.engine import KnowledgeGraph
from genesis_ai.knowledge.storage.engine import KnowledgeStorage
from genesis_ai.core.understanding.engine import UnderstandingResult


@dataclass
class AnalysisResult:
    """Result of analyzing a user's request into components and knowledge gaps."""

    components: list[dict] = field(default_factory=list)
    known_knowledge: list[dict] = field(default_factory=list)
    unknown_knowledge: list[dict] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    recommended_approach: str = ""
    complexity_score: float = 0.0
    estimated_steps: int = 0
    research_needed: bool = True


# ── Component templates per intent ─────────────────────────────

_CODE_COMPONENTS = {
    "input": "Define input parameters, data sources, and user interface requirements",
    "processing": "Core business logic, algorithms, and data transformations",
    "output": "Output format, display logic, and response structure",
    "error_handling": "Exception handling, validation, edge cases, and error messages",
    "testing": "Unit tests, integration tests, and validation cases",
}

_RESEARCH_COMPONENTS = {
    "definitions": "Core definitions and terminology for the topic",
    "examples": "Concrete examples and illustrations",
    "details": "In-depth details, mechanisms, and processes",
    "sources": "Authoritative sources and references",
}

_EXPLAIN_COMPONENTS = {
    "concept_identification": "What is the core concept to explain",
    "prerequisites": "Background knowledge needed to understand",
    "structure": "Logical flow of the explanation",
    "examples": "Concrete examples to illustrate the concept",
    "summary": "Key takeaways and summary",
}

_COMPARE_COMPONENTS = {
    "item_a": "First item to compare",
    "item_b": "Second item to compare",
    "criteria": "Attributes and criteria for comparison",
    "analysis": "Detailed comparison analysis",
    "conclusion": "Summary of comparison results",
}

_FIX_COMPONENTS = {
    "symptom": "Identify the error symptom and reproduction steps",
    "root_cause": "Diagnose the root cause of the issue",
    "solution": "Proposed fix and implementation",
    "verification": "Verify the fix resolves the issue",
}

_OPTIMIZE_COMPONENTS = {
    "baseline": "Current performance and behavior",
    "bottleneck": "Identified performance bottlenecks",
    "improvements": "Proposed optimization strategies",
    "validation": "Validate improvements deliver results",
}

_DEFAULT_COMPONENTS = {
    "understanding": "Clarify the exact request",
    "gathering": "Gather necessary information",
    "processing": "Process and synthesize the information",
    "output": "Deliver the result",
}


# ── Complexity weights ─────────────────────────────────────────

_INTENT_COMPLEXITY = {
    "create": 0.7,
    "fix": 0.6,
    "optimize": 0.75,
    "analyze": 0.65,
    "compare": 0.5,
    "explain": 0.4,
    "research": 0.55,
    "summarize": 0.3,
    "list": 0.25,
    "translate": 0.3,
}

_TASK_TYPE_COMPLEXITY = {
    "code": 0.8,
    "analysis": 0.7,
    "factual": 0.4,
    "creative": 0.5,
    "math": 0.65,
    "conversation": 0.1,
}

_COMPONENT_BASE_COMPLEXITY = 0.08


class AnalysisEngine:
    """Decomposes user requests into components and identifies knowledge gaps.

    Uses the UnderstandingResult to break problems into manageable parts,
    checks the local knowledge graph and storage for existing knowledge,
    and identifies what needs to be researched externally.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.graph = KnowledgeGraph(db)
        self.storage = KnowledgeStorage(db)

    def analyze(self, understanding: UnderstandingResult) -> AnalysisResult:
        """Analyze an understood request and produce a component breakdown.

        Args:
            understanding: The structured UnderstandingResult from the UnderstandingEngine.

        Returns:
            AnalysisResult with components, known/unknown knowledge, and complexity.
        """
        result = AnalysisResult()

        result.components = self._build_components(understanding)
        result.dependencies = self._build_dependencies(result.components, understanding)

        for component in result.components:
            known, unknown = self._check_knowledge_for_component(component, understanding)
            result.known_knowledge.extend(known)
            result.unknown_knowledge.extend(unknown)

        result.known_knowledge = self._deduplicate_knowledge(result.known_knowledge)
        result.unknown_knowledge = self._deduplicate_knowledge(result.unknown_knowledge)

        result.recommended_approach = self._recommend_approach(understanding, result)
        result.complexity_score = self._calculate_complexity(understanding, result)
        result.estimated_steps = self._estimate_steps(result)

        return result

    def _build_components(self, understanding: UnderstandingResult) -> list[dict]:
        """Build a list of problem components based on intent and task type."""
        intent = understanding.intent
        task_type = understanding.task_type

        template_map = {
            "create": _CODE_COMPONENTS if task_type == "code" else _DEFAULT_COMPONENTS,
            "fix": _FIX_COMPONENTS,
            "optimize": _OPTIMIZE_COMPONENTS,
            "analyze": _RESEARCH_COMPONENTS,
            "compare": _COMPARE_COMPONENTS,
            "explain": _EXPLAIN_COMPONENTS,
            "research": _RESEARCH_COMPONENTS,
            "summarize": _DEFAULT_COMPONENTS,
            "list": _DEFAULT_COMPONENTS,
            "translate": _DEFAULT_COMPONENTS,
        }

        template = template_map.get(intent, _DEFAULT_COMPONENTS)
        components = []

        for name, description in template.items():
            component = {
                "name": name,
                "description": description,
                "type": self._classify_component_type(name, intent, task_type),
                "complexity": self._estimate_component_complexity(name, intent, task_type),
                "status": "pending",
            }
            components.append(component)

        for sub_task in understanding.sub_tasks:
            already_covered = any(
                sub_task.replace("_", " ") in c["description"].lower()
                or sub_task in c["name"]
                for c in components
            )
            if not already_covered:
                components.append({
                    "name": sub_task,
                    "description": f"Handle sub-task: {sub_task.replace('_', ' ')}",
                    "type": "processing",
                    "complexity": 0.3,
                    "status": "pending",
                })

        return components

    def _classify_component_type(self, name: str, intent: str, task_type: str) -> str:
        """Classify a component's functional type."""
        type_hints = {
            "input": "input",
            "definition": "input",
            "item_a": "input",
            "item_b": "input",
            "symptom": "input",
            "baseline": "input",
            "output": "output",
            "result": "output",
            "conclusion": "output",
            "summary": "output",
            "error_handling": "validation",
            "testing": "validation",
            "verification": "validation",
            "validation": "validation",
        }
        return type_hints.get(name, "processing")

    def _estimate_component_complexity(self, name: str, intent: str, task_type: str) -> float:
        """Estimate complexity of a single component on a 0-1 scale."""
        base = _COMPONENT_BASE_COMPLEXITY
        complexity_hints = {
            "processing": 0.15,
            "core": 0.2,
            "algorithm": 0.25,
            "analysis": 0.2,
            "diagnosis": 0.2,
            "root_cause": 0.25,
            "bottleneck": 0.2,
            "testing": 0.1,
            "verification": 0.1,
            "error_handling": 0.1,
            "input": 0.05,
            "output": 0.05,
            "summary": 0.05,
        }
        for hint, weight in complexity_hints.items():
            if hint in name:
                return base + weight
        return base

    def _build_dependencies(self, components: list[dict], understanding: UnderstandingResult) -> list[dict]:
        """Map dependencies between components."""
        dependencies = []
        component_names = [c["name"] for c in components]

        dependency_rules = {
            "processing": ["input"],
            "output": ["processing"],
            "error_handling": ["processing"],
            "testing": ["processing", "error_handling"],
            "solution": ["root_cause", "symptom"],
            "verification": ["solution"],
            "improvements": ["baseline", "bottleneck"],
            "validation": ["improvements"],
            "analysis": ["item_a", "item_b", "criteria"],
            "conclusion": ["analysis"],
            "examples": ["definitions"],
            "details": ["definitions", "examples"],
            "sources": ["details"],
            "prerequisites": ["concept_identification"],
            "structure": ["concept_identification", "prerequisites"],
            "gather": ["understanding"],
            "synthesize_answer": ["gather_information"],
            "generate_summary": ["extract_key_points"],
        }

        for component in components:
            name = component["name"]
            if name in dependency_rules:
                for dep in dependency_rules[name]:
                    if dep in component_names:
                        dependencies.append({
                            "component": name,
                            "depends_on": dep,
                            "type": "requires",
                        })

        return dependencies

    def _check_knowledge_for_component(
        self, component: dict, understanding: UnderstandingResult
    ) -> tuple[list[dict], list[dict]]:
        """Check local knowledge for a component and categorize as known or unknown."""
        known = []
        unknown = []

        search_terms = self._build_search_terms(component, understanding)

        for term in search_terms:
            graph_results = self.graph.search_concepts(term)
            storage_results = self.storage.search_knowledge(term)

            if graph_results or storage_results:
                known.append({
                    "component": component["name"],
                    "query": term,
                    "graph_matches": len(graph_results),
                    "storage_matches": len(storage_results),
                    "source": "local_knowledge",
                })
            else:
                unknown.append({
                    "component": component["name"],
                    "query": term,
                    "gap_type": "missing",
                    "priority": self._assess_gap_priority(component, understanding),
                })

        if not search_terms:
            unknown.append({
                "component": component["name"],
                "query": component["description"],
                "gap_type": "missing",
                "priority": "medium",
            })

        return known, unknown

    def _build_search_terms(self, component: dict, understanding: UnderstandingResult) -> list[str]:
        """Generate search terms from component and understanding context."""
        terms = []

        component_name = component["name"].replace("_", " ")
        terms.append(component_name)

        if understanding.entities.get("topics"):
            for topic in understanding.entities["topics"]:
                terms.append(f"{topic} {component_name}")

        if understanding.entities.get("languages"):
            for lang in understanding.entities["languages"]:
                terms.append(f"{lang} {component_name}")

        if understanding.entities.get("frameworks"):
            for fw in understanding.entities["frameworks"]:
                terms.append(f"{fw} {component_name}")

        if understanding.domain != "general":
            terms.append(f"{understanding.domain} {component_name}")

        return list(set(terms))

    def _assess_gap_priority(self, component: dict, understanding: UnderstandingResult) -> str:
        """Assess the priority of a knowledge gap for a component."""
        component_type = component.get("type", "processing")
        if component_type == "input":
            return "high"
        if component_type == "validation":
            return "low"
        if understanding.intent == "fix" and component["name"] in ("root_cause", "solution"):
            return "high"
        if understanding.intent == "create" and component["name"] == "processing":
            return "high"
        return "medium"

    def _deduplicate_knowledge(self, knowledge_list: list[dict]) -> list[dict]:
        """Remove duplicate knowledge entries."""
        seen = set()
        deduped = []
        for item in knowledge_list:
            key = (item.get("component", ""), item.get("query", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    def _recommend_approach(self, understanding: UnderstandingResult, result: AnalysisResult) -> str:
        """Recommend an execution approach based on analysis."""
        intent = understanding.intent
        task_type = understanding.task_type
        complexity = understanding.complexity
        unknown_count = len(result.unknown_knowledge)
        known_count = len(result.known_knowledge)

        if unknown_count == 0 and known_count > 0:
            return "local_only"
        if unknown_count == 0:
            return "direct_response"
        if complexity == "simple" and unknown_count <= 2:
            return "quick_research_then_respond"
        if intent in ("create", "fix", "optimize"):
            return "deep_research_then_build"
        if intent == "research":
            return "comprehensive_research"
        if intent == "explain":
            return "research_and_explain"
        if intent == "compare":
            return "parallel_research_then_compare"
        return "standard_research"

    def _calculate_complexity(self, understanding: UnderstandingResult, result: AnalysisResult) -> float:
        """Calculate a normalized complexity score from 0.0 to 1.0."""
        score = 0.0

        intent_weight = _INTENT_COMPLEXITY.get(understanding.intent, 0.5)
        score += intent_weight * 0.3

        task_weight = _TASK_TYPE_COMPLEXITY.get(understanding.task_type, 0.5)
        score += task_weight * 0.2

        component_count = len(result.components)
        component_score = min(component_count / 10.0, 1.0)
        score += component_score * 0.2

        unknown_ratio = (
            len(result.unknown_knowledge) / max(len(result.unknown_knowledge) + len(result.known_knowledge), 1)
        )
        score += unknown_ratio * 0.15

        dependency_score = min(len(result.dependencies) / 8.0, 1.0)
        score += dependency_score * 0.15

        return round(min(score, 1.0), 3)

    def _estimate_steps(self, result: AnalysisResult) -> int:
        """Estimate the number of execution steps needed."""
        base_steps = len(result.components)
        research_steps = len(result.unknown_knowledge)
        dependency_overhead = len(result.dependencies) // 3

        return base_steps + research_steps + dependency_overhead + 1
