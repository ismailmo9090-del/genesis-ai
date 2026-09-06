"""Skill engine for creating, retrieving, and adapting procedural knowledge."""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.database.db import DatabaseManager


@dataclass
class SkillStep:
    step_number: int
    action: str
    description: str = ""
    knowledge_required: str = ""
    tool_required: str = ""


class SkillEngine:
    """Manages skills as reusable procedural knowledge with adaptive steps."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def create_skill(
        self, name: str, description: str, steps: list[dict], context: dict = None
    ) -> int:
        existing = self.db.get_skill_by_name(name)
        if existing:
            self.db.update_skill(
                existing["id"],
                description=description,
                metadata=json.dumps(context or {}),
            )
            for step in self.db.get_skill_steps(existing["id"]):
                self.db.delete_skill_step(step["id"])
            for step_data in steps:
                self.db.insert_skill_step(
                    skill_id=existing["id"],
                    step_order=step_data.get("step_number", step_data.get("step_order", 0)),
                    action=step_data.get("action", ""),
                    description=step_data.get("description", ""),
                    expected_outcome=step_data.get("knowledge_required", ""),
                )
            return existing["id"]
        skill_id = self.db.insert_skill(
            name=name,
            description=description,
            skill_type=context.get("skill_type", "general") if context else "general",
            proficiency=0.0,
        )
        for step_data in steps:
            self.db.insert_skill_step(
                skill_id=skill_id,
                step_order=step_data.get("step_number", step_data.get("step_order", 0)),
                action=step_data.get("action", ""),
                description=step_data.get("description", ""),
                expected_outcome=step_data.get("knowledge_required", ""),
            )
        if context:
            self.db.update_skill(skill_id, metadata=json.dumps(context))
        return skill_id

    def get_skill(self, name: str) -> Optional[dict]:
        skill = self.db.get_skill_by_name(name)
        if not skill:
            return None
        steps = self.db.get_skill_steps(skill["id"])
        return {
            "id": skill["id"],
            "name": skill["name"],
            "description": skill["description"],
            "skill_type": skill["skill_type"],
            "proficiency": skill["proficiency"],
            "usage_count": skill["usage_count"],
            "last_used": skill["last_used"],
            "steps": [
                {
                    "step_number": s["step_order"],
                    "action": s["action"],
                    "description": s["description"],
                    "knowledge_required": s["expected_outcome"],
                    "tool_required": "",
                }
                for s in steps
            ],
        }

    def search_skills(self, query: str) -> list[dict]:
        query_lower = query.lower()
        all_skills = self.db.list_skills()
        results = []
        for skill in all_skills:
            score = 0.0
            name_lower = skill["name"].lower()
            desc_lower = (skill.get("description") or "").lower()
            if query_lower in name_lower:
                score += 0.6
            if query_lower in desc_lower:
                score += 0.3
            query_words = set(re.findall(r'\b[a-z]{3,}\b', query_lower))
            name_words = set(re.findall(r'\b[a-z]{3,}\b', name_lower))
            desc_words = set(re.findall(r'\b[a-z]{3,}\b', desc_lower))
            word_overlap = len(query_words & (name_words | desc_words))
            score += word_overlap * 0.05
            if score > 0:
                steps = self.db.get_skill_steps(skill["id"])
                results.append({
                    "id": skill["id"],
                    "name": skill["name"],
                    "description": skill["description"],
                    "skill_type": skill["skill_type"],
                    "proficiency": skill["proficiency"],
                    "usage_count": skill["usage_count"],
                    "relevance_score": round(score, 4),
                    "steps": [
                        {
                            "step_number": s["step_order"],
                            "action": s["action"],
                            "description": s["description"],
                        }
                        for s in steps
                    ],
                })
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results

    def reuse_skill(self, skill_id: int, new_context: dict = None) -> list[dict]:
        skill = self.db.get_skill(skill_id)
        if not skill:
            return []
        self.db.use_skill(skill_id)
        steps = self.db.get_skill_steps(skill_id)
        adapted = []
        new_context = new_context or {}
        context_domain = new_context.get("domain", "")
        context_tools = set(new_context.get("available_tools", []))
        context_requirements = new_context.get("requirements", [])
        for step in steps:
            adapted_step = {
                "step_number": step["step_order"],
                "action": step["action"],
                "description": step["description"],
                "knowledge_required": step["expected_outcome"],
                "tool_required": "",
                "adapted": False,
            }
            if context_domain:
                adapted_step["action"] = self._adapt_action(
                    step["action"], context_domain
                )
                if adapted_step["action"] != step["action"]:
                    adapted_step["adapted"] = True
            if context_requirements:
                required_tools = step.get("expected_outcome", "")
                if required_tools:
                    for req in context_requirements:
                        if req.lower() not in required_tools.lower():
                            adapted_step["description"] = (
                                adapted_step["description"]
                                + f" [Adapted for: {req}]"
                            )
                            adapted_step["adapted"] = True
            adapted.append(adapted_step)
        if new_context.get("skip_steps"):
            skip = set(new_context["skip_steps"])
            adapted = [s for s in adapted if s["step_number"] not in skip]
        if new_context.get("add_steps"):
            for extra in new_context["add_steps"]:
                adapted.append({
                    "step_number": len(adapted) + 1,
                    "action": extra.get("action", ""),
                    "description": extra.get("description", ""),
                    "knowledge_required": extra.get("knowledge_required", ""),
                    "tool_required": extra.get("tool_required", ""),
                    "adapted": True,
                })
        return adapted

    def rate_skill(self, skill_id: int, rating: float) -> Optional[dict]:
        skill = self.db.get_skill(skill_id)
        if not skill:
            return None
        rating = max(0.0, min(1.0, rating))
        current_prof = skill.get("proficiency", 0.0)
        usage_count = skill.get("usage_count", 0)
        new_prof = (current_prof * usage_count + rating) / max(usage_count + 1, 1)
        new_prof = round(max(0.0, min(1.0, new_prof)), 4)
        self.db.update_skill(skill_id, proficiency=new_prof)
        updated = self.db.get_skill(skill_id)
        steps = self.db.get_skill_steps(skill_id)
        return {
            "id": updated["id"],
            "name": updated["name"],
            "proficiency": updated["proficiency"],
            "usage_count": updated["usage_count"],
            "steps": [
                {
                    "step_number": s["step_order"],
                    "action": s["action"],
                    "success_rate": s.get("success_rate", 0.0),
                }
                for s in steps
            ],
        }

    def get_skill_stats(self) -> dict:
        all_skills = self.db.list_skills()
        total = len(all_skills)
        total_usage = sum(s.get("usage_count", 0) for s in all_skills)
        avg_proficiency = (
            sum(s.get("proficiency", 0) for s in all_skills) / total if total > 0 else 0.0
        )
        type_counts = {}
        for s in all_skills:
            st = s.get("skill_type", "general")
            type_counts[st] = type_counts.get(st, 0) + 1
        top_skills = sorted(all_skills, key=lambda x: x.get("usage_count", 0), reverse=True)[:5]
        return {
            "total_skills": total,
            "total_usage_count": total_usage,
            "average_proficiency": round(avg_proficiency, 4),
            "skills_by_type": type_counts,
            "most_used_skills": [
                {"name": s["name"], "usage_count": s["usage_count"], "proficiency": s.get("proficiency", 0)}
                for s in top_skills
            ],
        }

    def _adapt_action(self, action: str, domain: str) -> str:
        domain_lower = domain.lower()
        action_lower = action.lower()
        adaptations = {
            "code": {"write": "implement", "test": "unit test", "review": "code review"},
            "data": {"write": "query", "test": "validate", "analyze": "statistical analysis"},
            "design": {"write": "sketch", "test": "usability review", "review": "critique"},
        }
        for _domain, mapping in adaptations.items():
            if _domain in domain_lower:
                for original, replacement in mapping.items():
                    if original in action_lower:
                        return action.replace(original, replacement)
        return action

    def _build_adapted_description(self, base_description: str, context: dict) -> str:
        parts = [base_description]
        if context.get("domain"):
            parts.append(f"Domain: {context['domain']}")
        if context.get("requirements"):
            parts.append(f"Requirements: {', '.join(context['requirements'])}")
        return " | ".join(parts)
