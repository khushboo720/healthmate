"""LLM provider wrapper (Google Gemini REST API). Falls back to demo mode when no key is set."""
import json
import re

import httpx

from .config import AI_TIMEOUT_SECONDS, GEMINI_API_KEY, GEMINI_MODEL

SYSTEM_PROMPT = """You are HealthMate AI, an educational health-information assistant for a college project.
Rules you must always follow:
- Give general, easy-to-understand health information. Use short paragraphs and bullet points.
- NEVER give a definitive diagnosis, disease probabilities, or say the user 'has' a condition.
- NEVER prescribe medicines, recommend doses, or advise changing/stopping prescribed medicines.
  For medicines say: follow your doctor's or pharmacist's instructions.
- NEVER claim to replace a doctor. Say when it is sensible to see a doctor.
- If any message suggests an emergency (chest pain, trouble breathing, stroke signs, severe bleeding,
  unconsciousness, self-harm), tell the user to call emergency services immediately and stop there.
- Keep answers under 250 words. Do not ask for names, addresses or phone numbers."""


class AIError(Exception):
    pass


def ai_enabled() -> bool:
    return bool(GEMINI_API_KEY)


def status() -> dict:
    return {"mode": "live" if ai_enabled() else "demo", "model": GEMINI_MODEL if ai_enabled() else None}


def generate(messages: list[dict], system: str = SYSTEM_PROMPT, json_mode: bool = False, max_tokens: int = 900) -> str:
    """messages: [{'role': 'user'|'assistant', 'content': str}]. Raises AIError on any failure."""
    if not ai_enabled():
        raise AIError("AI key not configured")
    contents = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in messages
    ]
    gen_cfg: dict = {"temperature": 0.4, "maxOutputTokens": max_tokens}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"
    body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gen_cfg}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    try:
        r = httpx.post(url, json=body, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=AI_TIMEOUT_SECONDS)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise AIError(type(exc).__name__) from exc


def generate_json(prompt: str, max_tokens: int = 1200) -> dict:
    text = generate([{"role": "user", "content": prompt}], json_mode=True, max_tokens=max_tokens)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIError("invalid JSON") from exc
    if not isinstance(data, dict):
        raise AIError("unexpected JSON shape")
    return data
