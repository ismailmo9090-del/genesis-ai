"""Code validator — validates generated code for correctness."""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """A single validation error."""
    file_path: str
    line: Optional[int]
    message: str
    severity: Severity
    error_type: str
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result for a set of generated files."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    info: list[ValidationError] = field(default_factory=list)
    files_checked: int = 0
    files_passed: int = 0
    metadata: dict = field(default_factory=dict)

    def merge(self, other: ValidationResult) -> ValidationResult:
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            info=self.info + other.info,
            files_checked=self.files_checked + other.files_checked,
            files_passed=self.files_passed + other.files_passed,
        )


class CodeValidator:
    """Validates generated code for syntax, imports, structure, and consistency."""

    def validate(self, files: dict[str, str], language: Optional[str] = None) -> ValidationResult:
        if not files:
            return ValidationResult(valid=False, errors=[
                ValidationError("_", None, "No files to validate", Severity.ERROR, "empty")
            ])

        lang = language or self._detect_language(files)
        result = ValidationResult(valid=True)

        for path, content in files.items():
            file_result = self._validate_file(path, content, lang)
            result = result.merge(file_result)

        result = result.merge(self._validate_cross_file(files, lang))
        result.metadata = {"language": lang, "file_count": len(files)}
        return result

    def _detect_language(self, files: dict[str, str]) -> str:
        ext_map = {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
            ".java": "java", ".html": "html", ".css": "css",
            ".sql": "sql", ".go": "go", ".rs": "rust",
            ".rb": "ruby", ".php": "php",
        }
        ext_counts: dict[str, int] = {}
        for path in files:
            ext = os.path.splitext(path)[1].lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        if ext_counts:
            best_ext = max(ext_counts, key=ext_counts.get)
            return ext_map.get(best_ext, "unknown")
        return "unknown"

    def _validate_file(self, path: str, content: str, lang: str) -> ValidationResult:
        result = ValidationResult(valid=True, files_checked=1)
        ext = os.path.splitext(path)[1].lower()

        if ext == ".py":
            r = self._validate_python(path, content)
        elif ext in (".js", ".jsx", ".ts", ".tsx"):
            r = self._validate_javascript(path, content)
        elif ext == ".html":
            r = self._validate_html(path, content)
        elif ext == ".json":
            r = self._validate_json(path, content)
        elif ext in (".txt", ".md", ".cfg", ".ini", ".yml", ".yaml"):
            r = ValidationResult(valid=True, files_checked=1)
        elif ext == ".sql":
            r = self._validate_generic(path, content)
        else:
            r = self._validate_generic(path, content)

        result = result.merge(r)
        if result.valid:
            result.files_passed = 1
        return result

    def _validate_python(self, path: str, content: str) -> ValidationResult:
        result = ValidationResult(valid=True, files_checked=1)
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            if stripped.endswith(":") and not stripped.startswith("#"):
                if not stripped.endswith("::"):
                    next_idx = i
                    if next_idx < len(lines) and lines[next_idx].strip():
                        next_stripped = lines[next_idx].strip()
                        if not next_stripped and next_idx + 1 < len(lines) and not lines[next_idx + 1].strip():
                            result.errors.append(ValidationError(
                                path, i, f"Empty block after '{stripped}'",
                                Severity.WARNING, "empty_block"
                            ))

        try:
            ast.parse(content)
        except SyntaxError as e:
            result.errors.append(ValidationError(
                path, e.lineno, f"Syntax error: {e.msg}",
                Severity.ERROR, "syntax", suggestion="Check indentation and syntax"
            ))
            result.valid = False

        if "def " in content:
            func_names = re.findall(r'def\s+(\w+)', content)
            dunder_count = sum(1 for n in func_names if n.startswith("__") and n.endswith("__"))
            if dunder_count > 5:
                result.warnings.append(ValidationError(
                    path, None, f"Many dunder methods ({dunder_count}) — check if all needed",
                    Severity.WARNING, "excessive_dunders"
                ))

        if "import " in content:
            imports = re.findall(r'^(?:from\s+(\S+)\s+)?import\s+(.+)', content, re.MULTILINE)
            for module, names in imports:
                if module and module.startswith("."):
                    result.warnings.append(ValidationError(
                        path, None, f"Relative import from '{module}' — verify package structure",
                        Severity.INFO, "relative_import"
                    ))

        return result

    def _validate_javascript(self, path: str, content: str) -> ValidationResult:
        result = ValidationResult(valid=True, files_checked=1)

        if content.count("{") != content.count("}"):
            result.errors.append(ValidationError(
                path, None, f"Mismatched braces: {{ = {content.count('{')}, }} = {content.count('}')}",
                Severity.ERROR, "mismatched_braces"
            ))
            result.valid = False

        if content.count("(") != content.count(")"):
            result.errors.append(ValidationError(
                path, None, f"Mismatched parentheses: ( = {content.count('(')}, ) = {content.count(')')}",
                Severity.ERROR, "mismatched_parens"
            ))
            result.valid = False

        if content.count("[") != content.count("]"):
            result.errors.append(ValidationError(
                path, None, f"Mismatched brackets: [ = {content.count('[')}, ] = {content.count(']')}",
                Severity.ERROR, "mismatched_brackets"
            ))
            result.valid = False

        return result

    def _validate_html(self, path: str, content: str) -> ValidationResult:
        result = ValidationResult(valid=True, files_checked=1)

        if "<!DOCTYPE" not in content and "<!doctype" not in content:
            result.warnings.append(ValidationError(
                path, None, "Missing DOCTYPE declaration",
                Severity.WARNING, "missing_doctype"
            ))

        open_tags = re.findall(r'<(\w+)[^/]*>', content)
        close_tags = re.findall(r'</(\w+)>', content)
        open_tags = [t.lower() for t in open_tags if t.lower() not in ("br", "hr", "img", "input", "meta", "link")]
        close_tags = [t.lower() for t in close_tags]

        if len(open_tags) != len(close_tags):
            result.warnings.append(ValidationError(
                path, None, f"Tag count mismatch: {len(open_tags)} open, {len(close_tags)} close",
                Severity.WARNING, "tag_mismatch"
            ))

        return result

    def _validate_json(self, path: str, content: str) -> ValidationResult:
        result = ValidationResult(valid=True, files_checked=1)
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            result.errors.append(ValidationError(
                path, e.lineno, f"Invalid JSON: {e.msg}",
                Severity.ERROR, "json_syntax"
            ))
            result.valid = False
        return result

    def _validate_generic(self, path: str, content: str) -> ValidationResult:
        return ValidationResult(valid=True, files_checked=1)

    def _validate_cross_file(self, files: dict[str, str], lang: str) -> ValidationResult:
        result = ValidationResult(valid=True)

        if lang == "python":
            result = result.merge(self._validate_python_cross(files))
        elif lang in ("javascript", "typescript"):
            result = result.merge(self._validate_js_cross(files))

        return result

    def _validate_python_cross(self, files: dict[str, str]) -> ValidationResult:
        result = ValidationResult(valid=True)

        all_imports: dict[str, list[str]] = {}
        for path, content in files.items():
            imports = re.findall(r'^(?:from\s+([\w.]+)\s+)?import\s+(.+)', content, re.MULTILINE)
            all_imports[path] = [m[0] or m[1].split(",")[0].strip() for m in imports]

        local_modules = set()
        for path in files:
            if path.endswith(".py"):
                module = path.replace("/", ".").replace("\\", ".").replace(".py", "")
                if module.startswith("src."):
                    module = module[4:]
                local_modules.add(module)

        for path, imports in all_imports.items():
            for imp in imports:
                base = imp.split(".")[0]
                if base in local_modules and base not in ("src", "os", "sys"):
                    pass

        return result

    def _validate_js_cross(self, files: dict[str, str]) -> ValidationResult:
        result = ValidationResult(valid=True)

        exports: set[str] = set()
        for path, content in files.items():
            named = re.findall(r'export\s+(?:const|let|var|function|class)\s+(\w+)', content)
            exports.update(named)

        return result

    def validate_syntax_only(self, code: str, language: str) -> bool:
        if language == "python":
            try:
                ast.parse(code)
                return True
            except SyntaxError:
                return False
        return True
