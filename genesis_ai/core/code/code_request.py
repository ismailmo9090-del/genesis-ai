"""Structured representation of code generation requests."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RequestType(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    EXTEND = "extend"
    REFACTOR = "refactor"
    DEBUG = "debug"
    OPTIMIZE = "optimize"
    MIGRATE = "migrate"


@dataclass
class CodeRequest:
    """Structured representation of a user's coding request."""
    raw_input: str
    request_type: RequestType = RequestType.CREATE
    language: Optional[str] = None
    framework: Optional[str] = None
    platform: Optional[str] = None
    project_type: Optional[str] = None
    user_goal: str = ""
    features: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    security_requirements: list[str] = field(default_factory=list)
    performance_requirements: list[str] = field(default_factory=list)
    deployment_target: Optional[str] = None
    existing_code: Optional[str] = None
    requested_changes: Optional[str] = None

    @classmethod
    def parse(cls, raw: str) -> CodeRequest:
        """Parse a natural language coding request into a structured CodeRequest."""
        msg = raw.lower().strip()
        req = cls(raw_input=raw)

        req.request_type = cls._detect_request_type(msg)
        req.language = cls._detect_language(msg)
        req.framework = cls._detect_framework(msg)
        req.platform = cls._detect_platform(msg)
        req.project_type = cls._detect_project_type(msg)
        req.user_goal = cls._extract_goal(msg, req.request_type)
        req.features = cls._extract_features(msg)
        req.constraints = cls._extract_constraints(msg)
        req.dependencies = cls._extract_dependencies(msg)
        req.inputs = cls._extract_inputs(msg)
        req.outputs = cls._extract_outputs(msg)

        return req

    @staticmethod
    def _detect_request_type(msg: str) -> RequestType:
        if any(w in msg for w in ("fix", "debug", "error", "bug", "broken", "doesn't work")):
            return RequestType.DEBUG
        if any(w in msg for w in ("optimize", "faster", "performance", "speed up")):
            return RequestType.OPTIMIZE
        if any(w in msg for w in ("refactor", "restructure", "clean up", "reorganize")):
            return RequestType.REFACTOR
        if any(w in msg for w in ("add", "extend", "enhance", "improve", "new feature")):
            return RequestType.EXTEND
        if any(w in msg for w in ("migrate", "convert", "port", "switch to")):
            return RequestType.MIGRATE
        if any(w in msg for w in ("modify", "change", "update", "alter")):
            return RequestType.MODIFY
        return RequestType.CREATE

    @staticmethod
    def _detect_language(msg: str) -> Optional[str]:
        langs = {
            "python": "python", "py": "python",
            "javascript": "javascript", "js": "javascript",
            "typescript": "typescript", "ts": "typescript",
            "java": "java",
            "c++": "cpp", "cpp": "cpp",
            "c#": "csharp", "csharp": "csharp",
            "rust": "rust",
            "go": "go", "golang": "go",
            "ruby": "ruby",
            "php": "php",
            "html": "html",
            "css": "css",
            "sql": "sql",
            "swift": "swift",
            "kotlin": "kotlin",
            "scala": "scala",
            "r": "r",
            "matlab": "matlab",
            "shell": "shell", "bash": "shell",
        }
        for key, lang in langs.items():
            if re.search(r'\b' + re.escape(key) + r'\b', msg):
                return lang
        # Infer from framework
        js_frameworks = ("react", "vue", "angular", "svelte", "express", "next", "nextjs")
        for fw in js_frameworks:
            if re.search(r'\b' + re.escape(fw) + r'\b', msg):
                return "javascript"
        return None

    @staticmethod
    def _detect_framework(msg: str) -> Optional[str]:
        frameworks = {
            "flask": "flask", "django": "django", "fastapi": "fastapi",
            "express": "express", "next": "nextjs", "nextjs": "nextjs",
            "react": "react", "vue": "vue", "angular": "angular",
            "svelte": "svelte",
            "spring": "spring", "springboot": "spring",
            "rails": "rails", "sinatra": "sinatra",
            "laravel": "laravel", "symfony": "symfony",
            "tensorflow": "tensorflow", "pytorch": "pytorch",
            "pandas": "pandas", "numpy": "numpy",
            "gin": "gin", "fiber": "fiber",
            "actix": "actix", "rocket": "rocket",
        }
        for key, fw in frameworks.items():
            if re.search(r'\b' + re.escape(key) + r'\b', msg):
                return fw
        return None

    @staticmethod
    def _detect_platform(msg: str) -> Optional[str]:
        platforms = {
            "web": "web", "mobile": "mobile", "desktop": "desktop",
            "cli": "cli", "api": "api", "server": "server",
            "cloud": "cloud", "aws": "aws", "gcp": "gcp",
            "azure": "azure", "docker": "docker", "kubernetes": "k8s",
            "linux": "linux", "windows": "windows", "macos": "macos",
        }
        for key, plat in platforms.items():
            if re.search(r'\b' + re.escape(key) + r'\b', msg):
                return plat
        return None

    @staticmethod
    def _detect_project_type(msg: str) -> Optional[str]:
        types = {
            "rest api": "rest_api", "restapi": "rest_api",
            "graphql": "graphql", "web app": "web_app", "webapp": "web_app",
            "mobile app": "mobile_app", "cli tool": "cli_tool",
            "library": "library", "package": "library",
            "microservice": "microservice", "monolith": "monolith",
            "crawler": "crawler", "scraper": "scraper",
            "chatbot": "chatbot", "game": "game",
            "dashboard": "dashboard", "admin panel": "dashboard",
            "data pipeline": "data_pipeline", "etl": "data_pipeline",
            "machine learning": "ml_model", "ml model": "ml_model",
        }
        for key, ptype in types.items():
            if re.search(r'\b' + re.escape(key) + r'\b', msg):
                return ptype
        return None

    @staticmethod
    def _extract_goal(msg: str, req_type: RequestType) -> str:
        prefixes = [
            r'create\s+a\s+', r'build\s+a\s+', r'write\s+a\s+',
            r'make\s+a\s+', r'develop\s+a\s+', r'implement\s+a\s+',
            r'generate\s+a\s+', r'design\s+a\s+',
            r'add\s+\w+\s+to\s+', r'fix\s+the\s+', r'optimize\s+the\s+',
            r'refactor\s+the\s+', r'modify\s+the\s+',
        ]
        for prefix in prefixes:
            match = re.search(prefix, msg)
            if match:
                return msg[match.end():].strip()
        return msg

    @staticmethod
    def _extract_features(msg: str) -> list[str]:
        features = []
        feature_patterns = [
            r'with\s+(.+?)(?:\s+(?:and|for|to|that|in)\b|$)',
            r'including\s+(.+?)(?:\s+(?:and|for|to|that|in)\b|$)',
            r'features?\s+(?:like|such as)\s+(.+?)(?:\s+(?:and|for|to|that|in)\b|$)',
        ]
        for pattern in feature_patterns:
            matches = re.findall(pattern, msg)
            for m in matches:
                features.extend([f.strip() for f in re.split(r'\s+and\s+|\s*,\s*', m)])
        return features[:10]

    @staticmethod
    def _extract_constraints(msg: str) -> list[str]:
        constraints = []
        if any(w in msg for w in ("no external", "without", "no dependencies")):
            constraints.append("minimize_dependencies")
        if "async" in msg:
            constraints.append("async_required")
        if any(w in msg for w in ("fast", "efficient", "performance")):
            constraints.append("performance_critical")
        if any(w in msg for w in ("secure", "security", "auth")):
            constraints.append("security_required")
        return constraints

    @staticmethod
    def _extract_dependencies(msg: str) -> list[str]:
        deps = []
        dep_match = re.findall(r'using\s+([\w\s,]+?)(?:\s+(?:and|for|to|with)\b|$)', msg)
        for m in dep_match:
            deps.extend([d.strip() for d in re.split(r'\s*,\s*|\s+and\s+', m)])
        return deps[:10]

    @staticmethod
    def _extract_inputs(msg: str) -> list[str]:
        inputs = []
        if "user input" in msg or "from user" in msg:
            inputs.append("user_input")
        if "stdin" in msg or "command line" in msg or "cli" in msg:
            inputs.append("cli_input")
        if "file" in msg and ("read" in msg or "load" in msg):
            inputs.append("file_input")
        if "api" in msg and ("request" in msg or "call" in msg):
            inputs.append("api_input")
        return inputs

    @staticmethod
    def _extract_outputs(msg: str) -> list[str]:
        outputs = []
        if "print" in msg or "console" in msg or "stdout" in msg:
            outputs.append("console_output")
        if "file" in msg and ("write" in msg or "save" in msg):
            outputs.append("file_output")
        if "return" in msg or "response" in msg:
            outputs.append("return_value")
        return outputs
