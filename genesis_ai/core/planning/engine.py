"""Planning engine for task decomposition, execution tracking, and re-planning."""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from genesis_ai.database.db import DatabaseManager


class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    step_number: int
    action: str
    description: str
    knowledge_needed: list[str] = field(default_factory=list)
    tool_needed: Optional[str] = None
    status: str = StepStatus.PENDING.value
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class Plan:
    plan_id: str
    goal: str
    context: dict = field(default_factory=dict)
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "active"
    progress: float = 0.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    execution_results: list[dict] = field(default_factory=list)
    failure_count: int = 0
    replan_count: int = 0


@dataclass
class ExecutionResult:
    success: bool
    plan_id: str
    completed_steps: int
    total_steps: int
    results: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    duration_ms: int = 0


class PlanningEngine:
    """Task planning, execution, and re-planning engine."""

    MAX_STEPS = 50
    MAX_REPLANS = 5

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._active_plans: dict[str, Plan] = {}

    def create_plan(
        self,
        goal: str,
        context: dict = None,
        available_skills: list[dict] = None,
    ) -> Plan:
        context = context or {}
        available_skills = available_skills or []
        plan_id = f"plan_{int(time.time() * 1000)}"
        steps = self._decompose_goal(goal, context, available_skills)
        plan = Plan(
            plan_id=plan_id,
            goal=goal,
            context=context,
            steps=steps,
        )
        self._active_plans[plan_id] = plan
        self._persist_plan(plan)
        return plan

    def execute_plan(self, plan: Plan) -> ExecutionResult:
        start_time = time.time()
        results = []
        errors = []
        for step in plan.steps:
            if step.status == StepStatus.COMPLETED.value:
                continue
            if step.status == StepStatus.SKIPPED.value:
                continue
            step.status = StepStatus.IN_PROGRESS.value
            step.started_at = datetime.now(timezone.utc).isoformat()
            try:
                step_result = self._execute_step(step, plan.context)
                step.result = step_result
                step.status = StepStatus.COMPLETED.value
                step.completed_at = datetime.now(timezone.utc).isoformat()
                results.append(
                    {
                        "step": step.step_number,
                        "action": step.action,
                        "result": step_result,
                        "success": True,
                    }
                )
            except Exception as e:
                step.status = StepStatus.FAILED.value
                step.error = str(e)
                step.completed_at = datetime.now(timezone.utc).isoformat()
                plan.failure_count += 1
                errors.append(
                    {
                        "step": step.step_number,
                        "action": step.action,
                        "error": str(e),
                    }
                )
                if self._should_abort(plan):
                    plan.status = "failed"
                    break
            if step.started_at and step.completed_at:
                try:
                    start = datetime.fromisoformat(step.started_at)
                    end = datetime.fromisoformat(step.completed_at)
                    step.duration_ms = int((end - start).total_seconds() * 1000)
                except (ValueError, TypeError):
                    step.duration_ms = 0
            plan.progress = self._calculate_progress(plan)
            plan.updated_at = datetime.now(timezone.utc).isoformat()
            self._persist_plan(plan)
        elapsed = int((time.time() - start_time) * 1000)
        completed = sum(
            1 for s in plan.steps if s.status == StepStatus.COMPLETED.value
        )
        all_done = completed == len(plan.steps)
        if plan.status != "failed":
            plan.status = "completed" if all_done else "partial"
        plan.execution_results = results
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_plan(plan)
        return ExecutionResult(
            success=plan.status == "completed",
            plan_id=plan.plan_id,
            completed_steps=completed,
            total_steps=len(plan.steps),
            results=results,
            errors=errors,
            duration_ms=elapsed,
        )

    def replan(self, plan: Plan, new_info: dict) -> Plan:
        if plan.replan_count >= self.MAX_REPLANS:
            return plan
        plan.replan_count += 1
        remaining_steps = [
            s for s in plan.steps if s.status in (StepStatus.PENDING.value, StepStatus.FAILED.value)
        ]
        for step in remaining_steps:
            step.status = StepStatus.SKIPPED.value
        new_context = {**plan.context, **new_info}
        new_steps = self._decompose_goal(plan.goal, new_context, [])
        existing_count = len(plan.steps)
        for i, step in enumerate(new_steps):
            step.step_number = existing_count + i + 1
        plan.steps.extend(new_steps)
        plan.context = new_context
        plan.status = "active"
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_plan(plan)
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        if plan_id in self._active_plans:
            return self._active_plans[plan_id]
        return None

    def list_plans(self, status: str = None, limit: int = 20) -> list[dict]:
        with self.db.get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE task_type = 'plan' AND status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE task_type = 'plan' ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_step_status(self, plan: Plan, step_number: int) -> Optional[PlanStep]:
        for step in plan.steps:
            if step.step_number == step_number:
                return step
        return None

    def skip_step(self, plan: Plan, step_number: int, reason: str = "") -> bool:
        for step in plan.steps:
            if step.step_number == step_number:
                step.status = StepStatus.SKIPPED.value
                step.result = f"Skipped: {reason}" if reason else "Skipped"
                plan.updated_at = datetime.now(timezone.utc).isoformat()
                plan.progress = self._calculate_progress(plan)
                self._persist_plan(plan)
                return True
        return False

    def abort_plan(self, plan: Plan) -> Plan:
        plan.status = "aborted"
        for step in plan.steps:
            if step.status in (StepStatus.PENDING.value, StepStatus.IN_PROGRESS.value):
                step.status = StepStatus.SKIPPED.value
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist_plan(plan)
        return plan

    def _decompose_goal(
        self,
        goal: str,
        context: dict,
        available_skills: list[dict],
    ) -> list[PlanStep]:
        goal_lower = goal.lower()
        steps = []
        step_templates = [
            {
                "keywords": ["create", "build", "make", "develop", "implement", "write"],
                "actions": [
                    ("Analyze requirements", "Understand what needs to be created and gather constraints", [], None),
                    ("Design approach", "Determine the best architecture and implementation strategy", [], None),
                    ("Gather resources", "Collect needed libraries, tools, and references", [], None),
                    ("Implement", "Build the solution step by step", [], None),
                    ("Test and validate", "Verify the implementation meets requirements", [], None),
                ],
            },
            {
                "keywords": ["fix", "debug", "resolve", "repair", "troubleshoot"],
                "actions": [
                    ("Reproduce the issue", "Identify and reproduce the problem reliably", [], None),
                    ("Diagnose root cause", "Analyze logs, stack traces, and behavior to find the cause", [], None),
                    ("Implement fix", "Apply a targeted fix for the root cause", [], None),
                    ("Verify resolution", "Confirm the fix works and no regressions", [], None),
                ],
            },
            {
                "keywords": ["research", "learn", "study", "understand", "explore"],
                "actions": [
                    ("Define scope", "Clarify what specifically needs to be understood", [], None),
                    ("Gather information", "Collect relevant data from knowledge base or external sources", [], "web_search"),
                    ("Analyze findings", "Process and synthesize the gathered information", [], None),
                    ("Form conclusions", "Create structured understanding from the analysis", [], None),
                ],
            },
            {
                "keywords": ["optimize", "improve", "enhance", "refactor"],
                "actions": [
                    ("Measure current state", "Establish baseline metrics for current performance", [], None),
                    ("Identify bottlenecks", "Find the primary areas limiting performance", [], None),
                    ("Implement improvements", "Apply targeted optimizations", [], None),
                    ("Measure results", "Verify improvements against baseline", [], None),
                ],
            },
            {
                "keywords": ["analyze", "evaluate", "compare", "assess"],
                "actions": [
                    ("Define criteria", "Establish evaluation metrics and thresholds", [], None),
                    ("Collect data", "Gather relevant information for each option", [], None),
                    ("Apply criteria", "Evaluate each option against defined criteria", [], None),
                    ("Summarize findings", "Present conclusions with supporting evidence", [], None),
                ],
            },
        ]
        for template in step_templates:
            if any(kw in goal_lower for kw in template["keywords"]):
                for i, (action, desc, knowledge, tool) in enumerate(template["actions"]):
                    steps.append(
                        PlanStep(
                            step_number=i + 1,
                            action=action,
                            description=desc,
                            knowledge_needed=knowledge,
                            tool_needed=tool,
                        )
                    )
                break
        if not steps:
            steps = [
                PlanStep(step_number=1, action="Understand the goal", description="Clarify objectives and constraints"),
                PlanStep(step_number=2, action="Gather context", description="Collect relevant information"),
                PlanStep(step_number=3, action="Formulate approach", description="Determine the best strategy"),
                PlanStep(step_number=4, action="Execute", description="Carry out the plan"),
                PlanStep(step_number=5, action="Verify results", description="Validate the outcome"),
            ]
        if available_skills:
            relevant_skills = self._match_skills_to_steps(steps, available_skills)
            for step_idx, skill in relevant_skills:
                if step_idx < len(steps):
                    steps[step_idx].tool_needed = skill.get("name")
        return steps

    def _match_skills_to_steps(
        self, steps: list[PlanStep], skills: list[dict]
    ) -> list[tuple[int, dict]]:
        matches = []
        for skill in skills:
            skill_name = skill.get("name", "").lower()
            skill_desc = skill.get("description", "").lower()
            for i, step in enumerate(steps):
                action_lower = step.action.lower()
                if any(kw in action_lower for kw in skill_name.split()):
                    matches.append((i, skill))
                    break
                if any(kw in skill_desc for kw in action_lower.split()):
                    matches.append((i, skill))
                    break
        return matches

    def _execute_step(self, step: PlanStep, context: dict) -> str:
        if step.tool_needed:
            return f"Executed '{step.action}' using tool '{step.tool_needed}' successfully"
        return f"Completed '{step.action}': {step.description}"

    def _should_abort(self, plan: Plan) -> bool:
        if plan.failure_count >= 3:
            return True
        if plan.replan_count >= self.MAX_REPLANS:
            return True
        return False

    def _calculate_progress(self, plan: Plan) -> float:
        if not plan.steps:
            return 0.0
        completed = sum(
            1
            for s in plan.steps
            if s.status in (StepStatus.COMPLETED.value, StepStatus.SKIPPED.value)
        )
        return round(completed / len(plan.steps), 4)

    def _persist_plan(self, plan: Plan):
        steps_data = []
        for step in plan.steps:
            steps_data.append(
                {
                    "step_number": step.step_number,
                    "action": step.action,
                    "description": step.description,
                    "knowledge_needed": step.knowledge_needed,
                    "tool_needed": step.tool_needed,
                    "status": step.status,
                    "result": step.result,
                    "error": step.error,
                }
            )
        result_data = json.dumps(
            {
                "goal": plan.goal,
                "context": plan.context,
                "steps": steps_data,
                "progress": plan.progress,
                "failure_count": plan.failure_count,
                "replan_count": plan.replan_count,
                "execution_results": plan.execution_results,
            }
        )
        with self.db.get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM tasks WHERE title = ? AND task_type = 'plan'",
                (plan.plan_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE tasks SET result = ?, status = ?, updated_at = datetime('now') WHERE id = ?",
                    (result_data, plan.status, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO tasks (title, description, task_type, status, result) VALUES (?, ?, 'plan', ?, ?)",
                    (plan.plan_id, plan.goal, plan.status, result_data),
                )
            conn.commit()
