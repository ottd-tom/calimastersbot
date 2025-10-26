# maddybot.py
import os, re, json, difflib, random
from pathlib import Path
from typing import Any, Dict, List, Optional

# ------------ Config ------------
GPT_MODEL = os.getenv("MADDY_GPT_MODEL", "gpt-4o-mini")
DEFAULT_MAX_UNITS = 5
TOP_K = 8
# Optionally set MADDY_DATA_DIR env; else use ./data
def _data_dir() -> Path:
    env = os.getenv("MADDY_DATA_DIR")
    return Path(env) if env else (Path(__file__).parent / "data")
# --------------------------------

# ------------ Basic utils ------------
def _normalize(s: str) -> str:
    s = s.lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return re.sub(r"\s+", " ", s).strip()

def _parse_numeric(value: Any) -> Optional[float]:
    if value is None: return None
    if isinstance(value, (int, float)): return float(value)
    s = str(value).strip().replace('"', "").replace("”", "").replace("“", "").rstrip("+")
    if re.fullmatch(r"\d+(\.\d+)?", s): return float(s)
    m = re.search(r"(\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else None

def _avg_dice(expr: str) -> Optional[float]:
    s = expr.strip().upper().replace(" ", "")
    if re.fullmatch(r"\d+(\.\d+)?", s): return float(s)
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
# -------------------------------------

# ------------ Data load (cached) ------------
_CACHE = {
    "unit_names": None,
    "rules": None,
    "armies": None,
    "phrases": None,
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
    names = [u["unit"] for u in idx.get("units", []) if "unit" in u]
    names = sorted(set(names))
    _CACHE["unit_names"] = names
    _CACHE["rules"] = rules
    return names, rules

def _build_armies_map(rules: Dict[str, Any]):
    if _CACHE["armies"] is not None:
        return _CACHE["armies"]
    out: Dict[str, List[Dict[str, Any]]] = {}
    armies = None
    if isinstance(rules, dict):
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
# --------------------------------------------

# ------------ Selection helpers ------------
def _contains_word(hay_norm: str, needle_norm: str) -> bool:
    return re.search(r"(?:^|\s)"+re.escape(needle_norm)+r"(?:\s|$)", " "+hay_norm+" ") is not None

def _partial_ratio(a: str, b: str) -> float:
    if not a or not b: return 0.0
    la, lb = len(a), len(b)
    if lb <= la: return difflib.SequenceMatcher(a=a, b=b).ratio()
    m = 0.0
    for i in range(lb - la + 1):
        r = difflib.SequenceMatcher(a=a, b=b[i:i+la]).ratio()
        if r > m: m = r
    toks = b.split()
    for w in range(1, min(6, len(toks)) + 1):
        for i in range(0, len(toks) - w + 1):
            sub = " ".join(toks[i:i+w])
            r = difflib.SequenceMatcher(a=a, b=sub).ratio()
            if r > m: m = r
    return m

def _score_against_question(name: str, qnorm: str) -> float:
    nn = _normalize(name)
    if nn and _contains_word(qnorm, nn): return 1.10
    return max(_partial_ratio(nn, qnorm), difflib.SequenceMatcher(a=nn, b=qnorm).ratio())

def _local_top_candidates(question: str, unit_names: List[str], k: int) -> List[str]:
    qn = _normalize(question)
    scored = [(n, _score_against_question(n, qn)) for n in unit_names]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [n for n,_ in scored[:k]]

def _parse_explicit_list(question: str) -> List[str]:
    if ":" not in question: return []
    after = question.split(":", 1)[1]
    lines = [_normalize(x) for x in after.splitlines() if _normalize(x)]
    return lines

def _map_names_to_units(raw_names: List[str], unit_names: List[str]) -> List[str]:
    if not raw_names: return []
    results: List[str] = []
    for raw in raw_names:
        best = None; best_s = 0.0
        for u in unit_names:
            s = difflib.SequenceMatcher(a=_normalize(u), b=raw).ratio()
            if s > best_s:
                best_s = s; best = u
        if best and best not in results:
            results.append(best)
    return results
# ----------------------------------------

# ------------ Derived stats ------------
def _estimate_model_count(unit: Dict[str, Any]) -> Optional[int]:
    models = unit.get("models")
    if isinstance(models, list) and models:
        m0 = models[0]
        if isinstance(m0, dict):
            num = _parse_numeric(m0.get("max"))
            if num is not None:
                try: return int(num)
                except: pass
    bp = unit.get("battleProfile") or {}
    if isinstance(bp, dict):
        num = _parse_numeric(bp.get("unit_size"))
        if num is not None:
            try: return int(num)
            except: pass
    return None

def _iter_weapon_groups(unit: Dict[str, Any]):
    models = unit.get("models")
    if not isinstance(models, list): return
    for m in models:
        if not isinstance(m, dict): continue
        w = m.get("weapons") or {}
        for bucket in ("basic", "advanced", "selected"):
            b = w.get(bucket)
            if isinstance(b, dict):
                for _, group in b.items():
                    if isinstance(group, dict):
                        yield group

def _count_per_model_from_group(group: Dict[str, Any]) -> float:
    per = str(group.get("per", "")).lower()
    minc = _parse_numeric(group.get("min"))
    maxc = _parse_numeric(group.get("max"))
    if per == "model":
        if minc is not None: return float(minc)
        if maxc is not None: return float(maxc)
        return 1.0
    return 1.0

def _is_melee_type(t):  return t in (0, "melee", "Melee", "MELEE")
def _is_ranged_type(t): return t in (1, "ranged", "Ranged", "RANGED")

def _expected_damage_per_model(unit: Dict[str, Any], *, melee: Optional[bool]) -> Optional[float]:
    total = 0.0
    found = False
    model_count = _estimate_model_count(unit) or 1
    for group in _iter_weapon_groups(unit):
        profs = group.get("weapons")
        if not isinstance(profs, list): continue
        cpm = _count_per_model_from_group(group)
        for prof in profs:
            if not isinstance(prof, dict): continue
            t = prof.get("type")
            if melee is True and not _is_melee_type(t):   continue
            if melee is False and not _is_ranged_type(t): continue
            atk = _parse_numeric(prof.get("attack"))
            dmg_raw = prof.get("damage")
            avgd = _parse_numeric(dmg_raw)
            if avgd is None and isinstance(dmg_raw, str): avgd = _avg_dice(dmg_raw)
            ph = _prob_x_plus(prof.get("hit"))
            pw = _prob_x_plus(prof.get("wound"))
            if atk is None or avgd is None or ph is None or pw is None:
                continue
            per = str(group.get("per", "")).lower()
            per_model_multiplier = cpm if per == "model" else (cpm / model_count if model_count else cpm)
            total += per_model_multiplier * atk * ph * pw * avgd
            found = True
    return total if found else None

def _derive_fields(unit: Dict[str, Any]) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    count = _estimate_model_count(unit)
    if count is not None: d["_unit_model_count"] = count
    per_model_health = _parse_numeric(unit.get("health", unit.get("wounds")))
    if per_model_health is not None:
        d["_per_model_health"] = per_model_health
        if count is not None: d["_unit_total_health"] = per_model_health * count
    melee_pm = _expected_damage_per_model(unit, melee=True)
    if melee_pm is not None:
        d["_per_model_expected_melee"] = melee_pm
        if count is not None: d["_unit_expected_melee"] = melee_pm * count
    ranged_pm = _expected_damage_per_model(unit, melee=False)
    if ranged_pm is not None:
        d["_per_model_expected_ranged"] = ranged_pm
        if count is not None: d["_unit_expected_ranged"] = ranged_pm * count
    d["_notes"] = [
        "Expected damage = attacks * P(hit) * P(wound) * avg(damage), summed across profiles.",
        "Totals multiply per-model by model count. No rerolls/mods. Ignores enemy saves/rend.",
        "P(X+)=(7-X)/6. Dice averages: D3=2, D6=3.5, etc."
    ]
    return d

def _attach_derived(unit: Dict[str, Any]) -> Dict[str, Any]:
    v = dict(unit)
    v["_derived"] = _derive_fields(unit)
    return v
# --------------------------------------

# ------------ Personality ------------
def _persona() -> str:
    return (
        "You are Maddy: a very short, precise, slightly chilly young woman in black Victorian dresses. "
        "You love soup, dislike jokes (and know it), and value pedantry. Your tone is dry and careful. "
        "Answers MUST be grounded strictly in the provided JSON; if something is missing, say so."
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
# -------------------------------------

# ------------ GPT calls (async, discord-friendly) ------------
async def _gpt_choose_units(question: str, candidates: List[str], max_units: int) -> List[str]:
    import openai
    if not candidates:
        return []
    sys = _persona() + " From the candidate unit names, select up to N relevant to the user's question. Return only a JSON array of strings."
    user = f"N={max_units}\nQuestion: {question}\nCandidates:\n- " + "\n- ".join(candidates)
    resp = await openai.ChatCompletion.acreate(
        model=GPT_MODEL,
        messages=[{"role":"system","content":sys},{"role":"user","content":user}],
        temperature=0
    )
    text = resp.choices[0].message.content.strip()
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            candset = {c: True for c in candidates}
            out = []
            for x in arr:
                if isinstance(x, str) and x in candset and x not in out:
                    out.append(x)
            return out[:max_units] or candidates[:max_units]
    except Exception:
        pass
    return candidates[:max_units]

async def _gpt_answer(question: str, unit_objs: List[Dict[str, Any]]) -> str:
    import openai
    units_aug = [_attach_derived(u) for u in unit_objs]
    if len(units_aug) == 1:
        sys = (
            _persona() + " Answer strictly and only from the provided unit JSON. "
            "For damage or total health, use the _derived totals. "
            "Expected damage = attacks * P(hit) * P(wound) * avg(damage), summed over profiles; "
            "multiply per-model by _derived._unit_model_count. No rerolls/mods; ignore enemy saves/rend. Be concise."
        )
        msg = f"Question: {question}\n\nUnit JSON (full, with _derived):\n{json.dumps(units_aug[0], ensure_ascii=True)}"
    else:
        sys = (
            _persona() + " Compare the units strictly from the provided JSON. "
            "Use _derived._unit_expected_melee/_ranged and _unit_total_health when relevant. "
            "If any required value is missing or non-numeric, say so and compare what is available. Be concise."
        )
        bundle = [{"name": u.get("name","(unknown)"), "unit": _attach_derived(u)} for u in unit_objs]
        msg = f"Question: {question}\n\nUnits JSON array (full, with _derived):\n{json.dumps(bundle, ensure_ascii=True)}"

    r = await openai.ChatCompletion.acreate(
        model=GPT_MODEL,
        messages=[{"role":"system","content":sys},{"role":"user","content":msg}],
        temperature=0.1
    )
    return r.choices[0].message.content.strip()
# -------------------------------------------------------------
def get_maddy_preline() -> str:
    return load_maddy_phrase()

# ------------ Public API (answer only; no pre-line) ------------
async def maddy_answer(
    question: str,
    *,
    max_units: int = DEFAULT_MAX_UNITS,
    use_gpt_select: bool = True
) -> str:
    """
    Returns the final answer string (no pre-line).
    """
    unit_names, rules = _load_index_and_rules()
    armies = _build_armies_map(rules)

    explicit = _parse_explicit_list(question)
    chosen = _map_names_to_units(explicit, unit_names) if explicit else []

    if not chosen:
        if use_gpt_select:
            local_cands = _local_top_candidates(question, unit_names, k=max(TOP_K, max_units))
            chosen = await _gpt_choose_units(question, local_cands, max_units=max_units)
        else:
            chosen = _local_top_candidates(question, unit_names, k=max_units)

    unit_objs: List[Dict[str, Any]] = []
    for name in chosen:
        obj = _get_unit_object(name, armies)
        if obj:
            unit_objs.append(obj)

    if not unit_objs:
        return "I cannot determine any unit from that. Be more specific."

    return await _gpt_answer(question, unit_objs)
