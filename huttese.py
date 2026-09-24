"""
Huttese translation for the Jabbabot persona.

Lexicon transcribed from the Basic-Huttese dictionary at
https://mystwarscollection.weebly.com/how-to-speak-huttese.html
(compiled by "The Complete Wermo's Guide"). Canon entries — words sourced from
the films and games — are listed first; the guide's non-canon additions are in
the second block and are easy to trim if you'd rather stay canon-only.

Design: translation is a deterministic dictionary substitution, so the guide
drives the output rather than the model's own idea of Huttese. The GPT pass in
huttese_answer() is optional polish and is handed only the words that actually
matched, with instructions never to invent new ones. If OpenAI is unavailable
the persona still works — it just returns the straight substitution.

    translate("My friend is a big fool")
    -> ("Ma pateesa is a porko stupa", TranslationStats(matched=4, total=6, ...))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import openai

# ── Lexicon ──────────────────────────────────────────────────────────────────
# Basic -> Huttese. Multi-word keys are matched before single words.
# Where the guide lists several options, the most recognisable is used.

CANON: dict[str, str] = {
    "a": "du", "activate": "rundee", "alone": "solo", "amazing": "inkabunga",
    "and": "an", "another": "andoba", "antennae": "tenya", "any": "kickee",
    "anybody": "kickeeyuna", "around": "dee boonkee", "away": "neechu",
    "backstage": "backa", "bad": "goola", "band": "banda", "bargain": "bargon",
    "back": "bata", "bed": "koga", "bet": "buttmalia", "better": "mo gootu",
    "big": "porko", "big-time": "porkman", "blaster": "blastoh", "body": "yuna",
    "boss": "lorda", "bother": "baatu baatu", "bounty hunter": "murishani",
    "boy": "peedunkee", "brain damage": "rocka rocka", "bring": "koose",
    "burnout": "skocha", "burp": "howdunga", "business": "poonoo", "buy": "bedwana",
    "cake": "waffmula", "can i": "kavaa", "careful": "chess ko",
    "challenge": "hodrudda", "champion": "champio", "charge": "chinka",
    "cheat": "cheeska", "check": "wabdah", "classic": "magi",
    "competition": "hodrudda", "computer program": "pogwa",
    "confederacy": "confeeba", "consider": "ka tinka", "contract": "niboba",
    "crazy": "loca", "credit": "creeda", "credit card": "creeta", "crop": "von",
    "cruiser": "teesaw", "curse": "fierfek", "dammit": "chuba",
    "dancers": "whirlee", "dancing girl": "chik youngee", "dangerous": "azalus",
    "deal": "bargon", "dessert": "lickmoomoo", "die": "nee choo",
    "do not": "hagwa", "don't": "hagwa", "double": "fofo",
    "double-crossing": "dopa-meeky", "dowager": "dowahga", "drink": "yocola",
    "droid": "droi", "droids": "droida", "drool": "sleemo poy", "drop": "hasa",
    "dump": "dumpa", "dusters": "dusta", "ejector seat": "keejeckta",
    "engine": "bota", "engines": "bota", "enjoy": "panwa", "every": "miki",
    "everybody": "mikiyuna", "excuse me": "chut chut", "fancy": "lapti",
    "fast": "shado", "faster": "gran shado", "fellow": "footoo", "film": "holo",
    "final": "fa", "first class": "yuna puna", "fodder": "poodoo",
    "fool": "stupa", "for": "che", "foreigner": "outmian", "fresh": "flootah",
    "friend": "pateesa", "from": "tuta", "front line": "tula moosta",
    "fry": "crispo", "garden": "bootana", "gardens": "bootana",
    "get out": "pushee", "glorious": "grandio", "go": "bolla", "going": "koona",
    "good-bye": "me jewz ku", "goodbye": "me jewz ku", "grand": "granee",
    "great": "grancha", "greetings": "h'chu apenkee", "guards": "gardo",
    "gun": "wanga", "hail": "yavoo", "hands": "kapa", "hazardous": "azalus",
    "he is": "hees", "hello": "achuta", "help": "hopa", "her": "cheekta",
    "here": "wata", "here is": "vota", "hex": "fierfek", "holonet": "halapu",
    "hot": "hotsa", "home": "bunky dunko", "host": "lust", "how": "kava",
    "how much": "kava", "hungry": "kayfoundo", "hutt-size": "huttuk",
    "i": "jee", "i am": "dobra", "i want": "oto", "idiot": "koochoo",
    "imperial": "d'emperiolo", "in": "noleeya", "incredible": "inkabunga",
    "inferior": "con", "is": "sa", "it is": "soong", "it's": "soong",
    "jedi": "jeedai", "joke": "na yoka", "juices": "reeta", "keep": "jeeska",
    "kidnap": "jujiminmee", "kill": "killee", "large": "grancha", "late": "alay",
    "latest": "kagwa", "let's go": "boska", "look for": "stuta",
    "looks like": "stuka", "low-down": "doompa", "lucky": "gusha", "man": "nek",
    "maybe": "haba", "me": "je", "meal": "yafulkee", "message": "wankee",
    "methinks": "meendeeya", "mighty": "wonky", "money": "moulee-rah",
    "motel": "motal", "move": "yatuka", "movie": "holo", "my": "ma",
    "myself": "magoosa", "naptime": "hunka be", "neck": "punda",
    "never mind": "chut chut", "new": "newpa", "newest": "kagwa", "nice": "leah",
    "no": "nobata", "not": "nopa", "not bad": "nagoola", "now": "ateema",
    "nuisance": "hotshuh", "off": "ovv", "offer": "choba", "okay": "eniki",
    "one": "wompa", "opened": "watta", "or": "mo", "out": "nenoleeya",
    "outlander": "outmian", "outside": "cheesa", "paid": "moolee-rah",
    "pal": "punchee", "palace": "bunko", "parts": "pachee", "pay": "wamma",
    "payment": "mu-moolee", "payoff": "makacheesa", "percent": "luto",
    "pie": "patogga", "pit droid": "peet droid", "place": "pa",
    "planet": "planeeto", "podrace": "choppa chawa", "poop": "poodoo",
    "poor": "con", "power": "pawa", "price": "che copah", "program": "pogwa",
    "punk": "peedunkey", "queen": "kwee-kunee", "race": "hodrudda",
    "ransom": "gopptula", "real": "ree", "receipt": "chimpa",
    "republic": "publiko", "reigning": "granee", "sail barge": "see'ybark",
    "sand": "sando", "satisfactory": "foonta", "say": "settah",
    "scrapmetal": "junkie", "scum": "kung", "scurrier": "scuzzi",
    "search": "boska", "see": "stuka", "sell": "dwana",
    "shape-shifter": "shapa-keesay", "shipments": "spastika", "shoot": "keepuna",
    "shoulder": "bongo", "sixth": "steeth", "slave": "shag", "sleep": "winkee",
    "slime-ball": "sleemo", "slimeball": "sleemo", "slowly": "slagwa",
    "smile": "smeeleeya", "smoking": "puffee", "smuggler": "ulwan",
    "snack": "smak tellia", "somewhere": "tchuta", "space": "doma toma",
    "spaceport": "panksta", "spaceship": "pankpa", "spicy": "hotsa",
    "starting line": "tula moosta", "steal": "moocha", "strained": "binggona",
    "style": "stell", "suction cups": "sookee koopa", "surprising": "inkabunga",
    "systems consultant": "poolyee yama", "tart": "pagona", "tentacles": "tonta",
    "that": "da", "that one": "da wanga", "the": "ta", "them": "hoohah",
    "there": "la", "think": "tinka", "throat": "hoopa", "tie": "tee",
    "time": "tee-tocky", "tips": "spits", "to": "tah", "together": "weeteebah",
    "too": "peetch", "turn": "moova", "two-faced": "dopa-maskey",
    "underground": "unubunko", "up": "tonka", "upgrade": "hataw",
    "vault": "locktulla", "vegetarian cuisine": "kimbabaloomba", "very": "ree",
    "vice-president": "nupee nupee", "visit": "kyotopa", "waking planet": "da soocha",
    "want": "naga", "war": "nudcha", "warranty": "wontahumpa", "we": "jee-jee",
    "weak-minded": "maya", "weapon": "punyoo", "welcome": "chowbaso",
    "what": "haku", "when": "joppay", "where": "konchee", "which is": "coo sa",
    "who": "coo", "who is": "coo sa", "why haven't": "wanta", "wine": "gokola",
    "wish": "waba", "with": "gee", "woman": "cheeka", "wookiee": "wooky",
    "worm": "wermo", "would like": "vopa", "yeah": "eh", "yes": "tagwa",
    "you": "uba", "your": "do",
}

# The guide's own non-canon additions (its author filled gaps in the canon list).
# Delete this block and the update() below to stay strictly canon.
NON_CANON: dict[str, str] = {
    "about": "chaychay", "afraid": "theechu", "always": "kuteela",
    "bite": "chompa", "black": "yana", "blue": "ankwas", "cloud": "fooyu",
    "coward": "wakamancha", "disgusting": "huchaspu", "drug": "payokee",
    "ear": "neenree", "eat": "lacka", "eye": "nawee", "flower": "pukaneekee",
    "food": "goonu", "fruit": "freeta", "girl": "emeela", "green": "kwomur",
    "grey": "kwosnyee", "head": "ooma", "leaf": "chaala", "meat": "charkee",
    "morning": "manta", "mouth": "bocha", "never": "neeja", "north": "nauroo",
    "nose": "snoota", "orange": "weelapee", "over": "heeru", "purple": "muraroo",
    "rain": "paraploo", "read": "naweenchay", "red": "pukaa", "run": "faaway",
    "sad": "lakeela", "scratch": "haspee", "sing": "seenga", "sky": "tuukra",
    "snow": "reesnee", "song": "songu", "sour": "kalku", "south": "barathoo",
    "stand": "santay", "sweet": "meeshku", "tractor beam": "traskyoo",
    "under": "keeru", "walk": "kachay", "water": "wateela", "white": "yurak",
    "yellow": "kwelloo",
}

LEXICON: dict[str, str] = {**CANON, **NON_CANON}

# ── Density tiers ────────────────────────────────────────────────────────────
# Translating every word, articles and all, produces something nobody can read.
# On screen, Hutts mostly speak Basic and drop in the colourful words — so the
# lexicon is split into tiers and only the flavourful end is used by default.

# Structural words. Swapping these is what turns a sentence to mush, so they
# stay in Basic unless density="full".
GRAMMAR = {
    "a", "and", "another", "any", "anybody", "around", "away", "back", "every",
    "everybody", "for", "from", "he is", "her", "here", "here is", "how",
    "how much", "i", "i am", "in", "is", "it is", "it's", "kind", "maybe", "me",
    "my", "myself", "no", "not", "now", "off", "or", "out", "outside", "over",
    "place", "real", "somewhere", "that", "that one", "the", "them", "there",
    "to", "together", "too", "type", "under", "up", "very", "we", "what",
    "when", "where", "which is", "who", "who is", "why haven't", "with", "you",
    "your", "always", "about", "never",
}

# The words worth hearing in Huttese — greetings, insults, money, ships, and
# the handful of nouns everyone recognises from the films.
ICONIC = {
    "hello", "greetings", "good-bye", "goodbye", "welcome", "excuse me",
    "never mind", "yes", "okay", "let's go", "don't", "do not", "dammit",
    "friend", "pal", "fool", "idiot", "punk", "worm", "scum", "slime-ball",
    "slimeball", "coward", "boss", "bounty hunter", "smuggler", "slave",
    "foreigner", "outlander", "woman", "girl", "boy", "man", "wookiee", "jedi",
    "queen", "guards", "champion", "rookie", "money", "payment", "payoff",
    "price", "credit", "credit card", "bargain", "deal", "contract", "ransom",
    "business", "droid", "droids", "spaceship", "cruiser", "spaceport",
    "planet", "space", "palace", "home", "sail barge", "podrace", "race",
    "challenge", "competition", "weapon", "blaster", "gun", "kill", "die",
    "shoot", "steal", "cheat", "kidnap", "curse", "hex", "poop", "fodder",
    "drink", "wine", "meal", "snack", "dessert", "cake", "pie", "food",
    "big", "mighty", "great", "incredible", "amazing", "crazy", "bad",
    "not bad", "dangerous", "hazardous", "disgusting", "lucky", "hungry",
    "fast", "faster", "slowly", "time", "war", "holonet", "sleep", "naptime",
    "smile", "joke", "message", "brain damage", "two-faced", "double-crossing",
    "low-down", "weak-minded", "hutt-size", "glorious",
}

DENSITY_LEVELS = ("light", "medium", "full")
DEFAULT_DENSITY = "medium"


def _translatable(key: str, density: str) -> bool:
    if density == "full":
        return True
    if density == "light":
        return key in ICONIC
    return key not in GRAMMAR          # "medium"


# Per the guide, these have no Huttese equivalent at all — dropping them is
# more authentic than translating them.
NO_EQUIVALENT = {"please", "thank you", "thanks"}

# Flavour the model may use freely; all are attested in the guide.
FLAVOUR = ["Achuta", "Ho ho ho", "Bargon", "Boska", "Chut chut", "E chu ta",
           "Koochoo", "Nagoola", "Poodoo", "Sleemo", "Wermo"]

MAX_PHRASE = max(len(k.split()) for k in LEXICON)


@dataclass
class TranslationStats:
    matched: int = 0
    total: int = 0
    used: list[str] = field(default_factory=list)      # "friend -> pateesa"

    @property
    def coverage(self) -> float:
        return (self.matched / self.total * 100) if self.total else 0.0


def _match_case(source: str, replacement: str) -> str:
    if source.isupper() and len(source) > 1:
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _lookup(phrase: str, density: str = "full") -> Optional[str]:
    """Exact match, then a few cheap English inflections, honouring density."""
    key = phrase.lower()
    if key in LEXICON:
        return LEXICON[key] if _translatable(key, density) else None
    if " " in key:
        return None
    for suffix, stem in (("s", ""), ("es", ""), ("ed", ""), ("ing", ""),
                         ("ies", "y"), ("ied", "y")):
        if key.endswith(suffix) and len(key) > len(suffix) + 1:
            for cand in (candidate := key[: -len(suffix)] + stem,
                         candidate + "e" if suffix in ("ed", "ing") else None,
                         candidate[:-1] if suffix in ("ed", "ing") and len(candidate) > 2
                         and candidate[-1] == candidate[-2] else None):
                if cand and cand in LEXICON:
                    return LEXICON[cand] if _translatable(cand, density) else None
    return None


_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’-]*|\d+|\s+|[^\sA-Za-z\d]+")


def translate(text: str, density: str = DEFAULT_DENSITY) -> tuple[str, TranslationStats]:
    """Substitute Basic words for Huttese ones.

    density="light"  only the iconic words (most readable)
    density="medium" everything except structural grammar words (default)
    density="full"   every word in the lexicon (authentic, near-unreadable)
    """
    if density not in DENSITY_LEVELS:
        density = DEFAULT_DENSITY
    tokens = _TOKEN.findall(text)
    words = [i for i, t in enumerate(tokens) if t[:1].isalpha()]
    stats = TranslationStats(total=len(words))

    out = list(tokens)
    consumed: set[int] = set()
    pos = 0
    while pos < len(words):
        i = words[pos]
        if i in consumed:
            pos += 1
            continue

        # try the longest phrase first: "bounty hunter" before "bounty"
        for span in range(min(MAX_PHRASE, len(words) - pos), 0, -1):
            idxs = words[pos:pos + span]
            if any(j in consumed for j in idxs):
                continue
            phrase = " ".join(tokens[j] for j in idxs)
            key = phrase.lower()

            if key in NO_EQUIVALENT:
                for j in idxs:
                    out[j] = ""
                    consumed.add(j)
                stats.matched += span
                stats.used.append(f"{phrase} -> (no Huttese equivalent)")
                pos += span
                break

            hit = _lookup(phrase, density)
            if hit:
                out[idxs[0]] = _match_case(tokens[idxs[0]], hit)
                for j in idxs[1:]:
                    out[j] = ""
                    consumed.add(j)
                consumed.add(idxs[0])
                stats.matched += span
                stats.used.append(f"{phrase.lower()} -> {hit}")
                pos += span
                break
        else:
            pos += 1

    result = _tidy("".join(out))
    letters = [c for c in text if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        result = result.upper()        # SHOUTED input stays shouted
    return result, stats


_ELLIPSIS = "\x00E\x00"


def _tidy(text: str) -> str:
    """Repair spacing and punctuation left behind by substitutions/removals."""
    text = text.replace("...", _ELLIPSIS).replace("…", _ELLIPSIS)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Tighten a space before punctuation only when a real word precedes it, so
    # standalone runs like "!!! ???" survive.
    text = re.sub(r"(?<=[A-Za-z\d]) +([,.!?;:])", r"\1", text)
    # A dropped word can strand its punctuation.
    text = re.sub(r"[,;:]+[ \t]*(?=[.!?])", "", text)        # ", !"  -> "!"
    text = re.sub(r"([.!?])[ \t]*[,;:]+", r"\1", text)        # "!,"   -> "!"
    text = re.sub(r"([,;:])[ \t]*\1+", r"\1", text)           # ",,"   -> ","
    # "inkabunga! ." -> "inkabunga!" (only when a real word precedes it, so a
    # standalone run like "!!! ???" is left alone)
    text = re.sub(r"(?<=[A-Za-z\d])([.!?]+)[ \t]+[.!?]+", r"\1", text)
    text = re.sub(r"^[ \t]*[,;:]+[ \t]*", "", text)           # leading ", "
    text = re.sub(r"(?<=[A-Za-z\d]) +(?=[,;:])", "", text)
    text = text.replace(_ELLIPSIS, "...")
    return text.strip(" \t")


# ── Persona entry point ──────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are Jabbabot, a Hutt crime lord who speaks Huttese. You are given a "
    "message that has already been translated word-for-word using an authentic "
    "Huttese dictionary.\n"
    "Your job is ONLY to make it read like natural Hutt speech:\n"
    "- Keep every Huttese word exactly as given. Do not change their spelling.\n"
    "- NEVER invent Huttese words. If a word is still in Basic (English) and you "
    "have no dictionary entry for it, leave it in Basic — Hutts mix the two "
    "constantly.\n"
    "- The message is DELIBERATELY a mix of Basic and Huttese, the way Hutts "
    "actually speak on screen. Do NOT translate any more of it into Huttese, and "
    "do not replace Basic words with Huttese ones yourself — that makes it "
    "unreadable. Keep roughly the mix you are given.\n"
    "- Huttese word order is loose and often reversed; you may reorder freely.\n"
    "- You may add flavour words from the supplied list, a booming 'Ho ho ho', "
    "or address the speaker as a wermo, sleemo or koochoo.\n"
    "- Reply with one or two short sentences. No translation, no notes, no "
    "explanation — just the Huttese."
)


async def huttese_answer(target, density: str = DEFAULT_DENSITY) -> Optional[str]:
    """Translate a Discord message into Huttese. Works with or without OpenAI.

    Change DEFAULT_DENSITY above to dial the whole persona up or down.
    """
    from gpt_people_bots import _message_text          # shared attachment handling

    text = await _message_text(target)
    if not text:
        return None

    literal, stats = translate(text, density)

    glossary = "\n".join(stats.used) or "(no dictionary matches)"
    user_prompt = (
        f"Original Basic:\n{text}\n\n"
        f"Dictionary substitution:\n{literal}\n\n"
        f"Words that were translated:\n{glossary}\n\n"
        f"Flavour words you may add: {', '.join(FLAVOUR)}\n\n"
        "Polish the substitution into Hutt speech, keeping the same Basic/Huttese mix."
    )

    try:
        resp = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user_prompt}],
            temperature=0.8,
            max_tokens=200,
        )
        polished = resp.choices[0].message.content.strip()
    except Exception:
        # OpenAI down or unconfigured — the dictionary pass is still a real answer.
        polished = literal

    return polished or literal