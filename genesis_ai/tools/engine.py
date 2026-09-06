"""Tool engine for registering, executing, and managing tools with safety controls."""

import ast
import math
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from genesis_ai.database.db import DatabaseManager


class DangerLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolDefinition:
    name: str
    description: str
    function: Callable
    danger_level: str = DangerLevel.LOW
    permissions_required: list[str] = field(default_factory=list)
    enabled: bool = True
    usage_count: int = 0
    last_used: Optional[str] = None
    avg_duration_ms: float = 0.0


@dataclass
class ToolResult:
    success: bool
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    requires_confirmation: bool = False


class ToolEngine:
    """Manages tool registration, execution, safety controls, and rate limiting."""

    RATE_LIMIT_WINDOW = 60
    MAX_EXECUTIONS_PER_WINDOW = 30
    EXECUTION_TIMEOUT = 30

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._tools: dict[str, ToolDefinition] = {}
        self._execution_history: list[dict] = []
        self._execution_counts: dict[str, list[float]] = defaultdict(list)
        self._register_builtins()

    def register_tool(
        self,
        name: str,
        description: str,
        function: Callable,
        danger_level: str = DangerLevel.LOW,
        permissions_required: list[str] = None,
    ) -> bool:
        if name in self._tools:
            return False
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            function=function,
            danger_level=danger_level,
            permissions_required=permissions_required or [],
        )
        return True

    def execute_tool(
        self,
        tool_name: str,
        params: dict = None,
        user_confirmed: bool = False,
    ) -> ToolResult:
        params = params or {}
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' not found",
            )
        if not tool.enabled:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' is disabled",
            )
        if tool.danger_level == DangerLevel.HIGH and not user_confirmed:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                requires_confirmation=True,
                error="High-danger tool requires user confirmation",
            )
        if not self._check_rate_limit(tool_name):
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error="Rate limit exceeded. Please wait before retrying.",
            )
        start_time = time.time()
        try:
            result = tool.function(**params)
            elapsed = int((time.time() - start_time) * 1000)
            self._record_execution(tool_name, elapsed, True)
            return ToolResult(
                success=True,
                tool_name=tool_name,
                result=result,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.time() - start_time) * 1000)
            self._record_execution(tool_name, elapsed, False)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=str(e),
                duration_ms=elapsed,
            )

    def list_tools(self) -> list[dict]:
        tools = []
        for name, tool in self._tools.items():
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "danger_level": tool.danger_level,
                    "permissions_required": tool.permissions_required,
                    "enabled": tool.enabled,
                    "usage_count": tool.usage_count,
                    "last_used": tool.last_used,
                    "avg_duration_ms": tool.avg_duration_ms,
                }
            )
        return tools

    def get_tool(self, tool_name: str) -> Optional[dict]:
        tool = self._tools.get(tool_name)
        if not tool:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "danger_level": tool.danger_level,
            "permissions_required": tool.permissions_required,
            "enabled": tool.enabled,
            "usage_count": tool.usage_count,
        }

    def enable_tool(self, tool_name: str) -> bool:
        tool = self._tools.get(tool_name)
        if not tool:
            return False
        tool.enabled = True
        return True

    def disable_tool(self, tool_name: str) -> bool:
        tool = self._tools.get(tool_name)
        if not tool:
            return False
        tool.enabled = False
        return True

    def get_usage_stats(self) -> dict:
        stats = {}
        for name, tool in self._tools.items():
            db_stats = self.db.get_tool_stats(name)
            stats[name] = {
                "total_executions": db_stats.get("total", 0),
                "successes": db_stats.get("successes", 0),
                "failures": db_stats.get("failures", 0),
                "avg_duration_ms": db_stats.get("avg_duration_ms", 0),
                "danger_level": tool.danger_level,
            }
        return stats

    def _register_builtins(self):
        self.register_tool(
            name="calculator",
            description="Evaluate mathematical expressions safely",
            function=self._builtin_calculator,
            danger_level=DangerLevel.LOW,
        )
        self.register_tool(
            name="python_exec",
            description="Execute safe Python expressions (no imports, no exec, no eval)",
            function=self._builtin_python_exec,
            danger_level=DangerLevel.MEDIUM,
        )
        self.register_tool(
            name="file_read",
            description="Read contents of a file",
            function=self._builtin_file_read,
            danger_level=DangerLevel.MEDIUM,
            permissions_required=["file_access"],
        )
        self.register_tool(
            name="file_write",
            description="Write content to a file",
            function=self._builtin_file_write,
            danger_level=DangerLevel.HIGH,
            permissions_required=["file_write"],
        )
        self.register_tool(
            name="text_process",
            description="Process text: upper, lower, split, replace, count",
            function=self._builtin_text_process,
            danger_level=DangerLevel.LOW,
        )
        self.register_tool(
            name="web_search",
            description="Search the web for information",
            function=self._builtin_web_search,
            danger_level=DangerLevel.MEDIUM,
            permissions_required=["web_access"],
        )

    def _builtin_calculator(self, expression: str = "", **kwargs) -> Any:
        if not expression:
            raise ValueError("Expression is required")
        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            "int": int,
            "float": float,
        }
        allowed_names.update(
            {
                "pi": math.pi,
                "e": math.e,
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "log": math.log,
                "log2": math.log2,
                "log10": math.log10,
                "ceil": math.ceil,
                "floor": math.floor,
                "factorial": math.factorial,
            }
        )
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id not in allowed_names:
                        raise ValueError(f"Function '{node.func.id}' not allowed")
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                raise ValueError("Import statements not allowed")
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return result

    def _builtin_python_exec(self, code: str = "", **kwargs) -> Any:
        if not code:
            raise ValueError("Code is required")
        dangerous_patterns = [
            r"\bimport\b", r"\bexec\b", r"\beval\b", r"\bopen\b",
            r"\b__import__\b", r"\bglobals\b", r"\blocals\b",
            r"\bgetattr\b", r"\bsetattr\b", r"\bdelattr\b",
            r"\bsubprocess\b", r"\bos\b", r"\bsys\b",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                raise ValueError(f"Potentially dangerous code detected: pattern '{pattern}'")
        safe_builtins = {
            "True": True,
            "False": False,
            "None": None,
            "abs": abs,
            "round": round,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "min": min,
            "max": max,
            "sum": sum,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "print": print,
            "isinstance": isinstance,
            "type": type,
            "hasattr": hasattr,
            "range": range,
        }
        tree = ast.parse(code, mode="exec")
        result = None
        local_vars = {}
        exec(compile(tree, "<string>", "exec"), {"__builtins__": safe_builtins}, local_vars)
        if local_vars:
            result = local_vars
        return result

    def _builtin_file_read(self, path: str = "", encoding: str = "utf-8", **kwargs) -> str:
        if not path:
            raise ValueError("File path is required")
        sensitive_patterns = [
            r"/etc/passwd", r"/etc/shadow", r"\.ssh/", r"\.env",
            r"credentials", r"secrets",
        ]
        for pattern in sensitive_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                raise ValueError(f"Access to sensitive file blocked: {path}")
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        if not os.path.isfile(path):
            raise ValueError(f"Not a file: {path}")
        with open(path, "r", encoding=encoding) as f:
            content = f.read()
        return content

    def _builtin_file_write(
        self, path: str = "", content: str = "", encoding: str = "utf-8", **kwargs
    ) -> dict:
        if not path:
            raise ValueError("File path is required")
        sensitive_patterns = [
            r"/etc/passwd", r"/etc/shadow", r"\.ssh/", r"\.env",
        ]
        for pattern in sensitive_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                raise ValueError(f"Write to sensitive file blocked: {path}")
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return {"path": path, "bytes_written": len(content.encode(encoding))}

    def _builtin_text_process(
        self,
        text: str = "",
        operation: str = "upper",
        find: str = "",
        replace_with: str = "",
        **kwargs,
    ) -> Any:
        if not text:
            raise ValueError("Text is required")
        operations = {
            "upper": lambda t, **_: t.upper(),
            "lower": lambda t, **_: t.lower(),
            "title": lambda t, **_: t.title(),
            "strip": lambda t, **_: t.strip(),
            "split": lambda t, **_: t.split(),
            "count_words": lambda t, **_: len(t.split()),
            "count_chars": lambda t, **_: len(t),
            "reverse": lambda t, **_: t[::-1],
            "replace": lambda t, find=find, replace_with=replace_with, **_: t.replace(find, replace_with),
            "capitalize": lambda t, **_: t.capitalize(),
        }
        if operation not in operations:
            raise ValueError(f"Unknown operation: {operation}. Available: {list(operations.keys())}")
        return operations[operation](text)

    def _builtin_web_search(self, query: str = "", num_results: int = 5, **kwargs) -> list[dict]:
        if not query:
            raise ValueError("Search query is required")
        return [
            {
                "title": f"Result {i+1} for '{query}'",
                "url": f"https://example.com/result{i+1}",
                "snippet": f"This is a simulated search result for the query: {query}",
            }
            for i in range(min(num_results, 5))
        ]

    def _check_rate_limit(self, tool_name: str) -> bool:
        now = time.time()
        window_start = now - self.RATE_LIMIT_WINDOW
        self._execution_counts[tool_name] = [
            t for t in self._execution_counts[tool_name] if t > window_start
        ]
        if len(self._execution_counts[tool_name]) >= self.MAX_EXECUTIONS_PER_WINDOW:
            return False
        self._execution_counts[tool_name].append(now)
        return True

    def _record_execution(self, tool_name: str, duration_ms: int, success: bool):
        self.db.insert_tool_usage(
            tool_name=tool_name,
            input_data={},
            output_data={"success": success},
            success=success,
            duration_ms=duration_ms,
        )
        tool = self._tools.get(tool_name)
        if tool:
            tool.usage_count += 1
            tool.last_used = datetime.now(timezone.utc).isoformat()
            total = tool.avg_duration_ms * (tool.usage_count - 1) + duration_ms
            tool.avg_duration_ms = total / tool.usage_count
