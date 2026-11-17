"""Deterministic safety layer. Runs BEFORE any AI call so emergencies are never delayed."""
import re

DISCLAIMER = (
    "Medical disclaimer: HealthMate AI is an educational and wellness support tool. It does not provide "
    "medical diagnosis, treatment or prescriptions and does not replace a qualified doctor. "
    "In an emergency call your local emergency number immediately (India: 112 / ambulance 108; US: 911)."
)

EMERGENCY_MESSAGE = (
    "**This may be a medical emergency.**\n\n"
    "- Call your local emergency number now (India: **112** or ambulance **108**; US: **911**).\n"
    "- Do not wait for more questions or advice from this app.\n"
    "- If possible, ask someone to stay with you and do not drive yourself.\n"
    "- Tell the responders your symptoms, medicines you take and any allergies."
)

MENTAL_HEALTH_MESSAGE = (
    "**You are not alone, and help is available right now.**\n\n"
    "- If you may act on thoughts of harming yourself, call your local emergency number (India: **112**; US: **911**).\n"
    "- India: Tele-MANAS **14416** (free, 24x7). US: call or text **988**.\n"
    "- Please reach out to someone you trust and stay with them.\n\n"
    "I am an app and cannot provide crisis care, but a trained person can."
)

_PATTERNS: list[tuple[str, str]] = [
    (r"chest (pain|pressure|tightness|discomfort)|pain in (my |the )?chest|heart attack|tight chest", "chest pain"),
    (r"(can'?t|cannot|unable to|trouble|difficulty|struggling to|hard to) breath", "breathing difficulty"),
    (r"severe (shortness of breath|breathlessness)|gasping for air", "breathing difficulty"),
    (r"face (is )?droop|slurred speech|sudden(ly)? (weakness|numbness|confusion|loss of vision)|\bstroke\b|worst headache", "stroke signs"),
    (r"unconscious|unresponsive|passed out|not waking|won'?t wake", "loss of consciousness"),
    (r"\bseizure|convulsion", "seizure"),
    (r"(severe|heavy|uncontrol\w*) bleeding|bleeding (won'?t|will not|doesn'?t) stop|vomiting blood|coughing (up )?blood", "severe bleeding"),
    (r"swelling of (the )?(face|throat|tongue|lips)|throat (is )?(closing|swelling)|anaphyla", "severe allergic reaction"),
    (r"overdos|poison(ed|ing)|swallowed (a lot|too many|bleach|chemical)", "overdose or poisoning"),
]
_SELF_HARM = re.compile(r"suicid|kill myself|end my life|want to die|self[- ]harm|hurt myself", re.I)
_PERSONAL = re.compile(
    r"\b(i|i'm|im|i've|ive|my|me|we|he|she|his|her|mom|dad|mother|father|son|daughter|friend|wife|husband|baby|child|patient|someone|somebody)\b", re.I)
_COMPILED = [(re.compile(p, re.I), label) for p, label in _PATTERNS]


def detect_emergency(text: str) -> list[str]:
    """Return a list of red-flag labels found in free text."""
    found = []
    for rx, label in _COMPILED:
        if rx.search(text) and label not in found:
            found.append(label)
    if _SELF_HARM.search(text):
        found.append("self-harm")
    return found


def is_personal(text: str) -> bool:
    """Heuristic: is the user describing their own / someone's situation (vs a general question)?"""
    return bool(_PERSONAL.search(text))


def emergency_reply(flags: list[str]) -> str:
    if "self-harm" in flags:
        return MENTAL_HEALTH_MESSAGE
    return EMERGENCY_MESSAGE


# Free-text values sent to an external AI are stripped of obvious identifiers first.
_REDACT = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?<!\d)(\+?\d[\d\s-]{8,}\d)(?!\d)"), "[number]"),
    (re.compile(r"(?im)^\s*(patient\s*name|name|patient|address|mobile|phone|uhid|mrn|id)\s*[:\-].*$"), "[identifier line removed]"),
]


def redact(text: str) -> str:
    for rx, repl in _REDACT:
        text = rx.sub(repl, text)
    return text
