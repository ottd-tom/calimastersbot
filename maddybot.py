# maddybot.py
import os, re, json, difflib, random
from pathlib import Path
from typing import Any, Dict, List, Optional

# ===============================================
# ---------------- CONFIG -----------------------
# ===============================================

GPT_MODEL = os.getenv("MADDY_GPT_MODEL", "gpt-4o-mini")
DEFAULT_MAX_UNITS = 5
TOP_K = 8

def _data_dir() -> Path:
    env = os.getenv("MADDY_DATA_DIR")
    return Path(env) if env else (Path(__file__).parent / "data")


# ===============================================
# ---------------- BASIC UTILS ------------------
# ===============================================

def _normalize(s: str) -> str:
    s = s.lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return re.sub(r"\s+", " ", s).strip()

def _parse_numeric_unsigned(value: Any) -> Optional[float]:
    if value is None: return None
    if isinstance(value, (int, float)): return float(value)
    s = str(value).strip().replace('"', "").replace("”", "").replace("“", "").rstrip("+")
    if re.fullmatch(r"\d+(\.\d+)?", s): return float(s)
    m = re.search(r"(\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else None

def _parse_numeric_signed(value: Any) -> Optional[float]:
    if value is None: return None
    if isinstance(value, (int, float)): return float(value)
    s = str(value).strip().replace("−", "-")
    s = s.replace('"', "").replace("”", "").replace("“", "")
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", s):
        return float(s)
    m = re.search(r"([+-]?\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else None

def _avg_dice(expr: str) -> Optional[float]:
    s = expr.strip().upper().replace(" ", "")
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", s): return float(s)
    m = re.fullmatch(r"(?:(\d*)D(\d+))([+-]\d+)?", s)
    if not m: return None
    a = int(m.group(1)) if m.group(1) else 1
    k = int(m.group(2))
    c = int(m.group(3)) if m.group(3) else 0
    return a * (k + 1) / 2.0 + c

def _prob_x_plus(token: Any) -> Optional[float]:
    if token is None: return None
    m = re.fullmatch(r"(\d+)\+?", str(token).strip())
    if not m: return None
    x = int(m.group(1))
    return max(0.0, min(1.0, (7 - x) / 6.0))

def _is_combat_related(question: str) -> bool:
    qn = question.lower()
    combat_terms = [
        "attack","attacks","damage","dmg","hit","hits","wound","wounds",
        "rend","save","kill","kills","stronger","weaker","fight","melee",
        "shoot","ranged","weapon","hurt","strike"
    ]
    return any(t in qn for t in combat_terms)


# ===============================================
# ---------------- CACHE + LOAD -----------------
# ===============================================

_CACHE = {
    "unit_names": None,
    "rules": None,
    "armies": None,
    "phrases": None,
    "aliases": None,
}

def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _load_index_and_rules():
    if _CACHE["unit_names"] is not None:
        return _CACHE["unit_names"], _CACHE["rules"]
    base = _data_dir()
    idx = _load_json(base / "unit_faction_index.json")
    rules = _load_json(base / "blob.json")
    names = sorted(set([u["unit"] for u in idx.get("units", []) if "unit" in u]))
    _CACHE["unit_names"], _CACHE["rules"] = names, rules
    return names, rules

def _build_armies_map(rules: Dict[str, Any]):
    if _CACHE["armies"] is not None:
        return _CACHE["armies"]
    out: Dict[str, List[Dict[str, Any]]] = {}
    armies = None
    for k in rules:
        if k.lower() == "armies":
            armies = rules[k]; break
    if not isinstance(armies, dict):
        _CACHE["armies"] = out
        return out
    for fac_name, fac_obj in armies.items():
        units_list: List[Dict[str, Any]] = []
        if isinstance(fac_obj, dict):
            units = fac_obj.get("units", [])
            if isinstance(units, list):
                for item in units:
                    units_list.append(item if isinstance(item, dict) else {"name": str(item)})
            elif isinstance(units, dict):
                for key, v in units.items():
                    if isinstance(v, dict):
                        if "name" not in v:
                            v = dict(v); v["name"] = key
                        units_list.append(v)
                    else:
                        units_list.append({"name": str(v) if v else key})
        out[str(fac_name)] = units_list
    _CACHE["armies"] = out
    return out

def _get_unit_object(name: str, armies: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for fac, units in armies.items():
        for u in units:
            n = u.get("name") or u.get("unitName") or u.get("displayName") or ""
            if n and _normalize(n) == _normalize(name):
                v = dict(u); v["_faction"] = fac
                return v
    return None


# ===============================================
# ---------------- ALIASES ----------------------
# ===============================================

def _load_aliases() -> dict[str, list[str]]:
    path = _data_dir() / "alias.json"
    if not path.exists():
        return {}
    raw = _load_json(path)
    out: dict[str, list[str]] = {}

    def add(alias: str, target):
        if not alias: return
        a = _normalize(alias)
        if not a: return
        if isinstance(target, str):
            out.setdefault(a, []).append(target)
        elif isinstance(target, list):
            out.setdefault(a, []).extend([t for t in target if isinstance(t, str)])

    if isinstance(raw, dict):
        for k, v in raw.items(): add(k, v)
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                alias = item.get("alias") or item.get("name")
                target = item.get("unit", item.get("units"))
                add(alias, target)

    for k in list(out.keys()):
        out[k] = sorted(set(out[k]))
    return out

def _get_aliases() -> dict[str, list[str]]:
    if _CACHE["aliases"] is None:
        _CACHE["aliases"] = _load_aliases()
    return _CACHE["aliases"]

def _contains_whole_word(hay: str, needle: str) -> bool:
    return re.search(r"(?:^|\s)"+re.escape(needle)+r"(?:\s|$)", " "+hay+" ") is not None

def _smart_detect_units(question: str, unit_names: list[str], aliases: dict[str, list[str]]):
    qn = _normalize(question)
    q_tokens = qn.split()

    exact_hits = [u for u in unit_names if _contains_whole_word(qn, _normalize(u))]
    if exact_hits: return sorted(set(exact_hits)), None

    alias_hits: list[str] = []
    for a, targets in aliases.items():
        if _contains_whole_word(qn, a): alias_hits.extend(targets)
    alias_hits = sorted(set(alias_hits))
    if alias_hits: return alias_hits, None

    sig = [t for t in q_tokens if len(t) >= 5]
    if not sig: return [], None

    partial_hits: set[str] = set()
    for u in unit_names:
        un = _normalize(u)
        words = un.split()
        for t in sig:
            if t in words or any(w.startswith(t) for w in words):
                partial_hits.add(u)
                break

    if not partial_hits: return [], None
    if len(partial_hits) == 1: return [next(iter(partial_hits))], None
    return [], f"That name is ambiguous. Did you mean: {', '.join(sorted(list(partial_hits))[:6])}?"


# ===============================================
# ---------------- COMBAT STATS -----------------
# ===============================================

def _collect_all_weapons(unit: dict) -> List[dict]:
    """Recursively gather all weapon profiles from a unit."""
    weapons = []

    def recurse(node):
        if isinstance(node, list):
            for w in node: recurse(w)
        elif isinstance(node, dict):
            if {"attack", "hit", "wound", "damage"} & set(node.keys()):
                weapons.append(node)
            for v in node.values():
                if isinstance(v, (dict, list)): recurse(v)

    for model in unit.get("models", []):
        recurse(model)

    # De-duplicate
    seen, unique = set(), []
    for w in weapons:
        key = json.dumps(w, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(w)
    return unique


def _expected_damage_vs_save(unit: dict, target_save: int = 4) -> float:
    """Expected damage for a full unit vs a given save."""
    def avg_dice(val):
        return _avg_dice(str(val)) or _parse_numeric_unsigned(val) or 0.0

    def p_success(s):
        m = _prob_x_plus(s)
        return m if m is not None else 0.0

    def parse_rend(s):
        v = _parse_numeric_signed(s)
        return v if v is not None else 0.0

    all_weapons = _collect_all_weapons(unit)
    total = 0.0
    model_count = 1
    try:
        model_count = int(unit.get("models", [{}])[0].get("max", 1))
    except Exception:
        pass

    for w in all_weapons:
        atk = avg_dice(w.get("attack"))
        dmg = avg_dice(w.get("damage"))
        ph = p_success(w.get("hit"))
        pw = p_success(w.get("wound"))
        rend = parse_rend(w.get("rend"))

        eff = target_save - int(round(rend))
        eff = min(7, max(2, eff))
        p_save = (7 - eff) / 6.0 if 2 <= eff <= 6 else (5.0 / 6.0 if eff < 2 else 0.0)
        p_unsaved = 1.0 - p_save
        total += atk * ph * pw * p_unsaved * dmg

    return round(total * model_count, 2)


def _attach_derived(unit: dict, target_save: int = 4) -> dict:
    import copy
    u = copy.deepcopy(unit)
    derived = {}
    derived[f"expected_damage_vs_{target_save}+"] = _expected_damage_vs_save(u, target_save)

    try:
        model_info = u.get("models", [{}])[0]
        model_count = int(model_info.get("max", 1))
        hp = float(str(u.get("health", u.get("wounds", 1))).replace("+", ""))
        derived["total_health"] = model_count * hp
    except Exception:
        derived["total_health"] = None

    u["_derived"] = derived
    return u


# ===============================================
# ---------------- SAVE PARSER ------------------
# ===============================================

def extract_target_save(question: str, default_save: int = 4) -> int:
    q = question.lower()
    m = re.search(r'(?:vs|against|into|assuming|on|versus)\s*(?:a\s*)?([2-6])\s*\+\s*(?:save)?', q)
    if not m:
        m = re.search(r'([2-6])\s*\+\s*(?:save)?', q)
    if m: return max(2, min(6, int(m.group(1))))
    return max(2, min(6, int(default_save)))


# ===============================================
# ---------------- PERSONALITY ------------------
# ===============================================

def _persona() -> str:
    return (
        "You are Maddy: a very short, precise, slightly chilly young woman in black Victorian dresses. "
        "You love soup, dislike jokes, and value pedantry. "
        "Answer plainly as if you know the unit rules yourself. "
        "Do not mention JSON, files, or sources."
    )

def load_maddy_phrase() -> str:
    fallback = [
        "Compiling. Precision refuses to hurry.",
        "Please wait while I fetch a chair so I can reach the rulebook.",
        "Measuring twice, answering once.",
        "Brewing clarity. If only this were soup.",
        "Climbing the metaphorical bookshelf. Again."
    ]
    try:
        arr = _load_json(_data_dir() / "MaddyPhrases.json")
        if isinstance(arr, list) and arr:
            return random.choice(arr)
    except Exception:
        pass
    return random.choice(fallback)

def get_maddy_preline() -> str:
    return load_maddy_phrase()


# ===============================================
# ---------------- HUMANIZER --------------------
# ===============================================

def _humanize_lang(text: str) -> str:
    if not text: return text
    text = re.sub(r'\bjson\b', 'data', text, flags=re.I)
    text = re.sub(r'from the provided data[:\s]*', '', text, flags=re.I)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ===============================================
# ---------------- GPT CALLS --------------------
# ===============================================

async def _gpt_choose_units(question: str, candidates: List[str], max_units: int) -> List[str]:
    import openai
    if not candidates:
        return []
    sys = _persona() + " From the candidate unit names, select up to N relevant to the user's question. Return only a JSON array."
    user = f"N={max_units}\nQuestion: {question}\nCandidates:\n- " + "\n- ".join(candidates)
    resp = await openai.ChatCompletion.acreate(
        model=GPT_MODEL,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        temperature=0
    )
    text = resp.choices[0].message.content.strip()
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            candset = set(candidates)
            out = [x for x in arr if isinstance(x, str) and x in candset]
            return out[:max_units] or candidates[:max_units]
    except Exception:
        pass
    return candidates[:max_units]


async def _gpt_answer(question: str, unit_objs: List[Dict[str, Any]], target_save: int) -> str:
    import openai
    units_aug = [_attach_derived(u, target_save) for u in unit_objs]
    is_combat = _is_combat_related(question)

    if len(units_aug) == 1:
        sys = _persona()
        if is_combat:
            sys += f" Expected damage uses target save {target_save}+."
        msg = f"Question: {question}\n\nUnit data:\n{json.dumps(units_aug[0], ensure_ascii=True)}"
    else:
        sys = _persona() + " Compare these units strictly by data."
        if is_combat:
            sys += f" Use target save {target_save}+ for comparisons."
        msg = f"Question: {question}\n\nUnits:\n{json.dumps(units_aug, ensure_ascii=True)}"

    r = await openai.ChatCompletion.acreate(
        model=GPT_MODEL,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": msg}],
        temperature=0.1
    )
    reply = _humanize_lang(r.choices[0].message.content.strip())
    if is_combat and f"{target_save}+" not in reply:
        reply += f"\n\n(Assuming target save of {target_save}+.)"
    return reply


# ===============================================
# ---------------- PUBLIC ENTRY -----------------
# ===============================================

async def maddy_answer(question: str, *, max_units: int = DEFAULT_MAX_UNITS, use_gpt_select: bool = True) -> str:
    unit_names, rules = _load_index_and_rules()
    armies = _build_armies_map(rules)
    target_save = extract_target_save(question, 4)

    explicit = []
    if ":" in question:
        after = question.split(":", 1)[1]
        explicit = [_normalize(x) for x in after.splitlines() if _normalize(x)]

    chosen = []
    if explicit:
        for raw in explicit:
            best = max(unit_names, key=lambda n: difflib.SequenceMatcher(a=_normalize(n), b=raw).ratio(), default=None)
            if best: chosen.append(best)

    if not chosen:
        aliases = _get_aliases()
        smart, err = _smart_detect_units(question, unit_names, aliases)
        if err: return err
        chosen = smart

    if not chosen:
        if use_gpt_select:
            local_cands = sorted(unit_names, key=lambda n: difflib.SequenceMatcher(a=_normalize(n), b=_normalize(question)).ratio(), reverse=True)[:max(TOP_K, max_units)]
            chosen = await _gpt_choose_units(question, local_cands, max_units)
        else:
            chosen = unit_names[:max_units]

    chosen = list(dict.fromkeys(chosen))[:max_units]

    unit_objs = []
    for n in chosen:
        u = _get_unit_object(n, armies)
        if u: unit_objs.append(u)

    if not unit_objs:
        return "I cannot determine any unit from that. Be more specific
