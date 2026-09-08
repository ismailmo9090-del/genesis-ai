"""Generation provider interface — abstraction for code generation backends."""
from __future__ import annotations

import json
import logging
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.core.code.code_request import CodeRequest
from genesis_ai.core.code.planner import ProjectSpec

logger = logging.getLogger(__name__)


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


class DeepBridgeProvider(GenerationProvider):
    """Code generation via DeepBridge (local DeepSeek)."""

    def __init__(self, api_url: str = "http://127.0.0.1:8899/chat", timeout: int = 120):
        self._api_url = api_url
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "deepbridge"

    @property
    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8899/",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            return False

    def _call_deepbridge(self, prompt: str, system: Optional[str] = None) -> str:
        """Call DeepBridge and return response text."""
        payload = {"prompt": prompt}
        if system:
            payload["system"] = system
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self._api_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            result = json.loads(resp.read().decode())
            return result.get("response", "")

    def _build_generation_prompt(self, spec: ProjectSpec) -> str:
        """Build a structured prompt from ProjectSpec."""
        req = spec.request
        goal = req.user_goal
        features = ", ".join(req.features)
        files_needed = []
        for comp in spec.components:
            files_needed.extend(comp.files)

        # Generate each file separately for better formatting
        prompts = []
        for path in files_needed:
            prompt = (
                "Generate the file " + path + " for a " + (req.framework or "Python") + " project.\n\n"
                "Goal: " + goal + "\n"
                "Features: " + features + "\n\n"
                "IMPORTANT: Generate ONLY valid Python code. "
                "Each statement must be on its own line. "
                "Include proper indentation (4 spaces). "
                "Include blank lines between functions and classes.\n\n"
                "Return ONLY the complete file content, no explanations.\n"
            )
            prompts.append(prompt)

        # Combine into single prompt
        combined = "Generate the following files for a " + (req.framework or "Python") + " project.\n\n"
        combined += "Goal: " + goal + "\n"
        combined += "Features: " + features + "\n\n"
        combined += "For EACH file below, generate the complete file content.\n"
        combined += "Return each file in this format:\n"
        combined += "=== FILENAME: path/to/file ===\n"
        combined += "file content here\n"
        combined += "=== END FILENAME ===\n\n"
        combined += "CRITICAL FORMATTING RULES:\n"
        combined += "1. Each import statement must be on its own line\n"
        combined += "2. Each class attribute must be on its own line\n"
        combined += "3. Each method must be properly indented\n"
        combined += "4. Include blank lines between imports, functions, and classes\n"
        combined += "5. Never compress multiple statements onto one line\n\n"
        combined += "Files to generate:\n"
        for path in files_needed:
            combined += "- " + path + "\n"

        return combined

    def _parse_response(self, response: str) -> dict[str, str]:
        """Parse DeepBridge response into file dict."""
        files = {}
        # Try JSON format first
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Check if response is just the prompt template
        if "CRITICAL FORMATTING RULES" in response or "=== FILENAME: path/to/file ===" in response:
            return files

        # Try === FILENAME: ... === format
        import re
        # Pattern handles both:
        # === FILENAME: path ===\ncontent
        # === FILENAME: path ===content (no newline after marker)
        pattern = r'=== FILENAME:\s*(.+?)\s*===(.*?)(?==== FILENAME:|$)'
        matches = re.findall(pattern, response, re.DOTALL)

        for path, content in matches:
            path = path.strip()
            content = content.strip()
            # Remove trailing === END FILENAME === if present
            if content.endswith("=== END FILENAME ==="):
                content = content[:-len("=== END FILENAME ===")].strip()
            if path and content:
                # Fix: if content has no newlines, try to add them
                if "\n" not in content and path.endswith(".py"):
                    content = self._fix_python_newlines(content)
                files[path] = content

        return files

    def _fix_python_newlines(self, code: str) -> str:
        """Add newlines between Python statements when they're missing."""
        import re
        try:
            import black
            # First try to format with black
            try:
                formatted = black.format_str(code, mode=black.FileMode())
                return formatted
            except black.NoEnemy:
                pass
            except Exception:
                pass
        except ImportError:
            pass

        result = code

        # Step 1: Add newlines before Python keywords that start statements
        keywords = [
            'import', 'from', 'class', 'def', 'return', 'if', 'elif', 'else',
            'for', 'while', 'try', 'except', 'finally', 'with', 'as', 'yield',
            'raise', 'pass', 'break', 'continue', 'assert', 'del', 'global',
            'nonlocal', 'lambda', 'and', 'or', 'not', 'in', 'is', 'None',
            'True', 'False', 'self', '@'
        ]

        # Add newline before each keyword when it follows a non-whitespace character
        for kw in keywords:
            pattern = r'([^\s\n])(' + re.escape(kw) + r'\s)'
            result = re.sub(pattern, r'\1\n\2', result)

        # Step 2: Add newlines after colons (for class/def/if/etc.)
        result = re.sub(r':\s*(\w)', r':\n\1', result)

        # Step 3: Add indentation based on context
        lines = result.split('\n')
        indented_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                indented_lines.append('')
                continue

            # Decrease indent for certain keywords
            if stripped.startswith(('return', 'elif', 'else', 'except', 'finally')):
                indent_level = max(0, indent_level - 1)

            # Add indentation
            indented_lines.append('    ' * indent_level + stripped)

            # Increase indent after colons
            if stripped.endswith(':'):
                indent_level += 1

            # Reset indent for top-level statements
            if stripped.startswith(('import', 'from', 'class', 'def', '@')):
                indent_level = 0

        result = '\n'.join(indented_lines)

        # Clean up multiple newlines
        result = re.sub(r'\n{3,}', '\n\n', result)

        # Remove leading/trailing whitespace
        result = result.strip()

        return result

    def generate_from_request(self, request: CodeRequest) -> GenerationResult:
        try:
            from genesis_ai.core.code.planner import ProjectPlanner
            planner = ProjectPlanner()
            spec = planner.plan(request)
            prompt = self._build_generation_prompt(spec)
            response = self._call_deepbridge(prompt)
            files = self._parse_response(response)
            if not files:
                return GenerationResult(
                    success=False,
                    error="DeepBridge returned no parseable files",
                    provider=self.name,
                    metadata={"raw_response_length": len(response)}
                )
            return GenerationResult(
                success=True, files=files, provider=self.name,
                metadata={"method": "deepbridge_generation", "files_count": len(files)}
            )
        except Exception as e:
            return GenerationResult(success=False, error=str(e), provider=self.name)

    def generate_from_spec(self, spec: ProjectSpec) -> GenerationResult:
        try:
            prompt = self._build_generation_prompt(spec)
            response = self._call_deepbridge(prompt)
            files = self._parse_response(response)
            if not files:
                return GenerationResult(
                    success=False,
                    error="DeepBridge returned no parseable files",
                    provider=self.name,
                    metadata={"raw_response_length": len(response)}
                )
            return GenerationResult(
                success=True, files=files, provider=self.name,
                metadata={"method": "deepbridge_spec_generation", "files_count": len(files)}
            )
        except Exception as e:
            return GenerationResult(success=False, error=str(e), provider=self.name)

    def repair(self, files: dict[str, str], errors: list[str], request: CodeRequest) -> GenerationResult:
        try:
            error_text = "\n".join(errors)
            prompt = (
                "Fix the following code errors:\n\n"
                f"Errors:\n{error_text}\n\n"
                "Original files:\n"
            )
            for path, content in files.items():
                prompt += f"\n--- {path} ---\n{content}\n"

            prompt += "\nReturn the corrected files using the same === FILENAME: ... === format."

            response = self._call_deepbridge(prompt)
            fixed_files = self._parse_response(response)

            merged = dict(files)
            merged.update(fixed_files)

            return GenerationResult(
                success=True, files=merged, provider=self.name,
                metadata={"method": "deepbridge_repair", "fixed_files": list(fixed_files.keys())}
            )
        except Exception as e:
            return GenerationResult(success=False, error=str(e), provider=self.name)


class HybridProvider(GenerationProvider):
    """Provider that tries DeepBridge first, then local, then external."""

    def __init__(self, local: Optional[LocalProvider] = None, external: Optional[ExternalProvider] = None, deepbridge: Optional[DeepBridgeProvider] = None):
        self._local = local or LocalProvider()
        self._external = external or ExternalProvider()
        self._deepbridge = deepbridge or DeepBridgeProvider()

    @property
    def name(self) -> str:
        return "hybrid"

    @property
    def is_available(self) -> bool:
        return self._deepbridge.is_available or self._local.is_available or self._external.is_available

    def generate_from_request(self, request: CodeRequest) -> GenerationResult:
        if self._deepbridge.is_available:
            result = self._deepbridge.generate_from_request(request)
            if result.success:
                return result
        if self._local.is_available:
            result = self._local.generate_from_request(request)
            if result.success:
                return result
        if self._external.is_available:
            return self._external.generate_from_request(request)
        return GenerationResult(success=False, error="No providers available", provider=self.name)

    def generate_from_spec(self, spec: ProjectSpec) -> GenerationResult:
        if self._deepbridge.is_available:
            result = self._deepbridge.generate_from_spec(spec)
            if result.success:
                return result
        if self._local.is_available:
            result = self._local.generate_from_spec(spec)
            if result.success:
                return result
        if self._external.is_available:
            return self._external.generate_from_spec(spec)
        return GenerationResult(success=False, error="No providers available", provider=self.name)

    def repair(self, files: dict[str, str], errors: list[str], request: CodeRequest) -> GenerationResult:
        if self._deepbridge.is_available:
            result = self._deepbridge.repair(files, errors, request)
            if result.success:
                return result
        if self._local.is_available:
            result = self._local.repair(files, errors, request)
            if result.success:
                return result
        if self._external.is_available:
            return self._external.repair(files, errors, request)
        return GenerationResult(success=False, error="No providers available", provider=self.name)
