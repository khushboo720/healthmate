"""Rule-based text parsing that runs locally (no AI, no network): lab values, report dates and prescriptions.

Important: the prescription parser only COPIES what is written on the prescription. It never suggests or changes doses.
Anything it cannot read confidently is flagged `needs_review` so the user must confirm it.
"""
import re
from datetime import date, datetime, timedelta

# ----------------------------------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------------------------------
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE_LABEL = re.compile(r"\b(date|collected|collection|sample|reported|report date|prescribed|dated)\b", re.I)
_NOT_DATE = re.compile(r"\b(dob|birth|born|valid|expiry|expires|next|follow)", re.I)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_DMONY = re.compile(r"\b(\d{1,2})[ -]([A-Za-z]{3})[a-z]*[ ,.-]+(\d{4})\b")


def _valid(y: int, m: int, d: int) -> date | None:
    try:
        dt = date(y, m, d)
    except ValueError:
        return None
    return dt if date(1990, 1, 1) <= dt <= date.today() + timedelta(days=1) else None


def _first_date(line: str) -> date | None:
    if m := _ISO.search(line):
        return _valid(int(m[1]), int(m[2]), int(m[3]))
    if m := _DMONY.search(line):
        mon = _MONTHS.get(m[2].lower())
        return _valid(int(m[3]), mon, int(m[1])) if mon else None
    if m := _DMY.search(line):  # day-first (Indian / UK style); fall back to month-first if impossible
        return _valid(int(m[3]), int(m[2]), int(m[1])) or _valid(int(m[3]), int(m[1]), int(m[2]))
    return None


def find_date(text: str) -> str | None:
    """Return an ISO date taken from a labelled line such as 'Collected on: 12/10/2025'. None if not found."""
    for line in text.splitlines()[:80]:
        if _DATE_LABEL.search(line) and not _NOT_DATE.search(line):
            d = _first_date(line)
            if d:
                return d.isoformat()
    return None


# ----------------------------------------------------------------------------------------------
# Lab results
# ----------------------------------------------------------------------------------------------
_RANGE = r"(?P<lo>\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?P<hi>\d+(?:\.\d+)?)"
LINE_RX = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 /().%-]{1,40}?)\s*[:\-]?\s+(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?:(?!ref)(?P<unit>[A-Za-z%µ/][\w%µ/^.*]*)\s*)?[\(\[]?\s*(?:ref(?:erence)?(?:\s*range)?\s*[:\-]?\s*)?" + _RANGE,
    re.I)


def test_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def parse_results(text: str) -> list[dict]:
    """Find lines like 'Hemoglobin 11.2 g/dL (12.0 - 15.5)' and compare to the range printed in the report."""
    out = []
    for line in text.splitlines():
        m = LINE_RX.search(line.strip())
        if not m:
            continue
        value, lo, hi = float(m["value"]), float(m["lo"]), float(m["hi"])
        if lo >= hi:
            continue
        status = "low" if value < lo else "high" if value > hi else "normal"
        name = m["name"].strip(" :-")
        out.append({"name": name, "value": value, "unit": m["unit"] or "", "low": lo, "high": hi, "status": status})
    return out


# ----------------------------------------------------------------------------------------------
# Prescriptions
# ----------------------------------------------------------------------------------------------
_PREFIX = re.compile(r"^(?:tab(?:let)?s?|cap(?:sule)?s?|syp|syrup|inj(?:ection)?|drops?|oint(?:ment)?|cream|gel|sachet|susp(?:ension)?|rx)\b\.?\s*", re.I)
_NUMBERING = re.compile(r"^\s*(?:\d+\s*[.)]|[-•*])\s+")
_HEADER = re.compile(r"^\s*(dr\b|doctor|patient|name|age|sex|gender|date|diagnosis|dx|advice|follow|next visit|clinic|hospital|reg|phone|mobile|signature|address|weight|bp\b|allerg)", re.I)
_STRENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ml|iu|g|%)(?![a-z])", re.I)
_COUNT = re.compile(r"\b(\d+(?:\.\d+)?|half|one|two)\s*(tablets?|tabs?|capsules?|caps?|ml|drops?|puffs?|sachets?|spoons?|tsp)\b", re.I)
_SLOTS = re.compile(r"(?<![\d.])([0-3](?:\.5)?)\s*-\s*([0-3](?:\.5)?)\s*-\s*([0-3](?:\.5)?)(?:\s*-\s*([0-3](?:\.5)?))?(?![\d.])")
_LATIN = re.compile(r"\b(od|qd|bd|bid|tds|tid|qid|hs|sos|prn)\b", re.I)
_EVERY = re.compile(r"every\s+(\d+)\s*(?:hours?|hrs?|h)\b", re.I)
_ENGLISH = [
    (re.compile(r"\bonce\s+(?:a\s+|per\s+)?week(?:ly)?\b|\bweekly\b|\bevery\s+week\b", re.I), "weekly", ["08:00"]),
    (re.compile(r"\balternate\s+days?\b|\bevery\s+other\s+day\b", re.I), "alternate", ["08:00"]),
    (re.compile(r"\bfour\s+times\b", re.I), "daily", ["08:00", "13:00", "18:00", "22:00"]),
    (re.compile(r"\b(?:thrice|three\s+times)\b", re.I), "daily", ["08:00", "14:00", "20:00"]),
    (re.compile(r"\b(?:twice|two\s+times)\b", re.I), "daily", ["08:00", "20:00"]),
    (re.compile(r"\bonce\s+(?:a\s+|per\s+)?(?:day|daily)\b|\bone\s+time\b|\bdaily\b|\bevery\s*day\b", re.I), "daily", ["08:00"]),
    (re.compile(r"\bat\s+night\b|\bbed\s*time\b|\bbefore\s+sleep", re.I), "daily", ["22:00"]),
    (re.compile(r"\bmorning\b", re.I), "daily", ["08:00"]),
    (re.compile(r"\bafternoon\b", re.I), "daily", ["14:00"]),
    (re.compile(r"\bevening\b", re.I), "daily", ["18:00"]),
]
_LATIN_TIMES = {"od": ["08:00"], "qd": ["08:00"], "bd": ["08:00", "20:00"], "bid": ["08:00", "20:00"], "tds": ["08:00", "14:00", "20:00"],
                "tid": ["08:00", "14:00", "20:00"], "qid": ["08:00", "13:00", "18:00", "22:00"], "hs": ["22:00"]}
_EVERY_TIMES = {24: ["08:00"], 12: ["08:00", "20:00"], 8: ["06:00", "14:00", "22:00"], 6: ["06:00", "12:00", "18:00", "00:00"]}
_SLOT_TIMES = {3: ["08:00", "14:00", "21:00"], 4: ["08:00", "13:00", "18:00", "22:00"]}
_DURATION = re.compile(r"(?:\b(?:for|x|up\s*to|next)\b|×)\s*(\d+)\s*(days?|weeks?|wks?|months?)\b|\b(\d+)\s*(days?|weeks?|months?)\b", re.I)
_ONGOING = re.compile(r"\b(continue|ongoing|long[- ]term|lifelong|until\s+review)\b", re.I)
_NOTES = re.compile(r"\b(after\s+(?:food|meals?|breakfast|lunch|dinner)|before\s+(?:food|meals?|breakfast|lunch|dinner)|with\s+(?:food|water|milk)|empty\s+stomach)\b", re.I)


def _duration_days(line: str) -> int | None:
    m = _DURATION.search(line)
    if not m:
        return None
    n, unit = (m[1], m[2]) if m[1] else (m[3], m[4])
    n = int(n)
    unit = unit.lower()
    days = n * (30 if unit.startswith("month") else 7 if unit.startswith(("week", "wk")) else 1)
    return min(days, 365) if days > 0 else None


def parse_prescription_line(line: str) -> dict | None:
    raw = line.strip()
    text = _NUMBERING.sub("", raw)
    if len(text) < 4 or _HEADER.match(text):
        return None
    has_prefix = bool(_PREFIX.match(text))
    body = _PREFIX.sub("", text, count=1) if has_prefix else text

    slots = _SLOTS.search(body)
    latin = _LATIN.search(body)
    strength = _STRENGTH.search(body)
    english = next(((rx, f, t) for rx, f, t in _ENGLISH if rx.search(body)), None)
    every = _EVERY.search(body)
    count = _COUNT.search(body)
    has_freq = bool(latin or english or every)
    if not (has_prefix or slots or ((strength or count) and has_freq)):
        return None

    nm = re.match(
        r"(?P<name>[A-Za-z][A-Za-z0-9 +/&'-]*?)(?=\s+\d|\s*[,(:]|\s+(?:od|qd|bd|bid|tds|tid|qid|hs|sos|prn|once|twice|thrice|daily|every|for|x|at|after|before|weekly|alternate|morning|night)\b|$)",
        body)
    name = nm["name"].strip(" -+/&") if nm else ""
    if len(name) < 2 or name.lower() in {"rx", "tab", "cap"}:
        return None

    times: list[str] = []
    frequency, schedule_text, as_needed = "daily", "", False
    if slots:
        n_slots = 3 if not slots[4] else 4
        vals = [slots[i] for i in range(1, n_slots + 1)]
        mapped = _SLOT_TIMES[n_slots]
        times = [t for t, v in zip(mapped, vals) if float(v) > 0]
        schedule_text = slots[0].replace(" ", "")
    elif latin:
        word = latin[1].lower()
        schedule_text = word.upper()
        if word in ("sos", "prn"):
            as_needed = True
        else:
            times = list(_LATIN_TIMES[word])
    elif every and int(every[1]) in _EVERY_TIMES:
        times, schedule_text = list(_EVERY_TIMES[int(every[1])]), every[0]
    elif english:
        rx, frequency, times = english
        times = list(times)
        schedule_text = rx.search(body)[0]

    if not times and not as_needed:
        frequency = "daily"
    days = _duration_days(body)
    strength_inside_count = bool(strength and count and strength.start() >= count.start() and strength.end() <= count.end())
    dose_bits = [count[0] if count else "", "" if strength_inside_count else (strength[0] if strength else "")]
    dosage = " ".join(b for b in dose_bits if b).strip() or "As written on prescription"
    if schedule_text:
        dosage = f"{dosage} · {schedule_text}"
    notes = list(dict.fromkeys(m.lower() for m in _NOTES.findall(body)))
    if _ONGOING.search(body):
        notes.append("continue as advised")
    if as_needed:
        notes.append("only when needed (no fixed reminder)")
    return {
        "name": name, "dosage": dosage[:80], "times": times, "frequency": frequency, "duration_days": days,
        "instructions": ", ".join(notes), "raw": raw[:200], "as_needed": as_needed,
        "needs_review": not times and not as_needed,
    }


def parse_prescription(text: str) -> dict:
    items = [i for i in (parse_prescription_line(l) for l in text.splitlines()) if i]
    doctor = None
    for line in text.splitlines()[:40]:
        m = re.match(r"^\s*(?:prescribed\s+by\s*[:\-]?\s*)?(dr\.?\s+[A-Za-z][A-Za-z.\s]{2,40}?)\s*(?:\(|,|$|mbbs|md\b)", line, re.I)
        if m:
            doctor = re.sub(r"\s+", " ", m[1]).strip()
            break
    return {"items": items, "doctor": doctor, "date": find_date(text)}
