"""Project planner — decomposes code requests into structured project specifications."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from genesis_ai.core.code.code_request import CodeRequest, RequestType


@dataclass
class ComponentSpec:
    """Specification for a single project component."""
    name: str
    purpose: str
    dependencies: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    implementation_requirements: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class ProjectSpec:
    """Complete project specification produced by ProjectPlanner."""
    request: CodeRequest
    components: list[ComponentSpec] = field(default_factory=list)
    structure: dict[str, list[str]] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    configuration_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    dependencies_list: list[str] = field(default_factory=list)
    generation_order: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class ProjectPlanner:
    """Decomposes a CodeRequest into a structured ProjectSpec."""

    def plan(self, request: CodeRequest) -> ProjectSpec:
        spec = ProjectSpec(request=request)

        if request.request_type == RequestType.CREATE:
            spec = self._plan_creation(request, spec)
        elif request.request_type == RequestType.DEBUG:
            spec = self._plan_debug(request, spec)
        elif request.request_type == RequestType.MODIFY:
            spec = self._plan_modification(request, spec)
        elif request.request_type == RequestType.EXTEND:
            spec = self._plan_extension(request, spec)
        elif request.request_type == RequestType.REFACTOR:
            spec = self._plan_refactor(request, spec)
        elif request.request_type == RequestType.OPTIMIZE:
            spec = self._plan_optimization(request, spec)
        elif request.request_type == RequestType.MIGRATE:
            spec = self._plan_migration(request, spec)

        spec.generation_order = self._determine_generation_order(spec)
        spec.metadata = {
            "request_type": request.request_type.value,
            "language": request.language,
            "framework": request.framework,
            "project_type": request.project_type,
            "component_count": len(spec.components),
        }
        return spec

    def _plan_creation(self, req: CodeRequest, spec: ProjectSpec) -> ProjectSpec:
        lang = req.language or "python"
        ptype = req.project_type or self._infer_project_type(req)

        if ptype == "rest_api":
            spec.components.extend(self._rest_api_components(req, lang))
            spec.structure = self._rest_api_structure(lang)
            spec.entry_points = ["src/main.py" if lang == "python" else "src/index.js"]
            spec.configuration_files = self._config_files(lang)
        elif ptype == "web_app":
            spec.components.extend(self._web_app_components(req, lang))
            spec.structure = self._web_app_structure(lang)
            spec.entry_points = ["src/App.jsx"] if lang in ("javascript", "typescript") else ["src/main.py"]
            spec.configuration_files = self._config_files(lang)
        elif ptype == "cli_tool":
            spec.components.extend(self._cli_components(req, lang))
            spec.structure = self._cli_structure(lang)
            spec.entry_points = ["src/main.py" if lang == "python" else "src/index.js"]
        elif ptype == "library":
            spec.components.extend(self._library_components(req, lang))
            spec.structure = self._library_structure(lang)
        elif ptype == "crawler" or ptype == "scraper":
            spec.components.extend(self._scraper_components(req, lang))
            spec.structure = self._scraper_structure(lang)
            spec.entry_points = ["src/main.py" if lang == "python" else "src/index.js"]
        elif ptype == "ml_model":
            spec.components.extend(self._ml_components(req, lang))
            spec.structure = self._ml_structure(lang)
            spec.entry_points = ["src/main.py"]
        elif ptype == "chatbot":
            spec.components.extend(self._chatbot_components(req, lang))
            spec.structure = self._chatbot_structure(lang)
            spec.entry_points = ["src/main.py" if lang == "python" else "src/index.js"]
        elif ptype == "game":
            spec.components.extend(self._game_components(req, lang))
            spec.structure = self._game_structure(lang)
            spec.entry_points = ["src/main.py" if lang == "python" else "src/index.js"]
        elif ptype == "data_pipeline":
            spec.components.extend(self._data_pipeline_components(req, lang))
            spec.structure = self._data_pipeline_structure(lang)
            spec.entry_points = ["src/main.py"]
        elif ptype == "dashboard":
            spec.components.extend(self._dashboard_components(req, lang))
            spec.structure = self._dashboard_structure(lang)
            spec.entry_points = ["src/App.jsx"] if lang in ("javascript", "typescript") else ["src/app.py"]
        else:
            spec.components.extend(self._generic_components(req, lang))
            spec.structure = self._generic_structure(lang)
            spec.entry_points = ["src/main.py" if lang == "python" else "src/index.js"]

        spec.test_files = self._test_files(lang)
        spec.dependencies_list = self._gather_dependencies(spec, lang)
        return spec

    def _plan_debug(self, req: CodeRequest, spec: ProjectSpec) -> ProjectSpec:
        spec.components.append(ComponentSpec(
            name="error_analysis",
            purpose="Analyze the reported error and identify root cause",
            implementation_requirements=["error parsing", "stack trace analysis"],
        ))
        spec.components.append(ComponentSpec(
            name="fix_generation",
            purpose="Generate the minimal fix for the identified error",
            dependencies=["error_analysis"],
            implementation_requirements=["minimal change principle", "preserve existing behavior"],
        ))
        return spec

    def _plan_modification(self, req: CodeRequest, spec: ProjectSpec) -> ProjectSpec:
        spec.components.append(ComponentSpec(
            name="code_analysis",
            purpose="Analyze existing code structure and behavior",
            implementation_requirements=["AST parsing", "dependency analysis"],
        ))
        spec.components.append(ComponentSpec(
            name="change_specification",
            purpose="Define precise changes needed",
            dependencies=["code_analysis"],
        ))
        spec.components.append(ComponentSpec(
            name="patch_generation",
            purpose="Generate code modifications",
            dependencies=["change_specification"],
            implementation_requirements=["minimal diff", "backward compatibility"],
        ))
        return spec

    def _plan_extension(self, req: CodeRequest, spec: ProjectSpec) -> ProjectSpec:
        spec.components.append(ComponentSpec(
            name="existing_analysis",
            purpose="Understand existing codebase architecture",
        ))
        spec.components.append(ComponentSpec(
            name="feature_design",
            purpose="Design new feature to integrate with existing code",
            dependencies=["existing_analysis"],
        ))
        spec.components.append(ComponentSpec(
            name="integration_generation",
            purpose="Generate new code and integration points",
            dependencies=["feature_design"],
        ))
        return spec

    def _plan_refactor(self, req: CodeRequest, spec: ProjectSpec) -> ProjectSpec:
        spec.components.append(ComponentSpec(
            name="code_analysis",
            purpose="Identify code smells and improvement opportunities",
        ))
        spec.components.append(ComponentSpec(
            name="refactoring_plan",
            purpose="Plan refactoring steps preserving behavior",
            dependencies=["code_analysis"],
        ))
        spec.components.append(ComponentSpec(
            name="refactored_code",
            purpose="Generate refactored code",
            dependencies=["refactoring_plan"],
        ))
        return spec

    def _plan_optimization(self, req: CodeRequest, spec: ProjectSpec) -> ProjectSpec:
        spec.components.append(ComponentSpec(
            name="performance_analysis",
            purpose="Identify performance bottlenecks",
        ))
        spec.components.append(ComponentSpec(
            name="optimization_plan",
            purpose="Design optimization strategy",
            dependencies=["performance_analysis"],
        ))
        spec.components.append(ComponentSpec(
            name="optimized_code",
            purpose="Generate optimized code",
            dependencies=["optimization_plan"],
        ))
        return spec

    def _plan_migration(self, req: CodeRequest, spec: ProjectSpec) -> ProjectSpec:
        spec.components.append(ComponentSpec(
            name="source_analysis",
            purpose="Analyze source code and dependencies",
        ))
        spec.components.append(ComponentSpec(
            name="migration_plan",
            purpose="Map source constructs to target equivalents",
            dependencies=["source_analysis"],
        ))
        spec.components.append(ComponentSpec(
            name="migrated_code",
            purpose="Generate code in target language",
            dependencies=["migration_plan"],
        ))
        return spec

    def _rest_api_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        comps = [
            ComponentSpec(
                name="models",
                purpose="Data models and schemas",
                files=["src/models.py" if lang == "python" else "src/models/index.js"],
                implementation_requirements=["validation", "serialization"],
            ),
            ComponentSpec(
                name="routes",
                purpose="API route handlers",
                dependencies=["models"],
                files=["src/routes.py" if lang == "python" else "src/routes/index.js"],
                implementation_requirements=["RESTful conventions", "error handling"],
            ),
            ComponentSpec(
                name="app",
                purpose="Application entry point and configuration",
                dependencies=["routes"],
                files=["src/main.py" if lang == "python" else "src/index.js"],
            ),
        ]
        has_auth = any("auth" in f for f in req.features) or "security" in req.constraints
        if has_auth:
            comps.insert(1, ComponentSpec(
                name="authentication",
                purpose="Authentication and authorization middleware",
                dependencies=["models"],
                files=["src/auth.py" if lang == "python" else "src/middleware/auth.js"],
                implementation_requirements=["JWT or session", "password hashing"],
            ))
        return comps

    def _web_app_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="components", purpose="UI components", files=["src/components/"]),
            ComponentSpec(name="pages", purpose="Page layouts", dependencies=["components"], files=["src/pages/"]),
            ComponentSpec(name="app", purpose="Root application component", dependencies=["pages"], files=["src/App.jsx"]),
        ]

    def _cli_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="cli_parser", purpose="Command line argument parsing", files=["src/cli.py"]),
            ComponentSpec(name="core_logic", purpose="Core business logic", files=["src/core.py"]),
            ComponentSpec(name="app", purpose="Entry point", dependencies=["cli_parser", "core_logic"], files=["src/main.py"]),
        ]

    def _library_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="core", purpose="Core library functionality", files=["src/core.py"]),
            ComponentSpec(name="utils", purpose="Utility functions", files=["src/utils.py"]),
            ComponentSpec(name="api", purpose="Public API surface", dependencies=["core", "utils"], files=["src/__init__.py"]),
        ]

    def _scraper_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="fetcher", purpose="HTTP fetching with retry/backoff", files=["src/fetcher.py"]),
            ComponentSpec(name="parser", purpose="HTML/content parsing", files=["src/parser.py"]),
            ComponentSpec(name="pipeline", purpose="Data extraction pipeline", dependencies=["fetcher", "parser"], files=["src/pipeline.py"]),
            ComponentSpec(name="app", purpose="Entry point and orchestration", dependencies=["pipeline"], files=["src/main.py"]),
        ]

    def _ml_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="data", purpose="Data loading and preprocessing", files=["src/data.py"]),
            ComponentSpec(name="model", purpose="Model definition and training", dependencies=["data"], files=["src/model.py"]),
            ComponentSpec(name="evaluate", purpose="Evaluation and metrics", dependencies=["model"], files=["src/evaluate.py"]),
            ComponentSpec(name="app", purpose="Entry point", dependencies=["model", "evaluate"], files=["src/main.py"]),
        ]

    def _chatbot_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="nlu", purpose="Natural language understanding", files=["src/nlu.py"]),
            ComponentSpec(name="dialog", purpose="Dialog management", dependencies=["nlu"], files=["src/dialog.py"]),
            ComponentSpec(name="response", purpose="Response generation", dependencies=["dialog"], files=["src/response.py"]),
            ComponentSpec(name="app", purpose="Entry point", dependencies=["response"], files=["src/main.py"]),
        ]

    def _game_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="game_state", purpose="Game state management", files=["src/state.py"]),
            ComponentSpec(name="entities", purpose="Game entities and objects", files=["src/entities.py"]),
            ComponentSpec(name="renderer", purpose="Rendering and display", dependencies=["game_state", "entities"], files=["src/renderer.py"]),
            ComponentSpec(name="app", purpose="Game loop entry point", dependencies=["renderer"], files=["src/main.py"]),
        ]

    def _data_pipeline_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="extract", purpose="Data extraction from sources", files=["src/extract.py"]),
            ComponentSpec(name="transform", purpose="Data transformation logic", dependencies=["extract"], files=["src/transform.py"]),
            ComponentSpec(name="load", purpose="Data loading to destination", dependencies=["transform"], files=["src/load.py"]),
            ComponentSpec(name="app", purpose="Pipeline orchestration", dependencies=["extract", "transform", "load"], files=["src/main.py"]),
        ]

    def _dashboard_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="data_source", purpose="Data fetching and caching", files=["src/data.py"]),
            ComponentSpec(name="components", purpose="Dashboard UI components", files=["src/components/"]),
            ComponentSpec(name="app", purpose="Root application", dependencies=["data_source", "components"], files=["src/App.jsx"]),
        ]

    def _generic_components(self, req: CodeRequest, lang: str) -> list[ComponentSpec]:
        return [
            ComponentSpec(name="core", purpose="Core functionality", files=["src/core.py" if lang == "python" else "src/core.js"]),
            ComponentSpec(name="app", purpose="Entry point", dependencies=["core"], files=["src/main.py" if lang == "python" else "src/index.js"]),
        ]

    def _rest_api_structure(self, lang: str) -> dict[str, list[str]]:
        return {
            "src/": ["models.py", "routes.py", "main.py"],
            "tests/": ["test_routes.py"],
        }

    def _web_app_structure(self, lang: str) -> dict[str, list[str]]:
        return {
            "src/": ["App.jsx", "main.jsx"],
            "src/components/": [],
            "src/pages/": [],
        }

    def _cli_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["cli.py", "core.py", "main.py"]}

    def _library_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["__init__.py", "core.py", "utils.py"]}

    def _scraper_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["fetcher.py", "parser.py", "pipeline.py", "main.py"]}

    def _ml_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["data.py", "model.py", "evaluate.py", "main.py"]}

    def _chatbot_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["nlu.py", "dialog.py", "response.py", "main.py"]}

    def _game_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["state.py", "entities.py", "renderer.py", "main.py"]}

    def _data_pipeline_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["extract.py", "transform.py", "load.py", "main.py"]}

    def _dashboard_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["App.jsx", "main.jsx", "data.py"], "src/components/": []}

    def _generic_structure(self, lang: str) -> dict[str, list[str]]:
        return {"src/": ["core.py", "main.py"]}

    def _config_files(self, lang: str) -> list[str]:
        if lang == "python":
            return ["requirements.txt", "setup.py"]
        if lang in ("javascript", "typescript"):
            return ["package.json"]
        return []

    def _test_files(self, lang: str) -> list[str]:
        if lang == "python":
            return ["tests/test_core.py"]
        return ["tests/test.js"]

    def _infer_project_type(self, req: CodeRequest) -> str:
        msg = req.raw_input.lower()
        if any(w in msg for w in ("api", "endpoint", "route", "rest")):
            return "rest_api"
        if any(w in msg for w in ("app", "web", "frontend", "ui")):
            return "web_app"
        if any(w in msg for w in ("cli", "command line", "terminal")):
            return "cli_tool"
        if any(w in msg for w in ("library", "package", "module")):
            return "library"
        if any(w in msg for w in ("scrape", "crawl", "fetch")):
            return "scraper"
        if any(w in msg for w in ("ml", "model", "train", "predict")):
            return "ml_model"
        return "library"

    def _gather_dependencies(self, spec: ProjectSpec, lang: str) -> list[str]:
        deps = []
        for comp in spec.components:
            for dep in comp.implementation_requirements:
                if dep not in deps:
                    deps.append(dep)
        return deps

    def _determine_generation_order(self, spec: ProjectSpec) -> list[str]:
        if not spec.components:
            return []
        graph: dict[str, list[str]] = {}
        for comp in spec.components:
            graph[comp.name] = comp.dependencies

        ordered: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def dfs(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                return
            visiting.add(node)
            for dep in graph.get(node, []):
                if dep in graph:
                    dfs(dep)
            visiting.discard(node)
            visited.add(node)
            ordered.append(node)

        for name in graph:
            dfs(name)
        return ordered
