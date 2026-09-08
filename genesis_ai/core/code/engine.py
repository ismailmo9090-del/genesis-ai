"""Code generation engine — orchestrates the full code generation pipeline."""
from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.core.code.code_request import CodeRequest, RequestType
from genesis_ai.core.code.planner import ProjectPlanner, ProjectSpec
from genesis_ai.core.code.knowledge_provider import KnowledgeProvider, InternalKnowledgeProvider
from genesis_ai.core.code.generator import CodeGenerator
from genesis_ai.core.code.validator import CodeValidator, ValidationResult
from genesis_ai.core.code.regeneration import RegenerationEngine, RegenerationResult
from genesis_ai.core.code.generation_provider import (
    GenerationProvider, LocalProvider, HybridProvider, GenerationResult
)

KNOWLEDGE_PROVIDER_MODES = ("internal", "network", "hybrid")


def _build_knowledge_provider(mode: Optional[str] = None) -> KnowledgeProvider:
    if mode is None:
        mode = os.environ.get("GENESIS_KNOWLEDGE_MODE", "hybrid")
    mode = mode.lower()
    if mode not in KNOWLEDGE_PROVIDER_MODES:
        mode = "hybrid"

    if mode == "internal":
        return InternalKnowledgeProvider()

    from genesis_ai.core.code.genesis_knowledge_provider import GenesisKnowledgeProvider
    network_url = os.environ.get("GENESIS_KNOWLEDGE_URL", "http://127.0.0.1:8000")
    gp = GenesisKnowledgeProvider(network_url=network_url)

    if mode == "network":
        return gp
    return gp


@dataclass
class GenerationResponse:
    """Complete response from the code generation engine."""
    success: bool
    request_type: str = ""
    project_type: str = ""
    language: str = ""
    files: dict[str, str] = field(default_factory=dict)
    plan: Optional[ProjectSpec] = None
    validation: Optional[ValidationResult] = None
    regeneration: Optional[RegenerationResult] = None
    generation_time_ms: float = 0
    provider: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    knowledge_items_used: int = 0
    knowledge_types: list[str] = field(default_factory=list)
    knowledge_provider: str = "internal"

    def to_dict(self) -> dict:
        result = {
            "success": self.success,
            "request_type": self.request_type,
            "project_type": self.project_type,
            "language": self.language,
            "files": self.files,
            "generation_time_ms": self.generation_time_ms,
            "provider": self.provider,
            "warnings": self.warnings,
            "errors": self.errors,
            "knowledge_provider": self.knowledge_provider,
            "knowledge_items_used": self.knowledge_items_used,
            "knowledge_types": self.knowledge_types,
        }
        if self.plan:
            result["plan"] = {
                "components": [
                    {"name": c.name, "purpose": c.purpose, "files": c.files}
                    for c in self.plan.components
                ],
                "structure": self.plan.structure,
                "entry_points": self.plan.entry_points,
                "generation_order": self.plan.generation_order,
            }
        if self.validation:
            result["validation"] = {
                "valid": self.validation.valid,
                "files_checked": self.validation.files_checked,
                "files_passed": self.validation.files_passed,
                "error_count": len(self.validation.errors),
                "warning_count": len(self.validation.warnings),
            }
        if self.regeneration:
            result["regeneration"] = {
                "success": self.regeneration.success,
                "generations": self.regeneration.generations,
                "attempts": [
                    {"error": a.error, "cause": a.cause, "fix": a.attempted_fix}
                    for a in self.regeneration.attempts
                ],
            }
        return result

    def to_markdown(self) -> str:
        parts = []
        parts.append(f"# Code Generation {'Succeeded' if self.success else 'Failed'}\n")
        parts.append(f"- **Request Type:** {self.request_type}")
        parts.append(f"- **Project Type:** {self.project_type}")
        parts.append(f"- **Language:** {self.language}")
        parts.append(f"- **Provider:** {self.provider}")
        parts.append(f"- **Generation Time:** {self.generation_time_ms:.0f}ms\n")

        if self.plan:
            parts.append("## Project Plan\n")
            for comp in self.plan.components:
                parts.append(f"### {comp.name}\n{comp.purpose}\n")
                if comp.files:
                    parts.append(f"Files: {', '.join(comp.files)}\n")

        if self.files:
            parts.append("## Generated Files\n")
            for path in sorted(self.files.keys()):
                parts.append(f"### `{path}`\n```{self.language}\n{self.files[path]}\n```\n")

        if self.validation:
            parts.append("## Validation\n")
            parts.append(f"- Valid: {self.validation.valid}")
            parts.append(f"- Files Checked: {self.validation.files_checked}")
            parts.append(f"- Files Passed: {self.validation.files_passed}")
            if self.validation.errors:
                parts.append(f"- Errors: {len(self.validation.errors)}")
                for err in self.validation.errors[:5]:
                    parts.append(f"  - {err.file_path}:{err.line or '?'} — {err.message}")

        if self.warnings:
            parts.append("\n## Warnings\n")
            for w in self.warnings:
                parts.append(f"- {w}")

        return "\n".join(parts)


class CodeGenerationEngine:
    """Main orchestrator for code generation pipeline."""

    def __init__(self, provider: Optional[GenerationProvider] = None,
                 knowledge_provider: Optional[KnowledgeProvider] = None,
                 knowledge_mode: Optional[str] = None):
        self._provider = provider or LocalProvider()
        self._kp = knowledge_provider or _build_knowledge_provider(knowledge_mode)
        self._planner = ProjectPlanner()
        self._validator = CodeValidator()
        self._generator = CodeGenerator(self._kp)
        self._regen_engine = RegenerationEngine(self._generator)
        self._history: list[GenerationResponse] = []

    def generate(self, request_str: str, language: Optional[str] = None,
                 framework: Optional[str] = None, project_type: Optional[str] = None) -> GenerationResponse:
        start = time.time()

        request = CodeRequest.parse(request_str)
        if language:
            request.language = language
        if framework:
            request.framework = framework
        if project_type:
            request.project_type = project_type

        response = self._execute_pipeline(request)
        response.generation_time_ms = (time.time() - start) * 1000
        self._history.append(response)
        return response

    def modify(self, existing_code: str, changes: str, language: Optional[str] = None) -> GenerationResponse:
        request = CodeRequest(
            raw_input=f"Modify code: {changes}",
            request_type=RequestType.MODIFY,
            existing_code=existing_code,
            requested_changes=changes,
            language=language,
        )
        return self._execute_pipeline(request)

    def debug(self, code: str, error: str, language: Optional[str] = None) -> GenerationResponse:
        request = CodeRequest(
            raw_input=f"Debug error: {error}",
            request_type=RequestType.DEBUG,
            existing_code=code,
            requested_changes=error,
            language=language,
        )
        return self._execute_pipeline(request)

    def _execute_pipeline(self, request: CodeRequest) -> GenerationResponse:
        response = GenerationResponse(
            success=False,
            request_type=request.request_type.value,
            language=request.language or "unknown",
        )

        kp_name = type(self._kp).__name__
        response.knowledge_provider = "network" if "Genesis" in kp_name else "internal"

        try:
            spec = self._planner.plan(request)
            response.plan = spec
            response.project_type = spec.request.project_type or "generic"

            query = f"{request.raw_input} {request.language or ''} {request.framework or ''}".strip()
            knowledge_items = self._kp.search_knowledge(query, language=request.language, limit=10)
            response.knowledge_items_used = len(knowledge_items)
            response.knowledge_types = list(set(
                type(k).__name__ for k in knowledge_items
            ))

            gen_result = self._provider.generate_from_request(request)
            response.provider = self._provider.name

            if gen_result.success:
                response.files = gen_result.files

                validation = self._validator.validate(gen_result.files, request.language)
                response.validation = validation

                if not validation.valid:
                    regen = self._regen_engine.regenerate(gen_result.files, validation, request)
                    response.regeneration = regen
                    if regen.success:
                        response.files = regen.files
                        validation = self._validator.validate(regen.files, request.language)
                        response.validation = validation

                response.success = validation.valid
                if validation.warnings:
                    response.warnings = [w.message for w in validation.warnings]
            else:
                response.errors.append(gen_result.error or "Generation failed")
                if gen_result.error:
                    response.errors.append(gen_result.error)

        except Exception as e:
            response.errors.append(f"Pipeline error: {e}")
            response.metadata["traceback"] = traceback.format_exc()

        return response

    def validate_files(self, files: dict[str, str], language: Optional[str] = None) -> ValidationResult:
        return self._validator.validate(files, language)

    def get_history(self) -> list[GenerationResponse]:
        return list(self._history)

    def get_provider(self) -> GenerationProvider:
        return self._provider

    def set_provider(self, provider: GenerationProvider) -> None:
        self._provider = provider
