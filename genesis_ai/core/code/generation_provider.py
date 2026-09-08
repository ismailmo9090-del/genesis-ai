"""Generation provider interface — abstraction for code generation backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.core.code.code_request import CodeRequest
from genesis_ai.core.code.planner import ProjectSpec


@dataclass
class GenerationResult:
    """Result from a generation provider."""
    success: bool
    files: dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    provider: str = "unknown"
    metadata: dict = field(default_factory=dict)


class GenerationProvider(ABC):
    """Abstract interface for code generation backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is currently available."""

    @abstractmethod
    def generate_from_request(self, request: CodeRequest) -> GenerationResult:
        """Generate code from a parsed request."""

    @abstractmethod
    def generate_from_spec(self, spec: ProjectSpec) -> GenerationResult:
        """Generate code from a project specification."""

    @abstractmethod
    def repair(self, files: dict[str, str], errors: list[str], request: CodeRequest) -> GenerationResult:
        """Attempt to repair broken code."""


class LocalProvider(GenerationProvider):
    """Local code generation using Genesis's built-in generator."""

    def __init__(self):
        from genesis_ai.core.code.generator import CodeGenerator
        self._generator = CodeGenerator()

    @property
    def name(self) -> str:
        return "local"

    @property
    def is_available(self) -> bool:
        return True

    def generate_from_request(self, request: CodeRequest) -> GenerationResult:
        try:
            files = self._generator.generate_from_request(request)
            return GenerationResult(
                success=True, files=files, provider=self.name,
                metadata={"method": "template_composition"}
            )
        except Exception as e:
            return GenerationResult(success=False, error=str(e), provider=self.name)

    def generate_from_spec(self, spec: ProjectSpec) -> GenerationResult:
        try:
            files = self._generator.generate_from_spec(spec)
            return GenerationResult(
                success=True, files=files, provider=self.name,
                metadata={"method": "spec_composition"}
            )
        except Exception as e:
            return GenerationResult(success=False, error=str(e), provider=self.name)

    def repair(self, files: dict[str, str], errors: list[str], request: CodeRequest) -> GenerationResult:
        try:
            from genesis_ai.core.code.regeneration import RegenerationEngine
            from genesis_ai.core.code.validator import CodeValidator
            validator = CodeValidator()
            validation = validator.validate(files, request.language)
            engine = RegenerationEngine(self._generator)
            result = engine.regenerate(files, validation, request)
            return GenerationResult(
                success=result.success, files=result.files, provider=self.name,
                metadata={"repair_attempts": len(result.attempts)}
            )
        except Exception as e:
            return GenerationResult(success=False, error=str(e), provider=self.name)


class ExternalProvider(GenerationProvider):
    """Placeholder for external LLM API provider."""

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self._api_url = api_url
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "external"

    @property
    def is_available(self) -> bool:
        return self._api_url is not None and self._api_key is not None

    def generate_from_request(self, request: CodeRequest) -> GenerationResult:
        return GenerationResult(
            success=False, error="External provider not configured", provider=self.name
        )

    def generate_from_spec(self, spec: ProjectSpec) -> GenerationResult:
        return GenerationResult(
            success=False, error="External provider not configured", provider=self.name
        )

    def repair(self, files: dict[str, str], errors: list[str], request: CodeRequest) -> GenerationResult:
        return GenerationResult(
            success=False, error="External provider not configured", provider=self.name
        )


class HybridProvider(GenerationProvider):
    """Provider that tries local first, then external if available."""

    def __init__(self, local: Optional[LocalProvider] = None, external: Optional[ExternalProvider] = None):
        self._local = local or LocalProvider()
        self._external = external or ExternalProvider()

    @property
    def name(self) -> str:
        return "hybrid"

    @property
    def is_available(self) -> bool:
        return self._local.is_available or self._external.is_available

    def generate_from_request(self, request: CodeRequest) -> GenerationResult:
        if self._local.is_available:
            result = self._local.generate_from_request(request)
            if result.success:
                return result
        if self._external.is_available:
            return self._external.generate_from_request(request)
        return GenerationResult(success=False, error="No providers available", provider=self.name)

    def generate_from_spec(self, spec: ProjectSpec) -> GenerationResult:
        if self._local.is_available:
            result = self._local.generate_from_spec(spec)
            if result.success:
                return result
        if self._external.is_available:
            return self._external.generate_from_spec(spec)
        return GenerationResult(success=False, error="No providers available", provider=self.name)

    def repair(self, files: dict[str, str], errors: list[str], request: CodeRequest) -> GenerationResult:
        if self._local.is_available:
            result = self._local.repair(files, errors, request)
            if result.success:
                return result
        if self._external.is_available:
            return self._external.repair(files, errors, request)
        return GenerationResult(success=False, error="No providers available", provider=self.name)
