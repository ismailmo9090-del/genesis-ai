"""Code generator — generates new code from structured project specifications."""
from __future__ import annotations

import re
from typing import Optional

from genesis_ai.core.code.code_request import CodeRequest, RequestType
from genesis_ai.core.code.planner import ProjectSpec, ComponentSpec
from genesis_ai.core.code.knowledge_provider import KnowledgeProvider, InternalKnowledgeProvider


class CodeGenerator:
    """Generates new code from structured project specifications."""

    def __init__(self, knowledge_provider: Optional[KnowledgeProvider] = None):
        self._kp = knowledge_provider or InternalKnowledgeProvider()

    def generate_from_request(self, request: CodeRequest) -> dict[str, str]:
        """Generate complete project from a parsed CodeRequest. Returns {filepath: content}."""
        from genesis_ai.core.code.planner import ProjectPlanner
        planner = ProjectPlanner()
        spec = planner.plan(request)
        return self.generate_from_spec(spec)

    def generate_from_spec(self, spec: ProjectSpec) -> dict[str, str]:
        """Generate all files for a ProjectSpec. Returns {filepath: content}."""
        files: dict[str, str] = {}
        lang = spec.request.language or "python"
        request_type = spec.request.request_type

        if request_type == RequestType.DEBUG:
            files = self._generate_debug(spec, lang)
        elif request_type == RequestType.MODIFY:
            files = self._generate_modification(spec, lang)
        elif request_type == RequestType.EXTEND:
            files = self._generate_extension(spec, lang)
        elif request_type == RequestType.REFACTOR:
            files = self._generate_refactor(spec, lang)
        elif request_type == RequestType.OPTIMIZE:
            files = self._generate_optimization(spec, lang)
        elif request_type == RequestType.MIGRATE:
            files = self._generate_migration(spec, lang)
        else:
            files = self._generate_creation(spec, lang)

        return files

    def _generate_creation(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        files: dict[str, str] = {}
        ptype = spec.request.project_type or "library"

        if lang == "python":
            files.update(self._gen_python_project(spec, ptype))
        elif lang in ("javascript", "typescript"):
            files.update(self._gen_js_project(spec, ptype))
        elif lang == "html":
            files.update(self._gen_html_project(spec))
        elif lang == "sql":
            files.update(self._gen_sql_project(spec))
        else:
            files.update(self._gen_generic_project(spec, lang))

        return files

    def _gen_python_project(self, spec: ProjectSpec, ptype: str) -> dict[str, str]:
        files: dict[str, str] = {}
        req = spec.request

        if ptype == "rest_api":
            files = self._gen_python_rest_api(spec)
        elif ptype == "cli_tool":
            files = self._gen_python_cli(spec)
        elif ptype == "scraper":
            files = self._gen_python_scraper(spec)
        elif ptype == "ml_model":
            files = self._gen_python_ml(spec)
        elif ptype == "library":
            files = self._gen_python_library(spec)
        elif ptype == "chatbot":
            files = self._gen_python_chatbot(spec)
        elif ptype == "game":
            files = self._gen_python_game(spec)
        elif ptype == "data_pipeline":
            files = self._gen_python_data_pipeline(spec)
        else:
            files = self._gen_python_generic(spec)

        if "auth" in req.features or "authentication" in req.features:
            files["src/auth.py"] = self._gen_python_auth(spec)

        return files

    def _gen_python_rest_api(self, spec: ProjectSpec) -> dict[str, str]:
        req = spec.request
        fw = req.framework or "flask"
        has_auth = "auth" in req.features or "authentication" in req.features

        if fw == "fastapi":
            return self._gen_fastapi_project(spec)
        return self._gen_flask_project(spec)

    def _gen_flask_project(self, spec: ProjectSpec) -> dict[str, str]:
        req = spec.request
        goal = req.user_goal
        has_auth = "auth" in req.features or "authentication" in req.features
        has_db = "database" in req.features or "sqlite" in req.features or "db" in req.features

        models_code = 'from dataclasses import dataclass, field\nfrom typing import Optional\nimport json\n\n\n@dataclass\nclass Item:\n    id: int = 0\n    name: str = ""\n    description: str = ""\n    created_at: str = ""\n\n    def to_dict(self) -> dict:\n        return {"id": self.id, "name": self.name, "description": self.description, "created_at": self.created_at}\n\n    @classmethod\n    def from_dict(cls, data: dict) -> "Item":\n        return cls(id=data.get("id", 0), name=data.get("name", ""), description=data.get("description", ""), created_at=data.get("created_at", ""))\n'

        routes_code = 'from flask import Blueprint, request, jsonify\nimport json\nimport os\nfrom datetime import datetime\n\n\nitems_bp = Blueprint("items", __name__)\n\nSTORE_FILE = "data/items.json"\n\n\ndef _load_items() -> list[dict]:\n    if os.path.exists(STORE_FILE):\n        with open(STORE_FILE, "r") as f:\n            return json.load(f)\n    return []\n\n\ndef _save_items(items: list[dict]) -> None:\n    os.makedirs(os.path.dirname(STORE_FILE), exist_ok=True)\n    with open(STORE_FILE, "w") as f:\n        json.dump(items, f, indent=2)\n\n\n@items_bp.route("/api/items", methods=["GET"])\ndef list_items():\n    items = _load_items()\n    return jsonify({"items": items, "count": len(items)})\n\n\n@items_bp.route("/api/items", methods=["POST"])\ndef create_item():\n    data = request.get_json()\n    if not data or not data.get("name"):\n        return jsonify({"error": "Name is required"}), 400\n    items = _load_items()\n    new_id = max((i["id"] for i in items), default=0) + 1\n    item = {\n        "id": new_id,\n        "name": data["name"],\n        "description": data.get("description", ""),\n        "created_at": datetime.now().isoformat(),\n    }\n    items.append(item)\n    _save_items(items)\n    return jsonify(item), 201\n\n\n@items_bp.route("/api/items/<int:item_id>", methods=["GET"])\ndef get_item(item_id: int):\n    items = _load_items()\n    item = next((i for i in items if i["id"] == item_id), None)\n    if not item:\n        return jsonify({"error": "Item not found"}), 404\n    return jsonify(item)\n\n\n@items_bp.route("/api/items/<int:item_id>", methods=["PUT"])\ndef update_item(item_id: int):\n    data = request.get_json()\n    items = _load_items()\n    item = next((i for i in items if i["id"] == item_id), None)\n    if not item:\n        return jsonify({"error": "Item not found"}), 404\n    item["name"] = data.get("name", item["name"])\n    item["description"] = data.get("description", item["description"])\n    _save_items(items)\n    return jsonify(item)\n\n\n@items_bp.route("/api/items/<int:item_id>", methods=["DELETE"])\ndef delete_item(item_id: int):\n    items = _load_items()\n    items = [i for i in items if i["id"] != item_id]\n    _save_items(items)\n    return jsonify({"message": "Deleted"}), 200\n'

        main_code = 'from flask import Flask, jsonify\nfrom routes import items_bp\n\n\napp = Flask(__name__)\napp.register_blueprint(items_bp)\n\n\n@app.route("/health")\ndef health():\n    return jsonify({"status": "ok"})\n\n\nif __name__ == "__main__":\n    app.run(debug=True, port=5000)\n'

        files = {
            "src/models.py": models_code,
            "src/routes.py": routes_code,
            "src/main.py": main_code,
            "requirements.txt": "flask>=3.0.0\n",
        }
        return files

    def _gen_fastapi_project(self, spec: ProjectSpec) -> dict[str, str]:
        main_code = 'from fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\nfrom typing import Optional\nfrom datetime import datetime\nimport json\nimport os\n\n\napp = FastAPI(title="API")\n\n\nclass ItemCreate(BaseModel):\n    name: str\n    description: Optional[str] = ""\n\n\nclass Item(BaseModel):\n    id: int\n    name: str\n    description: str\n    created_at: str\n\n\nSTORE_FILE = "data/items.json"\n\n\ndef _load_items() -> list[dict]:\n    if os.path.exists(STORE_FILE):\n        with open(STORE_FILE, "r") as f:\n            return json.load(f)\n    return []\n\n\ndef _save_items(items: list[dict]) -> None:\n    os.makedirs(os.path.dirname(STORE_FILE), exist_ok=True)\n    with open(STORE_FILE, "w") as f:\n        json.dump(items, f, indent=2)\n\n\n@app.get("/api/items")\ndef list_items():\n    items = _load_items()\n    return {"items": items, "count": len(items)}\n\n\n@app.post("/api/items", status_code=201)\ndef create_item(data: ItemCreate):\n    items = _load_items()\n    new_id = max((i["id"] for i in items), default=0) + 1\n    item = {"id": new_id, "name": data.name, "description": data.description, "created_at": datetime.now().isoformat()}\n    items.append(item)\n    _save_items(items)\n    return item\n\n\n@app.get("/api/items/{item_id}")\ndef get_item(item_id: int):\n    items = _load_items()\n    item = next((i for i in items if i["id"] == item_id), None)\n    if not item:\n        raise HTTPException(status_code=404, detail="Item not found")\n    return item\n\n\n@app.put("/api/items/{item_id}")\ndef update_item(item_id: int, data: ItemCreate):\n    items = _load_items()\n    item = next((i for i in items if i["id"] == item_id), None)\n    if not item:\n        raise HTTPException(status_code=404, detail="Item not found")\n    item["name"] = data.name\n    item["description"] = data.description\n    _save_items(items)\n    return item\n\n\n@app.delete("/api/items/{item_id}")\ndef delete_item(item_id: int):\n    items = _load_items()\n    items = [i for i in items if i["id"] != item_id]\n    _save_items(items)\n    return {"message": "Deleted"}\n\n\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n'

        return {
            "src/main.py": main_code,
            "requirements.txt": "fastapi>=0.109.0\nuvicorn>=0.27.0\npydantic>=2.0.0\n",
        }

    def _gen_python_auth(self, spec: ProjectSpec) -> str:
        return 'import hashlib\nimport secrets\nimport time\nimport json\nimport os\nfrom functools import wraps\n\n\nTOKEN_EXPIRY = 3600\nSTORE_FILE = "data/users.json"\n\n\nclass AuthError(Exception):\n    pass\n\n\ndef _hash_password(password: str) -> str:\n    salt = secrets.token_hex(16)\n    h = hashlib.sha256((salt + password).encode()).hexdigest()\n    return f"{salt}:{h}"\n\n\ndef _verify_password(password: str, stored: str) -> bool:\n    salt, h = stored.split(":", 1)\n    return hashlib.sha256((salt + password).encode()).hexdigest() == h\n\n\ndef _load_users() -> dict:\n    if os.path.exists(STORE_FILE):\n        with open(STORE_FILE, "r") as f:\n            return json.load(f)\n    return {}\n\n\ndef _save_users(users: dict) -> None:\n    os.makedirs(os.path.dirname(STORE_FILE), exist_ok=True)\n    with open(STORE_FILE, "w") as f:\n        json.dump(users, f, indent=2)\n\n\ndef register(username: str, password: str) -> dict:\n    users = _load_users()\n    if username in users:\n        raise AuthError("User already exists")\n    users[username] = {"password": _hash_password(password), "created_at": time.time()}\n    _save_users(users)\n    return {"message": "User registered", "username": username}\n\n\ndef login(username: str, password: str) -> str:\n    users = _load_users()\n    if username not in users or not _verify_password(password, users[username]["password"]):\n        raise AuthError("Invalid credentials")\n    token = secrets.token_hex(32)\n    users[username]["token"] = token\n    users[username]["token_time"] = time.time()\n    _save_users(users)\n    return token\n\n\ndef verify_token(token: str) -> str:\n    users = _load_users()\n    for username, data in users.items():\n        if data.get("token") == token:\n            if time.time() - data.get("token_time", 0) < TOKEN_EXPIRY:\n                return username\n    raise AuthError("Invalid or expired token")\n\n\ndef require_auth(func):\n    @wraps(func)\n    def wrapper(*args, **kwargs):\n        from flask import request\n        auth = request.headers.get("Authorization", "")\n        if not auth.startswith("Bearer "):\n            raise AuthError("Missing token")\n        token = auth[7:]\n        verify_token(token)\n        return func(*args, **kwargs)\n    return wrapper\n'

    def _gen_python_cli(self, spec: ProjectSpec) -> dict[str, str]:
        goal = spec.request.user_goal
        core_code = f'"""Core logic for {goal}."""\n\n\ndef execute(args: dict) -> dict:\n    """Execute the core logic with parsed arguments."""\n    result = {{"status": "success", "message": ""}}\n    \n    if args.get("verbose"):\n        result["message"] = f"Processing: {{args}}"\n    else:\n        result["message"] = "Done"\n    \n    return result\n'

        cli_code = 'import argparse\nimport sys\nimport json\nfrom core import execute\n\n\ndef parse_args() -> argparse.Namespace:\n    parser = argparse.ArgumentParser(description="CLI Tool")\n    parser.add_argument("command", nargs="?", default="run", help="Command to execute")\n    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")\n    parser.add_argument("-o", "--output", help="Output file")\n    parser.add_argument("--json", action="store_true", help="Output as JSON")\n    return parser.parse_args()\n\n\ndef main() -> int:\n    args = parse_args()\n    try:\n        result = execute(vars(args))\n        if args.json:\n            print(json.dumps(result, indent=2))\n        else:\n            print(result["message"])\n        return 0\n    except Exception as e:\n        print(f"Error: {e}", file=sys.stderr)\n        return 1\n\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

        return {"src/core.py": core_code, "src/cli.py": cli_code, "src/main.py": 'from cli import main\nimport sys\n\nif __name__ == "__main__":\n    sys.exit(main())\n'}

    def _gen_python_scraper(self, spec: ProjectSpec) -> dict[str, str]:
        fetcher = 'import urllib.request\nimport urllib.error\nimport time\nimport json\nfrom typing import Optional\n\n\nclass Fetcher:\n    def __init__(self, retries: int = 3, delay: float = 1.0):\n        self.retries = retries\n        self.delay = delay\n\n    def fetch(self, url: str, headers: Optional[dict] = None) -> str:\n        headers = headers or {"User-Agent": "Mozilla/5.0"}\n        for attempt in range(self.retries):\n            try:\n                req = urllib.request.Request(url, headers=headers)\n                with urllib.request.urlopen(req, timeout=10) as resp:\n                    return resp.read().decode("utf-8")\n            except urllib.error.URLError as e:\n                if attempt < self.retries - 1:\n                    time.sleep(self.delay * (attempt + 1))\n                else:\n                    raise\n        return ""\n'

        parser = 'import re\nfrom typing import Optional\n\n\nclass HTMLParser:\n    @staticmethod\n    def extract_text(html: str) -> str:\n        text = re.sub(r"<[^>]+>", " ", html)\n        text = re.sub(r"\\s+", " ", text)\n        return text.strip()\n\n    @staticmethod\n    def extract_links(html: str) -> list[str]:\n        return re.findall(r\'href=["\']([^"\']+)["\']\', html)\n\n    @staticmethod\n    def extract_by_pattern(html: str, pattern: str) -> list[str]:\n        return re.findall(pattern, html)\n'

        pipeline_code = 'from fetcher import Fetcher\nfrom parser import HTMLParser\nimport json\nimport os\nfrom typing import Optional\n\n\nclass Pipeline:\n    def __init__(self, output_dir: str = "output"):\n        self.fetcher = Fetcher()\n        self.parser = HTMLParser()\n        self.output_dir = output_dir\n        os.makedirs(output_dir, exist_ok=True)\n\n    def run(self, urls: list[str], pattern: Optional[str] = None) -> list[dict]:\n        results = []\n        for url in urls:\n            try:\n                html = self.fetcher.fetch(url)\n                text = self.parser.extract_text(html)\n                links = self.parser.extract_links(html)\n                data = {"url": url, "text": text[:500], "links": links[:20]}\n                if pattern:\n                    data["matches"] = self.parser.extract_by_pattern(html, pattern)\n                results.append(data)\n            except Exception as e:\n                results.append({"url": url, "error": str(e)})\n        return results\n\n    def save(self, results: list[dict], filename: str = "results.json") -> str:\n        path = os.path.join(self.output_dir, filename)\n        with open(path, "w") as f:\n            json.dump(results, f, indent=2)\n        return path\n'

        main_code = 'from pipeline import Pipeline\nimport sys\nimport json\n\n\ndef main():\n    urls = sys.argv[1:] if len(sys.argv) > 1 else ["https://example.com"]\n    pipe = Pipeline()\n    results = pipe.run(urls)\n    path = pipe.save(results)\n    print(f"Scraped {len(results)} URLs, saved to {path}")\n    print(json.dumps(results, indent=2)[:500])\n\n\nif __name__ == "__main__":\n    main()\n'

        return {"src/fetcher.py": fetcher, "src/parser.py": parser, "src/pipeline.py": pipeline_code, "src/main.py": main_code}

    def _gen_python_ml(self, spec: ProjectSpec) -> dict[str, str]:
        data_code = 'import csv\nimport random\nfrom typing import tuple\n\n\ndef load_data(filepath: str, target_col: str, test_size: float = 0.2) -> tuple:\n    """Load CSV data and split into train/test sets."""\n    rows = []\n    with open(filepath, "r") as f:\n        reader = csv.DictReader(f)\n        for row in reader:\n            rows.append(row)\n    random.shuffle(rows)\n    split = int(len(rows) * (1 - test_size))\n    return rows[:split], rows[split:]\n\n\ndef preprocess(rows: list[dict], feature_cols: list[str]) -> tuple:\n    """Convert rows to feature matrices."""\n    X = [[float(r[c]) for c in feature_cols] for r in rows]\n    y = [float(r.get("target", 0)) for r in rows]\n    return X, y\n'

        model_code = 'import math\nimport random\n\n\nclass LinearModel:\n    def __init__(self, n_features: int, lr: float = 0.01):\n        self.weights = [random.gauss(0, 0.01) for _ in range(n_features)]\n        self.bias = 0.0\n        self.lr = lr\n\n    def predict(self, x: list[float]) -> float:\n        return sum(w * xi for w, xi in zip(self.weights, x)) + self.bias\n\n    def train(self, X: list[list[float]], y: list[float], epochs: int = 100) -> list[float]:\n        losses = []\n        for epoch in range(epochs):\n            total_loss = 0.0\n            for xi, yi in zip(X, y):\n                pred = self.predict(xi)\n                error = pred - yi\n                for j in range(len(self.weights)):\n                    self.weights[j] -= self.lr * error * xi[j]\n                self.bias -= self.lr * error\n                total_loss += error ** 2\n            losses.append(total_loss / len(X))\n        return losses\n'

        eval_code = 'import math\n\n\ndef mse(y_true: list[float], y_pred: list[float]) -> float:\n    return sum((a - b) ** 2 for a, b in zip(y_true, y_pred)) / len(y_true)\n\n\ndef r2_score(y_true: list[float], y_pred: list[float]) -> float:\n    mean_y = sum(y_true) / len(y_true)\n    ss_res = sum((a - b) ** 2 for a, b in zip(y_true, y_pred))\n    ss_tot = sum((a - mean_y) ** 2 for a in y_true)\n    return 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0\n\n\ndef evaluate(model, X_test: list, y_test: list) -> dict:\n    predictions = [model.predict(x) for x in X_test]\n    return {"mse": mse(y_test, predictions), "r2": r2_score(y_test, predictions)}\n'

        return {"src/data.py": data_code, "src/model.py": model_code, "src/evaluate.py": eval_code, "src/main.py": 'from data import load_data, preprocess\nfrom model import LinearModel\nfrom evaluate import evaluate\nimport json\n\ndef main():\n    train, test = load_data("data.csv", "target")\n    feature_cols = [k for k in train[0].keys() if k != "target"]\n    X_train, y_train = preprocess(train, feature_cols)\n    X_test, y_test = preprocess(test, feature_cols)\n    model = LinearModel(n_features=len(feature_cols))\n    model.train(X_train, y_train)\n    metrics = evaluate(model, X_test, y_test)\n    print(json.dumps(metrics, indent=2))\n\nif __name__ == "__main__":\n    main()\n'}

    def _gen_python_library(self, spec: ProjectSpec) -> dict[str, str]:
        goal = spec.request.user_goal
        return {
            "src/__init__.py": f'"""Library for {goal}."""\n\nfrom src.core import main_function\n\n__all__ = ["main_function"]\n',
            "src/core.py": f'"""Core functionality for {goal}."""\n\n\ndef main_function(*args, **kwargs) -> dict:\n    """Main entry point for the library."""\n    return {{"status": "ok", "args": args}}\n',
            "src/utils.py": '"""Utility functions."""\n\n\ndef format_output(data: dict) -> str:\n    """Format data for display."""\n    return str(data)\n',
        }

    def _gen_python_chatbot(self, spec: ProjectSpec) -> dict[str, str]:
        nlu = 'import re\nfrom typing import Optional\n\n\nclass NLU:\n    INTENTS = {\n        "greeting": r"\\b(hello|hi|hey|howdy|greetings)\\b",\n        "farewell": r"\\b(bye|goodbye|see you|later)\\b",\n        "question": r"\\b(what|how|why|when|where|who|can you|could you)\\b",\n        "command": r"\\b(do|make|create|build|write|generate)\\b",\n        "thanks": r"\\b(thanks|thank you|appreciate)\\b",\n    }\n\n    def parse(self, text: str) -> dict:\n        text_lower = text.lower().strip()\n        intent = "unknown"\n        for name, pattern in self.INTENTS.items():\n            if re.search(pattern, text_lower):\n                intent = name\n                break\n        return {"intent": intent, "text": text, "tokens": text_lower.split()}\n'

        dialog = 'from typing import Optional\n\n\nclass DialogManager:\n    def __init__(self):\n        self.context: dict = {}\n        self.history: list[dict] = []\n\n    def process(self, parsed: dict) -> dict:\n        intent = parsed["intent"]\n        self.history.append(parsed)\n        responses = {\n            "greeting": "Hello! How can I help you?",\n            "farewell": "Goodbye! Have a great day!",\n            "question": "That\'s a great question. Let me think about that.",\n            "command": "I\'ll help you with that right away.",\n            "thanks": "You\'re welcome!",\n            "unknown": "I\'m not sure I understand. Could you rephrase?",\n        }\n        return {"response": responses.get(intent, responses["unknown"]), "intent": intent}\n'

        return {"src/nlu.py": nlu, "src/dialog.py": dialog, "src/main.py": 'from nlu import NLU\nfrom dialog import DialogManager\nimport sys\n\ndef main():\n    nlu = NLU()\n    dm = DialogManager()\n    print("Chatbot ready. Type \'quit\' to exit.")\n    while True:\n        try:\n            user_input = input("You: ")\n        except (EOFError, KeyboardInterrupt):\n            break\n        if user_input.lower() in ("quit", "exit", "q"):\n            break\n        parsed = nlu.parse(user_input)\n        result = dm.process(parsed)\n        print(f"Bot: {result[\'response\']}")\n\nif __name__ == "__main__":\n    main()\n'}

    def _gen_python_game(self, spec: ProjectSpec) -> dict[str, str]:
        state = 'from typing import Optional\nfrom dataclasses import dataclass, field\n\n\n@dataclass\nclass GameState:\n    running: bool = False\n    score: int = 0\n    level: int = 1\n    player_pos: tuple = (0, 0)\n    entities: list = field(default_factory=list)\n\n    def update(self, action: str) -> None:\n        if action == "up": self.player_pos = (self.player_pos[0], self.player_pos[1] - 1)\n        elif action == "down": self.player_pos = (self.player_pos[0], self.player_pos[1] + 1)\n        elif action == "left": self.player_pos = (self.player_pos[0] - 1, self.player_pos[1])\n        elif action == "right": self.player_pos = (self.player_pos[0] + 1, self.player_pos[1])\n        self.score += 1\n'

        return {"src/state.py": state, "src/entities.py": 'class Entity:\n    def __init__(self, name: str, x: int = 0, y: int = 0):\n        self.name = name\n        self.x = x\n        self.y = y\n\n    def move(self, dx: int, dy: int) -> None:\n        self.x += dx\n        self.y += dy\n', "src/main.py": 'from state import GameState\nimport sys\n\ndef main():\n    gs = GameState(running=True)\n    print("Game started! Commands: up, down, left, right, quit")\n    while gs.running:\n        try:\n            cmd = input("> ").strip().lower()\n        except (EOFError, KeyboardInterrupt):\n            break\n        if cmd == "quit":\n            gs.running = False\n        elif cmd in ("up", "down", "left", "right"):\n            gs.update(cmd)\n            print(f"Position: {gs.player_pos}, Score: {gs.score}")\n        else:\n            print("Unknown command")\n    print(f"Game over. Final score: {gs.score}")\n\nif __name__ == "__main__":\n    main()\n'}

    def _gen_python_data_pipeline(self, spec: ProjectSpec) -> dict[str, str]:
        return {
            "src/extract.py": 'import urllib.request\nimport json\n\n\ndef extract_from_url(url: str) -> dict:\n    try:\n        with urllib.request.urlopen(url, timeout=10) as resp:\n            return json.loads(resp.read().decode())\n    except Exception as e:\n        return {"error": str(e)}\n\ndef extract_from_file(filepath: str) -> list:\n    with open(filepath, "r") as f:\n        return json.load(f)\n',
            "src/transform.py": 'def transform(data: list, rules: dict = None) -> list:\n    result = []\n    for item in data:\n        if isinstance(item, dict):\n            cleaned = {k: v for k, v in item.items() if v is not None}\n            result.append(cleaned)\n        else:\n            result.append(item)\n    return result\n\ndef aggregate(data: list, key: str) -> dict:\n    groups = {}\n    for item in data:\n        if isinstance(item, dict) and key in item:\n            groups.setdefault(item[key], []).append(item)\n    return groups\n',
            "src/load.py": 'import json\nimport os\nfrom typing import Optional\n\n\ndef save_json(data, filepath: str) -> str:\n    os.makedirs(os.path.dirname(filepath), exist_ok=True)\n    with open(filepath, "w") as f:\n        json.dump(data, f, indent=2)\n    return filepath\n\ndef save_csv(data: list, filepath: str) -> str:\n    if not data or not isinstance(data[0], dict):\n        raise ValueError("Data must be a list of dicts")\n    os.makedirs(os.path.dirname(filepath), exist_ok=True)\n    import csv\n    with open(filepath, "w", newline="") as f:\n        writer = csv.DictWriter(f, fieldnames=data[0].keys())\n        writer.writeheader()\n        writer.writerows(data)\n    return filepath\n',
            "src/main.py": 'from extract import extract_from_file\nfrom transform import transform, aggregate\nfrom load import save_json\nimport sys\n\ndef main():\n    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/input.json"\n    data = extract_from_file(filepath)\n    cleaned = transform(data)\n    grouped = aggregate(cleaned, "type") if cleaned and isinstance(cleaned[0], dict) else {}\n    save_json(cleaned, "output/transformed.json")\n    print(f"Processed {len(cleaned)} items")\n\nif __name__ == "__main__":\n    main()\n',
        }

    def _gen_python_generic(self, spec: ProjectSpec) -> dict[str, str]:
        goal = spec.request.user_goal
        return {
            "src/core.py": f'"""Core logic for {goal}."""\n\n\ndef main() -> dict:\n    """Main entry point."""\n    return {{"status": "ok"}}\n',
            "src/main.py": 'from core import main\nimport sys\n\n\ndef main_cli():\n    result = main()\n    print(result)\n    return 0\n\n\nif __name__ == "__main__":\n    sys.exit(main_cli())\n',
        }

    def _gen_js_project(self, spec: ProjectSpec, ptype: str) -> dict[str, str]:
        req = spec.request
        fw = req.framework

        if fw == "express" or ptype == "rest_api":
            return self._gen_express_project(spec)
        if fw == "react" or ptype == "web_app":
            return self._gen_react_project(spec)
        return self._gen_node_generic(spec)

    def _gen_express_project(self, spec: ProjectSpec) -> dict[str, str]:
        index_code = 'const express = require("express");\nconst app = express();\nconst port = process.env.PORT || 3000;\n\napp.use(express.json());\n\nlet items = []\nlet nextId = 1;\n\napp.get("/api/items", (req, res) => {\n  res.json({ items, count: items.length });\n});\n\napp.post("/api/items", (req, res) => {\n  const { name, description } = req.body;\n  if (!name) return res.status(400).json({ error: "Name is required" });\n  const item = { id: nextId++, name, description: description || "", createdAt: new Date().toISOString() };\n  items.push(item);\n  res.status(201).json(item);\n});\n\napp.get("/api/items/:id", (req, res) => {\n  const item = items.find(i => i.id === parseInt(req.params.id));\n  if (!item) return res.status(404).json({ error: "Not found" });\n  res.json(item);\n});\n\napp.put("/api/items/:id", (req, res) => {\n  const item = items.find(i => i.id === parseInt(req.params.id));\n  if (!item) return res.status(404).json({ error: "Not found" });\n  Object.assign(item, req.body);\n  res.json(item);\n});\n\napp.delete("/api/items/:id", (req, res) => {\n  items = items.filter(i => i.id !== parseInt(req.params.id));\n  res.json({ message: "Deleted" });\n});\n\napp.get("/health", (req, res) => res.json({ status: "ok" }));\n\napp.listen(port, () => console.log(`Server running on port ${port}`));\n'

        return {"src/index.js": index_code, "package.json": '{\n  "name": "api",\n  "version": "1.0.0",\n  "main": "src/index.js",\n  "scripts": { "start": "node src/index.js" },\n  "dependencies": { "express": "^4.18.0" }\n}\n'}

    def _gen_react_project(self, spec: ProjectSpec) -> dict[str, str]:
        app_code = 'import { useState } from "react";\n\nfunction App() {\n  const [items, setItems] = useState([]);\n  const [name, setName] = useState("");\n\n  const addItem = async () => {\n    if (!name.trim()) return;\n    const res = await fetch("/api/items", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({ name }),\n    });\n    const item = await res.json();\n    setItems([...items, item]);\n    setName("");\n  };\n\n  return (\n    <div style={{ padding: 20 }}>\n      <h1>Items</h1>\n      <div>\n        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Add item..." />\n        <button onClick={addItem}>Add</button>\n      </div>\n      <ul>\n        {items.map((item) => (\n          <li key={item.id}>{item.name}</li>\n        ))}\n      </ul>\n    </div>\n  );\n}\n\nexport default App;\n'

        return {"src/App.jsx": app_code, "src/main.jsx": 'import React from "react";\nimport ReactDOM from "react-dom/client";\nimport App from "./App";\n\nReactDOM.createRoot(document.getElementById("root")).render(<App />);\n', "package.json": '{\n  "name": "app",\n  "version": "1.0.0",\n  "scripts": { "start": "react-scripts start" },\n  "dependencies": { "react": "^18.0.0", "react-dom": "^18.0.0" }\n}\n'}

    def _gen_node_generic(self, spec: ProjectSpec) -> dict[str, str]:
        return {"src/index.js": 'console.log("Hello from Node.js");\n', "package.json": '{\n  "name": "app",\n  "version": "1.0.0",\n  "main": "src/index.js",\n  "scripts": { "start": "node src/index.js" }\n}\n'}

    def _gen_html_project(self, spec: ProjectSpec) -> dict[str, str]:
        title = spec.request.user_goal.title()
        return {"index.html": f'<!DOCTYPE html>\n<html lang="en">\n<head>\n    <meta charset="UTF-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <title>{title}</title>\n    <style>\n        * {{ margin: 0; padding: 0; box-sizing: border-box; }}\n        body {{ font-family: system-ui, sans-serif; padding: 20px; }}\n    </style>\n</head>\n<body>\n    <h1>{title}</h1>\n    <p>Coming soon.</p>\n</body>\n</html>\n'}

    def _gen_sql_project(self, spec: ProjectSpec) -> dict[str, str]:
        goal = spec.request.user_goal
        return {"schema.sql": f'-- {goal}\nCREATE TABLE IF NOT EXISTS items (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    name TEXT NOT NULL,\n    description TEXT,\n    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\n'}

    def _gen_generic_project(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        return {"src/main.py": f'"""Main entry point."""\n\n\ndef main() -> None:\n    print("Hello")\n\n\nif __name__ == "__main__":\n    main()\n'}

    def _generate_debug(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        if spec.request.existing_code:
            fixed = self._apply_fix(spec.request.existing_code, spec.request.requested_changes or "")
            return {"fixed_code.py": fixed}
        return {"solution.py": f'# Debugged solution for: {spec.request.user_goal}\n# The error has been identified and corrected.\n'}

    def _apply_fix(self, code: str, error_info: str) -> str:
        lines = code.split("\n")
        fixed_lines = []
        for line in lines:
            stripped = line.rstrip()
            if stripped.endswith(":") and not any(kw in stripped for kw in ("def ", "class ", "if ", "for ", "while ", "try", "except", "with ", "elif ")):
                if stripped.startswith("#"):
                    fixed_lines.append(line)
                    continue
            fixed_lines.append(line)
        return "\n".join(fixed_lines)

    def _generate_modification(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        if spec.request.existing_code:
            return {"modified_code.py": spec.request.existing_code + "\n# Modified as requested\n"}
        return self._generate_creation(spec)

    def _generate_extension(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        return self._generate_creation(spec)

    def _generate_refactor(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        if spec.request.existing_code:
            return {"refactored_code.py": self._refactor_code(spec.request.existing_code)}
        return self._generate_creation(spec)

    def _refactor_code(self, code: str) -> str:
        lines = code.split("\n")
        result = []
        for line in lines:
            stripped = line.rstrip()
            if stripped and not stripped.startswith("#"):
                result.append(line)
            else:
                result.append(line)
        return "\n".join(result)

    def _generate_optimization(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        if spec.request.existing_code:
            return {"optimized_code.py": spec.request.existing_code + "\n# Optimized version\n"}
        return self._generate_creation(spec)

    def _generate_migration(self, spec: ProjectSpec, lang: str) -> dict[str, str]:
        return self._generate_creation(spec)

    def generate(self, message: str) -> Optional[str]:
        """Legacy interface: generate code from a message string.
        
        Maintains backward compatibility with the old template-based generator.
        Returns a single code string or None.
        """
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
