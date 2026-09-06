"""Genesis AI Python Client — official example for the Inference API.

Usage:
    pip install requests
    python examples/python_client.py
"""

import json
import requests


class Genesis:
    """Simple Python client for Genesis AI Inference API."""

    def __init__(self, base_url: str = "http://localhost:5000", api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def chat(self, message: str, conversation_id: str = None) -> dict:
        """Send a message and get a response.

        Args:
            message: The message to send.
            conversation_id: Optional conversation ID for context.

        Returns:
            dict with keys: response, conversation_id, request_id, status, intent, confidence
        """
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        resp = self.session.post(f"{self.base_url}/v1/chat", json=payload)
        resp.raise_for_status()
        return resp.json()

    def chat_stream(self, message: str, conversation_id: str = None):
        """Stream a response using Server-Sent Events.

        Yields:
            dict events with 'type' and 'data' keys.
        """
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        resp = self.session.post(
            f"{self.base_url}/v1/chat/stream",
            json=payload,
            stream=True,
        )
        resp.raise_for_status()

        event_type = None
        for line in resp.iter_lines(decode_unicode=True):
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                yield {"type": event_type, "data": data}

    def evaluate(self, input_text: str, expected: dict = None, test_type: str = "direct") -> dict:
        """Evaluate Genesis response against criteria.

        Args:
            input_text: The question/task to test.
            expected: Evaluation criteria dict.
            test_type: direct, paraphrase, novel, cross-domain, multi-step.

        Returns:
            dict with response and evaluation result.
        """
        payload = {"input": input_text, "test_type": test_type}
        if expected:
            payload["expected"] = expected

        resp = self.session.post(f"{self.base_url}/v1/evaluate", json=payload)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        """Check Genesis health status."""
        resp = self.session.get(f"{self.base_url}/v1/health")
        return resp.json()

    def models(self) -> dict:
        """List available models."""
        resp = self.session.get(f"{self.base_url}/v1/models")
        return resp.json()

    def status(self) -> dict:
        """Get system status."""
        resp = self.session.get(f"{self.base_url}/v1/status")
        resp.raise_for_status()
        return resp.json()


def main():
    """Example usage of the Genesis client."""

    client = Genesis(
        base_url="http://localhost:5000",
        api_key="YOUR_API_KEY_HERE",
    )

    # Health check
    print("=== Health Check ===")
    health = client.health()
    print(f"Status: {health['status']}")
    print()

    # Models
    print("=== Models ===")
    models = client.models()
    for m in models["data"]:
        print(f"  {m['id']} — {m['name']} ({m['type']})")
    print()

    # Simple chat
    print("=== Chat ===")
    result = client.chat("Hello Genesis! Who are you?")
    print(f"Response: {result['response']}")
    print(f"Intent: {result['intent']} | Confidence: {result['confidence']}")
    print(f"Conversation ID: {result['conversation_id']}")
    print()

    # Multi-turn conversation
    print("=== Multi-turn Conversation ===")
    conv_id = result["conversation_id"]

    result2 = client.chat("What can you help me with?", conversation_id=conv_id)
    print(f"Turn 2: {result2['response'][:100]}...")

    result3 = client.chat("Tell me about Python programming", conversation_id=conv_id)
    print(f"Turn 3: {result3['response'][:100]}...")
    print()

    # Streaming
    print("=== Streaming ===")
    for event in client.chat_stream("What is machine learning?"):
        if event["type"] == "chunk":
            print(event["data"]["text"], end="", flush=True)
        elif event["type"] == "done":
            print()
            print(f"\nDone! Request ID: {event['data']['request_id']}")
        elif event["type"] == "status":
            print(f"\n[{event['data']['stage']}]", end=" ", flush=True)
    print()

    # Evaluation
    print("=== Evaluation ===")
    eval_result = client.evaluate(
        input_text="Explain what an HTTP request is.",
        expected={
            "contains_concepts": ["client", "server", "request", "response"],
            "min_length": 50,
        },
    )
    print(f"Score: {eval_result['evaluation']['score']}")
    print(f"Status: {eval_result['evaluation']['status']}")
    print(f"Criteria: {json.dumps(eval_result['evaluation']['criteria'], indent=2)}")


if __name__ == "__main__":
    main()
