#!/usr/bin/env python3

import json
from pathlib import Path
from urllib import request


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "local_llm.json"


def load_local_llm_config(path: Path | None = None):
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_json_content(content: str):
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])


def ollama_chat_json(messages, config=None, config_path: Path | None = None):
    if config is None:
        config = load_local_llm_config(config_path)

    base_url = config["base_url"].rstrip("/")
    payload = {
        "model": config["model"],
        "messages": messages,
        "format": "json",
        "stream": False,
        "think": config.get("think", False),
        "keep_alive": config.get("keep_alive", "10m"),
        "options": {
            "temperature": config.get("temperature", 0),
            **config.get("options", {}),
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req, timeout=config.get("timeout_seconds", 180)) as response:
        raw = json.loads(response.read().decode("utf-8"))

    content = raw["message"]["content"]
    return parse_json_content(content)
