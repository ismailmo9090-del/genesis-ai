"""Reasoning engine implementing multiple reasoning strategies."""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager
from genesis_ai.knowledge.graph.engine import KnowledgeGraph
from genesis_ai.knowledge.retrieval.engine import KnowledgeRetrieval


@dataclass
class ReasoningResult:
    query: str
    conclusions: list[dict] = field(default_factory=list)
    reasoning_type: str = "mixed"
    confidence: float = 0.0
    steps: list[str] = field(default_factory=list)
    supporting_evidence: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)


class ReasoningEngine:
    """Multi-strategy reasoning engine for query analysis and problem solving."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.graph = KnowledgeGraph(db)
        self.retrieval = KnowledgeRetrieval(db)

    def reason(self, query: str, context: dict = None, knowledge: list[dict] = None) -> ReasoningResult:
        context = context or {}
        result = ReasoningResult(query=query)
        sub_queries = self.decompose_query(query)
        result.steps.append(f"Decomposed into {len(sub_queries)} sub-queries: {sub_queries}")
        retrieved = knowledge or self.retrieval.retrieve(query, context)
        result.steps.append(f"Retrieved {len(retrieved)} knowledge items")
        rule_conclusions = self.rule_based_reasoning(retrieved, self._load_rules(context))
        result.conclusions.extend(rule_conclusions)
        result.steps.append(f"Rule-based reasoning produced {len(rule_conclusions)} conclusions")
        concept_insights = self.concept_reasoning(query, self.graph)
        result.conclusions.extend(concept_insights)
        result.steps.append(f"Concept reasoning produced {len(concept_insights)} insights")
        for sq in sub_queries:
            sq_results = self.retrieval.retrieve(sq, context)
            for item in sq_results[:3]:
                result.supporting_evidence.append({
                    "sub_query": sq,
                    "claim": item.get("claim"),
                    "confidence": item.get("confidence"),
                    "source": item.get("source"),
                })
        for item in retrieved:
            status = item.get("verification_status")
            if status == "disputed":
                result.contradictions.append({
                    "claim": item.get("claim"),
                    "confidence": item.get("confidence"),
                })
        all_confs = [c.get("confidence", 0) for c in result.conclusions]
        result.confidence = sum(all_confs) / len(all_confs) if all_confs else 0.0
        result.reasoning_type = self._classify_query(query)
        return result

    def decompose_query(self, query: str) -> list[str]:
        sub_queries = []
        query_lower = query.lower()
        question_words = ["what", "how", "why", "when", "where", "who", "which"]
        conjunctions = [" and ", " or ", " also ", " additionally ", " furthermore "]
        has_question = any(query_lower.startswith(qw) for qw in question_words)
        if has_question:
            parts = re.split(r'\band\b|\bor\b', query_lower)
            for part in parts:
                part = part.strip().strip('?').strip()
                if len(part) > 5:
                    sub_queries.append(part.capitalize())
        else:
            for conj in conjunctions:
                if conj in query_lower:
                    parts = query_lower.split(conj)
                    for part in parts:
                        part = part.strip().strip('?').strip()
                        if len(part) > 5:
                            sub_queries.append(part.capitalize())
                    break
        if not sub_queries:
            sub_queries = [query.strip().rstrip('?')]
        if len(sub_queries) > 1:
            topics = [sq.split()[0] if sq.split() else sq for sq in sub_queries]
            combined = f"Relationship between {', '.join(topics)}"
            sub_queries.append(combined)
        return sub_queries

    def rule_based_reasoning(self, facts: list[dict], rules: list[dict] = None) -> list[dict]:
        if not rules:
            rules = self._default_rules()
        conclusions = []
        fact_texts = [f.get("claim", "").lower() for f in facts]
        for rule in rules:
            condition = rule.get("condition", "").lower()
            if not condition:
                continue
            condition_parts = condition.split(" AND ")
            all_met = True
            for part in condition_parts:
                part = part.strip()
                if not any(part in ft for ft in fact_texts):
                    all_met = False
                    break
            if all_met:
                conclusions.append({
                    "conclusion": rule.get("conclusion", ""),
                    "confidence": rule.get("confidence", 0.5),
                    "rule": rule.get("name", "unknown"),
                    "reasoning_type": "rule_based",
                })
        return conclusions

    def concept_reasoning(self, query: str, knowledge_graph: KnowledgeGraph) -> list[dict]:
        insights = []
        concepts = knowledge_graph.search_concepts(query)
        for concept in concepts[:5]:
            related = knowledge_graph.get_related(concept["name"])
            if related:
                relation_types = [r["relation_type"] for r in related]
                type_counts = defaultdict(int)
                for rt in relation_types:
                    type_counts[rt] += 1
                dominant = max(type_counts, key=type_counts.get)
                insights.append({
                    "concept": concept["name"],
                    "insight": f"Concept '{concept['name']}' has {len(related)} relationships, dominated by '{dominant}'",
                    "dominant_relation": dominant,
                    "relation_count": len(related),
                    "confidence": concept.get("confidence", 0.5),
                    "reasoning_type": "concept_based",
                })
                if "contradicts" in type_counts:
                    contra_rels = [r for r in related if r["relation_type"] == "contradicts"]
                    insights.append({
                        "concept": concept["name"],
                        "insight": f"Contradiction detected for '{concept['name']}'",
                        "contradictions": [{"target": r["concept_name"], "strength": r["strength"]} for r in contra_rels],
                        "confidence": 0.7,
                        "reasoning_type": "contradiction_detection",
                    })
        return insights

    def plan_task(self, task_description: str) -> list[dict]:
        steps = []
        task_lower = task_description.lower()
        step_templates = [
            {
                "keywords": ["create", "build", "make", "develop", "implement", "write"],
                "steps": [
                    {"order": 1, "action": "Analyze requirements", "description": "Understand what needs to be created"},
                    {"order": 2, "action": "Design solution", "description": "Plan the architecture and approach"},
                    {"order": 3, "action": "Implement", "description": "Build the solution step by step"},
                    {"order": 4, "action": "Test and verify", "description": "Validate the implementation works correctly"},
                    {"order": 5, "action": "Document", "description": "Document the solution and usage"},
                ],
            },
            {
                "keywords": ["fix", "debug", "resolve", "repair", "troubleshoot"],
                "steps": [
                    {"order": 1, "action": "Identify the problem", "description": "Gather information about the issue"},
                    {"order": 2, "action": "Analyze root cause", "description": "Determine why the problem occurs"},
                    {"order": 3, "action": "Implement fix", "description": "Apply the solution"},
                    {"order": 4, "action": "Verify resolution", "description": "Confirm the fix works"},
                ],
            },
            {
                "keywords": ["learn", "study", "understand", "research", "explore"],
                "steps": [
                    {"order": 1, "action": "Gather information", "description": "Collect relevant resources and knowledge"},
                    {"order": 2, "action": "Analyze information", "description": "Study and process the gathered data"},
                    {"order": 3, "action": "Synthesize understanding", "description": "Form coherent understanding from the analysis"},
                    {"order": 4, "action": "Apply knowledge", "description": "Use the understanding to solve related problems"},
                ],
            },
            {
                "keywords": ["compare", "evaluate", "assess", "analyze"],
                "steps": [
                    {"order": 1, "action": "Define criteria", "description": "Establish evaluation criteria"},
                    {"order": 2, "action": "Gather data", "description": "Collect information for each option"},
                    {"order": 3, "action": "Apply criteria", "description": "Evaluate each option against criteria"},
                    {"order": 4, "action": "Draw conclusions", "description": "Form conclusions based on evaluation"},
                ],
            },
        ]
        for template in step_templates:
            if any(kw in task_lower for kw in template["keywords"]):
                steps = template["steps"]
                break
        if not steps:
            steps = [
                {"order": 1, "action": "Understand the task", "description": "Clarify what needs to be done"},
                {"order": 2, "action": "Gather resources", "description": "Collect needed information and tools"},
                {"order": 3, "action": "Execute", "description": "Perform the task"},
                {"order": 4, "action": "Verify results", "description": "Check that the outcome is correct"},
            ]
        task_concepts = self.graph.search_concepts(task_description)
        if task_concepts:
            for concept in task_concepts[:3]:
                related = self.graph.get_related(concept["name"])
                if related:
                    steps.append({
                        "order": len(steps) + 1,
                        "action": f"Consider related concept: {concept['name']}",
                        "description": f"Related concepts: {', '.join(r['concept_name'] for r in related[:3])}",
                    })
        return steps

    def compare(self, options: list[str], criteria: list[str] = None) -> list[dict]:
        if not criteria:
            criteria = ["relevance", "confidence", "coverage"]
        scored = []
        for option in options:
            option_data = {
                "option": option,
                "scores": {},
                "total_score": 0.0,
            }
            search_results = self.retrieval.retrieve(option)
            relevance = len(search_results) / 10.0
            option_data["scores"]["relevance"] = min(relevance, 1.0)
            if search_results:
                avg_conf = sum(r.get("confidence", 0) for r in search_results) / len(search_results)
                option_data["scores"]["confidence"] = avg_conf
            else:
                option_data["scores"]["confidence"] = 0.0
            graph_concepts = self.graph.search_concepts(option)
            option_data["scores"]["coverage"] = min(len(graph_concepts) / 5.0, 1.0)
            concept_insights = self.concept_reasoning(option, self.graph)
            option_data["scores"]["concept_richness"] = min(len(concept_insights) / 5.0, 1.0)
            for criterion in criteria:
                if criterion not in option_data["scores"]:
                    option_data["scores"][criterion] = 0.5
            weights = {c: 1.0 / len(criteria) for c in criteria}
            total = sum(option_data["scores"].get(c, 0) * w for c, w in weights.items())
            option_data["total_score"] = round(total, 4)
            scored.append(option_data)
        scored.sort(key=lambda x: x["total_score"], reverse=True)
        for rank, item in enumerate(scored):
            item["rank"] = rank + 1
        return scored

    def deduct(self, knowledge_items: list[dict]) -> list[dict]:
        conclusions = []
        claims_by_type = defaultdict(list)
        for item in knowledge_items:
            ct = item.get("claim_type", "fact")
            claims_by_type[ct].append(item)
        for item in knowledge_items:
            claim = item.get("claim", "").lower()
            if "all " in claim and " are " in claim:
                subject = claim.split("all ")[1].split(" are ")[0].strip()
                predicate = claim.split(" are ")[1].strip()
                for other in knowledge_items:
                    if other["id"] != item["id"]:
                        other_claim = other.get("claim", "").lower()
                        if subject in other_claim and " is " in other_claim:
                            obj = other_claim.split(" is ")[1].strip()
                            if predicate not in obj:
                                conclusions.append({
                                    "conclusion": f"Since all {subject} are {predicate}, and this is a {subject}, it is also {predicate}",
                                    "premises": [item.get("claim"), other.get("claim")],
                                    "confidence": min(item.get("confidence", 0.5), other.get("confidence", 0.5)) * 0.9,
                                    "reasoning_type": "deductive",
                                })
        verified = [k for k in knowledge_items if k.get("verification_status") == "verified"]
        disputed = [k for k in knowledge_items if k.get("verification_status") == "disputed"]
        if verified and disputed:
            verified_topics = set()
            for v in verified:
                verified_topics.add(v.get("topic", ""))
            for d in disputed:
                if d.get("topic") in verified_topics:
                    conclusions.append({
                        "conclusion": f"Disputed claim '{d.get('claim', '')}' may be false given verified knowledge on the same topic",
                        "confidence": 0.6,
                        "reasoning_type": "abductive",
                    })
        return conclusions

    def _load_rules(self, context: dict) -> list[dict]:
        rules = context.get("rules", [])
        rules.extend(self._default_rules())
        return rules

    def _default_rules(self) -> list[dict]:
        return [
            {
                "name": "confidence_boost",
                "condition": "verified",
                "conclusion": "Verified knowledge has higher reliability",
                "confidence": 0.8,
            },
            {
                "name": "source_reliability",
                "condition": "peer-reviewed",
                "conclusion": "Peer-reviewed sources are more trustworthy",
                "confidence": 0.85,
            },
            {
                "name": "contradiction_warning",
                "condition": "contradicts",
                "conclusion": "Conflicting information requires further investigation",
                "confidence": 0.7,
            },
        ]

    def _classify_query(self, query: str) -> str:
        query_lower = query.lower()
        if any(w in query_lower for w in ["compare", "versus", "vs", "better", "worse"]):
            return "comparison"
        if any(w in query_lower for w in ["plan", "how to", "steps", "process"]):
            return "planning"
        if any(w in query_lower for w in ["why", "reason", "cause", "because"]):
            return "causal"
        if any(w in query_lower for w in ["what is", "define", "explain", "describe"]):
            return "definitional"
        if any(w in query_lower for w in ["is it true", "verify", "confirm", "fact"]):
            return "verification"
        return "exploratory"
