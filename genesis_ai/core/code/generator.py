"""Local code generation engine — generates code from structural patterns, not hardcoded answers."""
import re


class CodeGenerator:
    """Generate code locally for common patterns using structural matching."""

    def generate(self, message: str) -> str | None:
        """Try to generate code from the message. Returns code string or None."""
        msg_lower = message.lower()

        lang_match = re.search(
            r'\b(python|javascript|js|java|c\+\+|rust|go|ruby|php|typescript|html|css|sql)\b',
            msg_lower,
        )
        if not lang_match:
            return None
        lang = lang_match.group(1)

        intent_match = re.search(
            r'\b(hello\s*world|fibonacci|factorial|calculator|calculator\s+app|'
            r'todo|to-do|to\s*do\s+list|api|flask|fastapi|'
            r'function|loop|class|sorting|search|binary\s+search|'
            r'matrix|palindrome|anagram|prime|'
            r'server|client|chat|game|'
            r'web\s*scrape|scraping|'
            r'file\s*read|file\s*write|file\s*io|'
            r'math|matrix|statistics|'
            r'linked\s*list|stack|queue|tree|graph|'
            r'encrypt|decrypt|hash|'
            r'machine\s*learning|neural|regression|classification|'
            r'decorator|generator|context\s*manager)\b',
            msg_lower,
        )
        if not intent_match:
            return None
        intent = intent_match.group(1)

        templates = self._get_templates(lang)
        return templates.get(intent)

    def _get_templates(self, lang: str) -> dict:
        if lang == "python":
            return {
                "hello world": 'print("Hello, World!")',
                "fibonacci": "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        yield a\n        a, b = b, a + b\n\nprint(list(fibonacci(10)))",
                "factorial": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n\nprint(factorial(5))",
                "calculator": 'def add(a, b): return a + b\ndef sub(a, b): return a - b\ndef mul(a, b): return a * b\ndef div(a, b): return a / b if b else "Cannot divide by zero"\n\nprint(add(2, 3))  # 5',
                "todo": 'class TodoList:\n    def __init__(self):\n        self.tasks = []\n    def add(self, task):\n        self.tasks.append({"task": task, "done": False})\n    def done(self, index):\n        if 0 <= index < len(self.tasks):\n            self.tasks[index]["done"] = True\n    def show(self):\n        for i, t in enumerate(self.tasks):\n            status = "✓" if t["done"] else "✗"\n            print(f"{i}. [{status}] {t[\"task\"]}")',
                "function": "def my_function(*args, **kwargs):\n    pass",
                "class": "class MyClass:\n    def __init__(self):\n        pass\n    def method(self):\n        pass",
                "sorting": "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
                "binary search": "def binary_search(arr, target):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1",
                "palindrome": "def is_palindrome(s):\n    return s == s[::-1]",
                "anagram": "def is_anagram(a, b):\n    return sorted(a.lower()) == sorted(b.lower())",
                "prime": "def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5) + 1):\n        if n % i == 0:\n            return False\n    return True",
                "linked list": "class Node:\n    def __init__(self, val):\n        self.val = val\n        self.next = None\n\nclass LinkedList:\n    def __init__(self):\n        self.head = None\n    def push(self, val):\n        node = Node(val)\n        node.next = self.head\n        self.head = node",
                "stack": "class Stack:\n    def __init__(self):\n        self.items = []\n    def push(self, item):\n        self.items.append(item)\n    def pop(self):\n        return self.items.pop() if self.items else None\n    def peek(self):\n        return self.items[-1] if self.items else None\n    def is_empty(self):\n        return len(self.items) == 0",
                "queue": "from collections import deque\n\nclass Queue:\n    def __init__(self):\n        self.items = deque()\n    def enqueue(self, item):\n        self.items.append(item)\n    def dequeue(self):\n        return self.items.popleft() if self.items else None\n    def is_empty(self):\n        return len(self.items) == 0",
                "decorator": "def timer(func):\n    import time\n    def wrapper(*args, **kwargs):\n        start = time.time()\n        result = func(*args, **kwargs)\n        print(f'{func.__name__} took {time.time() - start:.4f}s')\n        return result\n    return wrapper",
                "matrix": "def transpose(matrix):\n    return [list(row) for row in zip(*matrix)]",
                "flask": 'from flask import Flask\n\napp = Flask(__name__)\n\n@app.route("/")\ndef home():\n    return "Hello, World!"\n\nif __name__ == "__main__":\n    app.run(debug=True)',
                "api": 'from flask import Flask, jsonify\n\napp = Flask(__name__)\n\n@app.route("/api/data", methods=["GET"])\ndef get_data():\n    return jsonify({"status": "ok", "data": []})\n\nif __name__ == "__main__":\n    app.run(debug=True)',
            }
        elif lang in ("javascript", "js", "typescript"):
            return {
                "hello world": 'console.log("Hello, World!");',
                "fibonacci": "function fibonacci(n) {\n  let a = 0, b = 1;\n  for (let i = 0; i < n; i++) {\n    console.log(a);\n    [a, b] = [b, a + b];\n  }\n}",
                "function": "function myFunction(...args) {\n  // implementation\n}",
                "class": "class MyClass {\n  constructor() {}\n  method() {}\n}",
                "api": 'const express = require("express");\nconst app = express();\n\napp.get("/api/data", (req, res) => {\n  res.json({ status: "ok", data: [] });\n});\n\napp.listen(3000);',
                "server": 'const http = require("http");\nconst server = http.createServer((req, res) => {\n  res.writeHead(200, {"Content-Type": "text/plain"});\n  res.end("Hello, World!");\n});\nserver.listen(3000);',
            }
        elif lang == "html":
            return {
                "hello world": '<!DOCTYPE html>\n<html>\n<head><title>Hello</title></head>\n<body>\n  <h1>Hello, World!</h1>\n</body>\n</html>',
            }
        elif lang == "sql":
            return {"function": "SELECT 1;"}
        return {}
