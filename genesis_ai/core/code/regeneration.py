"""Regeneration engine — repairs failed code generation attempts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.core.code.code_request import CodeRequest
from genesis_ai.core.code.validator import CodeValidator, ValidationResult, ValidationError, Severity
from genesis_ai.core.code.generator import CodeGenerator


@dataclass
class RepairAttempt:
    """Record of a single repair attempt."""
    error: str
    cause: str
    attempted_fix: str
    successful_fix: Optional[str] = None
    confidence: float = 0.0


@dataclass
class RegenerationResult:
    """Result of a regeneration cycle."""
    success: bool
    files: dict[str, str] = field(default_factory=dict)
    validation: Optional[ValidationResult] = None
    attempts: list[RepairAttempt] = field(default_factory=list)
    generations: int = 0
    metadata: dict = field(default_factory=dict)


class RegenerationEngine:
    """Repairs failed code through error analysis and partial regeneration."""

    def __init__(self, generator: Optional[CodeGenerator] = None, max_attempts: int = 3):
        self._generator = generator or CodeGenerator()
        self._validator = CodeValidator()
        self._max_attempts = max_attempts
        self._experiences: list[dict] = []

    def regenerate(self, files: dict[str, str], validation: ValidationResult,
                   request: Optional[CodeRequest] = None) -> RegenerationResult:
        if validation.valid:
            return RegenerationResult(
                success=True, files=files, validation=validation, generations=1
            )

        current_files = dict(files)
        attempts: list[RepairAttempt] = []

        for attempt_num in range(self._max_attempts):
            errors = validation.errors
            if not errors:
                break

            primary_error = self._select_primary_error(errors)
            fix = self._analyze_and_fix(primary_error, current_files, request)

            if fix:
                attempt = RepairAttempt(
                    error=primary_error.message,
                    cause=primary_error.error_type,
                    attempted_fix=fix.get("description", "auto-fix"),
                    successful_fix=fix.get("description"),
                    confidence=0.7,
                )
                attempts.append(attempt)

                for path, content in fix.get("files", {}).items():
                    current_files[path] = content

                validation = self._validator.validate(current_files, request.language if request else None)

                if validation.valid:
                    self._record_experience(request, attempts, True)
                    return RegenerationResult(
                        success=True, files=current_files, validation=validation,
                        attempts=attempts, generations=attempt_num + 2
                    )
            else:
                break

        self._record_experience(request, attempts, False)
        return RegenerationResult(
            success=False, files=current_files, validation=validation,
            attempts=attempts, generations=self._max_attempts
        )

    def _select_primary_error(self, errors: list[ValidationError]) -> ValidationError:
        severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        return min(errors, key=lambda e: severity_order.get(e.severity, 3))

    def _analyze_and_fix(self, error: ValidationError, files: dict[str, str],
                         request: Optional[CodeRequest] = None) -> Optional[dict]:
        path = error.file_path
        if path not in files:
            return None

        content = files[path]
        fix_type = error.error_type

        if fix_type == "syntax":
            fixed = self._fix_python_syntax(content)
        elif fix_type == "mismatched_braces":
            fixed = self._fix_mismatched_braces(content)
        elif fix_type == "mismatched_parens":
            fixed = self._fix_mismatched_parens(content)
        elif fix_type == "empty_block":
            fixed = self._fix_empty_block(content, error.line)
        elif fix_type == "missing_doctype":
            fixed = self._fix_missing_doctype(content)
        elif fix_type == "json_syntax":
            fixed = self._fix_json_syntax(content)
        else:
            return None

        if fixed and fixed != content:
            return {"files": {path: fixed}, "description": f"Fixed {fix_type}"}
        return None

    def _fix_python_syntax(self, content: str) -> str:
        lines = content.split("\n")
        fixed = []
        prev_indent = 0
        for line in lines:
            stripped = line.rstrip()
            if stripped.endswith("::"):
                fixed.append(stripped[:-1])
            elif stripped and not stripped.startswith("#"):
                indent = len(line) - len(line.lstrip())
                if indent > prev_indent + 8:
                    fixed.append(" " * (prev_indent + 4) + line.lstrip())
                else:
                    fixed.append(line)
                prev_indent = indent
            else:
                fixed.append(line)
        return "\n".join(fixed)

    def _fix_mismatched_braces(self, content: str) -> str:
        diff = content.count("{") - content.count("}")
        if diff > 0:
            return content + "\n" + "}" * diff
        elif diff < 0:
            lines = content.rstrip().split("\n")
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == "}":
                    lines.pop(i)
                    diff += 1
                    if diff == 0:
                        break
            return "\n".join(lines)
        return content

    def _fix_mismatched_parens(self, content: str) -> str:
        diff = content.count("(") - content.count(")")
        if diff > 0:
            return content + ")" * diff
        elif diff < 0:
            return content[:content.rfind(")")]
        return content

    def _fix_empty_block(self, content: str, line_num: Optional[int]) -> str:
        if line_num is None:
            return content
        lines = content.split("\n")
        idx = line_num - 1
        if 0 <= idx < len(lines):
            stripped = lines[idx].rstrip()
            indent = len(lines[idx]) - len(lines[idx].lstrip())
            lines.insert(idx + 1, " " * (indent + 4) + "pass")
        return "\n".join(lines)

    def _fix_missing_doctype(self, content: str) -> str:
        return "<!DOCTYPE html>\n" + content

    def _fix_json_syntax(self, content: str) -> str:
        fixed = content.strip()
        if fixed.endswith(","):
            fixed = fixed[:-1]
        if not fixed.startswith("{"):
            fixed = "{" + fixed
        if not fixed.endswith("}"):
            fixed = fixed + "}"
        try:
            import json
            json.loads(fixed)
            return fixed
        except Exception:
            return content

    def _record_experience(self, request: Optional[CodeRequest], attempts: list[RepairAttempt],
                           success: bool) -> None:
        experience = {
            "task": "code_regeneration",
            "request_type": request.request_type.value if request else "unknown",
            "language": request.language if request else "unknown",
            "success": success,
            "attempt_count": len(attempts),
            "errors": [a.error for a in attempts],
            "fixes": [a.attempted_fix for a in attempts],
        }
        self._experiences.append(experience)

    def get_experiences(self) -> list[dict]:
        return list(self._experiences)
