# app/phase2_llm.py
import os
import requests
import json
from typing import Optional
from .config import OPENAI_API_KEY, AIPIPE_API_KEY

def llm_aipipe(prompt: str, max_tokens: int = 1500, model: str = "gpt-4o-mini") -> str:
    if not AIPIPE_API_KEY:
        raise RuntimeError("AIPIPE_API_KEY not set")
    headers = {"Authorization": f"Bearer {AIPIPE_API_KEY}"}
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0.0
    }
    r = requests.post("https://aipipe.org/openrouter/v1/chat/completions", json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "choices" in j and isinstance(j["choices"], list):
        return j["choices"][0].get("text") or j["choices"][0].get("message", {}).get("content", "")
    return json.dumps(j)

def llm_openai(prompt: str, max_tokens: int = 1500, model: str = "gpt-5.1-mini") -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0
        )
        return resp.choices[0].message["content"]
    except Exception:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0
        }
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"]

def phase2_llm(prompt: str, max_tokens: int = 1500) -> str:
    try:
        raw = llm_aipipe(prompt, max_tokens=max_tokens)
    except Exception:
        raw = llm_openai(prompt, max_tokens=max_tokens)

    # --- STRIP MARKDOWN FENCES ---
    cleaned = (
        raw.replace("```python", "")
           .replace("```py", "")
           .replace("```", "")
           .strip()
    )
    return cleaned

