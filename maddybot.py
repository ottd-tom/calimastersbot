# maddybot.py
import os, re, json, difflib, random
from pathlib import Path
from typing import Any, Dict, List, Optional

# ------------ Config ------------
GPT_MODEL = os.getenv("MADDY_GPT_MODEL", "gpt-4o-mini")
DEFAULT_MAX_UNITS = 5
TOP_K = 8
def _data_dir() -> Path:
    env = os.getenv("MADDY_DATA_DIR")
    return Path(env) if env else (Path(__file__).parent / "data")
# --------------------------------

# ------------ Basic utils ------------
def _normalize(s: str) -> str:
    s = s.lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    return re.sub(r"\s+", " ", s).strip()

def _parse_numeric_unsigned(value: Any) -> Optional[float]:
    """Unsigned numeric parse (legacy)."""
    if value is None: return None
    if isinstance(value, (int, float)): return float(value)
    s = str(value).strip().replace('"', "").replace("”", "").replace("“", "").rstrip("+")
    if re.fullmatch(r"\d+(\.\d+)?", s): return float(s)
    m = re.search(r"(\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else None

def _parse_numeric_signed(value: Any) -> Optional[float]:
    """Signed parse for things like rend -1, -2, +1, etc."""
    if value is None: return None
    if isinstance(value, (int, float)): return float(value)
    s = str(value).strip()
    s = s.replace("−", "-")  # Unicode minus
    s = s.replace('"', "").replace("”", "").replace("“", "")
    # Allow optional sign
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", s):
        return float(s)
    m = re.search(r"([+-]?\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else None

def _avg_dice(expr: str) -> Optional[float]:
    """Average of dice like D3, D6, 2D6, D3+1, 2D3+3."""
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
# -------------------------------------

# ------------ Data load (cached) ------------
_CACHE = {
    "unit_names": None,
    "rules": None,
    "armies": None,
    "phrases": None,
    "aliases": None,
}

def _get_aliases() -> dict[str, list[str]]:
    if _CACHE["aliases"] is None:
        _CACHE["aliases"] = _load_aliases()
    return _CACHE["aliases"]


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



# ===== Aliases =====
def _load_aliases() -> dict[str, list[str]]:
    """
    Load alias -> [unit names] from data/alias.json.
    Accepts dict {alias: unit|[units]} or list of {alias, unit|units}.
    Returns {normalized_alias: [unit1, unit2, ...]}
    """
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
        for k, v in raw.items():
            add(k, v)
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict): continue
            alias = item.get("alias") or item.get("name")
            target = item.get("unit", item.get("units"))
            add(alias, target)
    # de-dup
    for k in list(out.keys()):
        out[k] = sorted(set(out[k]))
    return out

def _contains_whole_word(hay: str, needle: str) -> bool:
    return re.search(r"(?:^|\s)"+re.escape(needle)+r"(?:\s|$)", " "+hay+" ") is not None

def _smart_detect_units(question: str, unit_names: list[str], aliases: dict[str, list[str]]) -> tuple[list[str], Optional[str]]:
    """
    Resolution order:
      A) Exact unit name appears as a whole word in the question -> return those (can be multiple).
      B) Alias matches (whole-word) -> return alias targets (can be multiple).
      C) Clean partials:
         - If a question token (>=5 chars) equals the *start* of a unit name word
           or equals a whole unit name word -> count it.
         - If exactly one unit matches -> return it.
         - If multiple -> ambiguous.
      D) If no hits -> [] (let caller decide to try fuzzy).
    """
    qn = _normalize(question)
    q_tokens = qn.split()

    # A) Exact whole-name hit
    exact_hits: list[str] = []
    for u in unit_names:
        un = _normalize(u)
        if _contains_whole_word(qn, un):
            exact_hits.append(u)
    if exact_hits:
        return sorted(set(exact_hits)), None

    # B) Aliases (whole-word)
    alias_hits: list[str] = []
    for a, targets in aliases.items():
        if _contains_whole_word(qn, a):
            alias_hits.extend(targets)
    alias_hits = sorted(set(alias_hits))
    if alias_hits:
        return alias_hits, None

    # C) Clean partials using stricter token rule
    #    use tokens >=5 chars to reduce collisions (e.g., chaos vs kairos)
    sig = [t for t in q_tokens if len(t) >= 5]
    if not sig:
        return [], None

    partial_hits: set[str] = set()
    for u in unit_names:
        un = _normalize(u)
        words = un.split()
        for t in sig:
            # match whole word OR word-prefix (e.g., 'kairos' -> 'kairos fateweaver')
            if t in words or any(w.startswith(t) for w in words):
                partial_hits.add(u)
                break

    if not partial_hits:
        return [], None
    if len(partial_hits) == 1:
        return [next(iter(partial_hits))], None

    # D) Ambiguous partials
    return [], f"That name is ambiguous. Did you mean: {', '.join(sorted(list(partial_hits))[:6])}?"





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
    q_tokens = qn.split()
    sig = {t for t in q_tokens if len(t) >= 5}

    def token_overlap(uname_norm: str) -> bool:
        if not sig:  # if no strong tokens, allow overlap-free (rare)
            return True
        w = set(uname_norm.split())
        # unit includes a strong token as word or the unit has a word that starts with it
        if w & sig:
            return True
        for t in sig:
            if any(uw.startswith(t) for uw in w):
                return True
        return False

    scored: List[tuple[str, float]] = []
    for n in unit_names:
        un = _normalize(n)
        if not token_overlap(un):
            continue
        s = _score_against_question(n, qn)
        scored.append((n, s))

    if not scored:
        # as a last resort, keep old behavior
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

# ------------ Derived stats (no-save baseline) ------------
def _estimate_model_count(unit: Dict[str, Any]) -> Optional[int]:
    models = unit.get("models")
    if isinstance(models, list) and models:
        m0 = models[0]
        if isinstance(m0, dict):
            num = _parse_numeric_unsigned(m0.get("max"))
            if num is not None:
                try: return int(num)
                except: pass
    bp = unit.get("battleProfile") or {}
    if isinstance(bp, dict):
        num = _parse_numeric_unsigned(bp.get("unit_size"))
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
    minc = _parse_numeric_unsigned(group.get("min"))
    maxc = _parse_numeric_unsigned(group.get("max"))
    if per == "model":
        if minc is not None: return float(minc)
        if maxc is not None: return float(maxc)
        return 1.0
    return 1.0

def _is_melee_type(t):  return t in (0, "melee", "Melee", "MELEE")
def _is_ranged_type(t): return t in (1, "ranged", "Ranged", "RANGED")

# --- NEW: expected damage vs a target save (includes rend, random attacks/damage) ---
def _expected_damage_per_model_vs_save(unit: Dict[str, Any], *, melee: Optional[bool], target_save: int) -> Optional[float]:
    """
    Expected unsaved damage per model vs a defender with save = target_save (2..6).
    Includes:
      - E(attacks) with dice averages,
      - P(hit), P(wound),
      - rend (signed, e.g., -1),
      - E(damage) with dice averages.
    """
    total = 0.0
    found = False
    model_count = _estimate_model_count(unit) or 1
    base_save = int(target_save)
    base_save = min(6, max(2, base_save))

    for group in _iter_weapon_groups(unit):
        profs = group.get("weapons")
        if not isinstance(profs, list): continue
        cpm = _count_per_model_from_group(group)  # per model if per=="Model", else 1
        for prof in profs:
            if not isinstance(prof, dict): continue
            t = prof.get("type")
            if melee is True and not _is_melee_type(t):   continue
            if melee is False and not _is_ranged_type(t): continue

            # E(attacks)
            atk_raw = prof.get("attack")
            atk = None
            if isinstance(atk_raw, (int, float)):
                atk = float(atk_raw)
            elif isinstance(atk_raw, str):
                atk = _avg_dice(atk_raw)
                if atk is None:
                    atk = _parse_numeric_unsigned(atk_raw)
            else:
                atk = _parse_numeric_unsigned(atk_raw)

            # E(damage)
            dmg_raw = prof.get("damage")
            avgd = None
            if isinstance(dmg_raw, (int, float)):
                avgd = float(dmg_raw)
            elif isinstance(dmg_raw, str):
                avgd = _avg_dice(dmg_raw)
                if avgd is None:
                    avgd = _parse_numeric_unsigned(dmg_raw)
            else:
                avgd = _parse_numeric_unsigned(dmg_raw)

            ph = _prob_x_plus(prof.get("hit"))
            pw = _prob_x_plus(prof.get("wound"))
            # Rend (signed)
            rend_val = _parse_numeric_signed(prof.get("rend"))
            if rend_val is None:
                rend_val = 0.0

            if atk is None or avgd is None or ph is None or pw is None:
                continue

            # Effective save after rend. AoS: save roll needed = base_save - rend.
            eff = base_save - int(round(rend_val))
            # Clamp/save probabilities: best is 2+ (5/6), worst is >6 (0)
            if eff < 2:
                p_save = 5.0/6.0
            elif eff <= 6:
                p_save = (7 - eff) / 6.0
            else:
                p_save = 0.0

            p_unsaved = 1.0 - p_save

            per = str(group.get("per", "")).lower()
            per_model_multiplier = cpm if per == "model" else (cpm / model_count if model_count else cpm)
            # Multiply by E(attacks) * ph * pw * p_unsaved * E(damage)
            total += per_model_multiplier * atk * ph * pw * p_unsaved * avgd
            found = True

    return total if found else None

def _derive_fields(unit: Dict[str, Any]) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    count = _estimate_model_count(unit)
    if count is not None: d["_unit_model_count"] = count
    per_model_health = _parse_numeric_unsigned(unit.get("health", unit.get("wounds")))
    if per_model_health is not None:
        d["_per_model_health"] = per_model_health
        if count is not None: d["_unit_total_health"] = per_model_health * count
    # Keep the no-save baseline (may still be useful for general questions)
    d["_notes"] = [
        "Expected damage uses dice averages; totals multiply per-model by model count. "
        "No rerolls/modifiers. Ignores wards and special rules."
    ]
    return d

def _attach_derived(unit: Dict[str, Any]) -> Dict[str, Any]:
    v = dict(unit)
    v["_derived"] = _derive_fields(unit)
    return v
# --------------------------------------

# ------------ Parse target save from the question ------------
def extract_target_save(question: str, default_save: int = 4) -> int:
    """
    Find a token like '3+', '4+', '5+ save', optionally after 'vs/against/assuming'.
    Returns 2..6; defaults to 4 if absent.
    """
    q = question.lower()
    # prefer forms explicitly tied to save
    m = re.search(r'(?:vs|against|into|assuming|on|versus)\s*(?:a\s*)?([2-6])\s*\+\s*(?:save)?', q)
    if not m:
        # any lone 'X+' mention
        m = re.search(r'([2-6])\s*\+\s*(?:save)?', q)
    if m:
        return max(2, min(6, int(m.group(1))))
    return max(2, min(6, int(default_save)))
# -------------------------------------------------------------

# ------------ Personality ------------
def _persona() -> str:
    return (
        "You are Maddy: a very short, precise, slightly chilly young woman in black Victorian dresses. "
        "You love soup, dislike jokes (and know it), and value pedantry. Your tone is dry and careful. "
        "Answer plainly as if you know the unit rules yourself. Do not mention files, JSON, or sources."
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
# -------------------------------------

# ------------ Output sanitizer ------------
def _humanize_lang(text: str) -> str:
    if not text: return text
    text = re.sub(r'^\s*from the provided json\s*:\s*$', '', text, flags=re.I|re.M)
    text = re.sub(r'^\s*from the json\s*:\s*$', '', text, flags=re.I|re.M)
    text = re.sub(r'\bprovided\s+json\b', 'the unit data', text, flags=re.I)
    text = re.sub(r'\bthe\s+json\b', 'the unit data', text, flags=re.I)
    text = re.sub(r'\bjson\b', 'data', text, flags=re.I)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
# ------------------------------------------

# ------------ GPT calls (async) ------------
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

def _build_query_context(units: List[Dict[str, Any]], target_save: int) -> Dict[str, Any]:
    """
    Build small per-unit metrics against a specified save so GPT can just report it.
    """
    out = {
        "target_save_plus": f"{target_save}+",
        "units": []
    }
    for u in units:
        name = u.get("name", "(unknown)")
        fac  = u.get("_faction", "")
        mc   = _estimate_model_count(u) or 1
        melee_pm = _expected_damage_per_model_vs_save(u, melee=True,  target_save=target_save)
        ranged_pm= _expected_damage_per_model_vs_save(u, melee=False, target_save=target_save)
        rec = {
            "name": name,
            "faction": fac,
            "models": mc,
            "per_model_expected_melee_vs_save": melee_pm,
            "per_model_expected_ranged_vs_save": ranged_pm,
            "unit_expected_melee_vs_save": (melee_pm * mc) if melee_pm is not None else None,
            "unit_expected_ranged_vs_save": (ranged_pm * mc) if ranged_pm is not None else None,
        }
        out["units"].append(rec)
    return out

async def _gpt_answer(question: str, unit_objs: List[Dict[str, Any]], target_save: int) -> str:
    import openai
    # Include derived (non-save) base plus per-question vs-save context.
    units_aug = [_attach_derived(u) for u in unit_objs]
    ctx = _build_query_context(unit_objs, target_save=target_save)

    if len(units_aug) == 1:
        sys = (
            _persona() + " "
            "Answer based strictly on the data below, but do NOT mention files/JSON/sources. "
            "Assume the opponent has a {sv}+ save unless the user specified otherwise; always state the save you used. "
            "Use the precomputed values in 'context' for damage vs save when relevant. "
            "No rerolls/modifiers; ignore wards and special rules. Be concise and natural."
        ).format(sv=target_save)
        msg = (
            f"Question: {question}\n\n"
            f"Unit (full data with _derived):\n{json.dumps(units_aug[0], ensure_ascii=True)}\n\n"
            f"context:\n{json.dumps(ctx, ensure_ascii=True)}"
        )
    else:
        sys = (
            _persona() + " "
            "Compare the units strictly from the data below, without mentioning files/JSON/sources. "
            "Assume the opponent has a {sv}+ save unless the user specified otherwise; always state the save you used. "
            "Use 'context' for damage vs save. No rerolls/modifiers; ignore wards and special rules. Be concise."
        ).format(sv=target_save)
        bundle = [{"name": u.get("name","(unknown)"), "unit": _attach_derived(u)} for u in unit_objs]
        msg = (
            f"Question: {question}\n\n"
            f"Units (each has _derived):\n{json.dumps(bundle, ensure_ascii=True)}\n\n"
            f"context:\n{json.dumps(ctx, ensure_ascii=True)}"
        )

    r = await openai.ChatCompletion.acreate(
        model=GPT_MODEL,
        messages=[{"role":"system","content":sys},{"role":"user","content":msg}],
        temperature=0.1
    )
    reply = r.choices[0].message.content.strip()
    return _humanize_lang(reply)
# -------------------------------------------------------------

# ------------ Public API ------------
async def maddy_answer(
    question: str,
    *,
    max_units: int = DEFAULT_MAX_UNITS,
    use_gpt_select: bool = True
) -> str:
    """
    Resolve unit(s) from the user's question (exact > alias > partial, with ambiguity guard),
    detect/assume a defender save (default 4+), and return Maddy's final answer.
    If a partial name is ambiguous (and no exact match exists), returns a short disambiguation string.

    Args:
        question: The user's natural-language question.
        max_units: Cap on units we’ll pass to GPT for answering/compare.
        use_gpt_select: If no unit can be resolved locally, allow GPT to choose from a small candidate set.

    Returns:
        A natural-language answer string (no pre-line). Always states the defender save used.
    """
    # Load rules/index and build faction->units map
    unit_names, rules = _load_index_and_rules()
    armies = _build_armies_map(rules)

    # Parse defender save from the question (fallback 4+)
    target_save = extract_target_save(question, default_save=4)

    # 1) Explicit "list" style (e.g., "Which of the following: ...")
    explicit = _parse_explicit_list(question)
    chosen: List[str] = _map_names_to_units(explicit, unit_names) if explicit else []

    # 2) Smart detection (exact name hit > alias map > partial tokens)
    if not chosen:
        aliases = _get_aliases()
        smart, err = _smart_detect_units(question, unit_names, aliases)
        if err:
            # Ambiguous partial (no exact match) — tell the user
            return err
        chosen = smart

    # 3) Fallback selection if still nothing: local fuzzy (then optional GPT pick)
    if not chosen:
        if use_gpt_select:
            local_cands = _local_top_candidates(question, unit_names, k=max(TOP_K, max_units))
            chosen = await _gpt_choose_units(question, local_cands, max_units=max_units)
        else:
            chosen = _local_top_candidates(question, unit_names, k=max_units)

    # De-dupe and cap
    if chosen:
        seen = set(); deduped = []
        for n in chosen:
            if n not in seen:
                deduped.append(n); seen.add(n)
        chosen = deduped[:max_units]

    # Resolve names -> full unit objects from armies
    unit_objs: List[Dict[str, Any]] = []
    for name in chosen:
        obj = _get_unit_object(name, armies)
        if obj:
            unit_objs.append(obj)

    if not unit_objs:
        return "I cannot determine any unit from that. Be more specific."

    # Compose final answer (includes stating the save used)
    return await _gpt_answer(question, unit_objs, target_save=target_save)

# ------------------------------------
