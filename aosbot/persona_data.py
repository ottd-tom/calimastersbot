"""
Static text for the persona / joke commands. Edit freely — nothing here has logic.
"""

# ── Maddy ────────────────────────────────────────────────────────────────────
maddy_phrases = [
    "I'm cold.",
    "I like black.",
    "I wear black clothes.",
    "I like soup.",
    "Soup doesn’t judge me.",
    "Black matches my soul.",
    "I don’t smile. It might crack my face.",
    "Steam from soup is my preferred warmth.",
    "I wear hoodies in summer. Don't ask.",
    "I collect spoons. Just in case.",
    "Black isn’t a color. It’s a lifestyle.",
    "I don’t tan. I seethe.",
    "Soup is the only hug I accept.",
    "I once felt joy. It was an error.",
    "I’m not brooding. This is my default.",
    "My spirit animal is soup.",
    "My closet is a void. I dress accordingly.",
    "I simmer like broth — quietly and with intent.",
    "I’ve made peace with the abyss.",
    "Tea is just soup with attitude.",
    "I speak fluent sigh.",
    "I’ve never been warm emotionally or physically.",
    "I microwave my emotions for 3 minutes on high.",
    "I wear black so people stop asking questions.",
    "Cold hands, colder heart.",
    "The soup understands me.",
    "I’m not short. I’m concentrated.",
    "I’m closer to the soup. Advantage: me.",
    "I don’t have to duck for anything. Ever.",
    "The air down here is just fine, thanks.",
    "I don’t look up to anyone. Literally.",
    "Low effort? No. Low height.",
    "I can hide behind terrain. Like, any terrain.",
    "My reach is emotional, not physical.",
    "Chairs are just unnecessarily tall tables.",
    "I would think you could relate to the joy of seeing the light drain from your opponent's eyes.",
    "As a child, I was not fortunate enough to have stuffed animals."
]

# ── Tom G (weighted) ─────────────────────────────────────────────────────────
SUN_TZU_AOS_STRAT = """
In Age of Sigmar, the principle Know yourself and know your enemy is as vital at the gaming table as it was on ancient battlefields. Before even rolling dice, a commander must understand the strengths and limitations of their chosen Host—whether the stoic resilience of the Stormcast Eternals, the untamed ferocity of the Kruleboyz, or the arcane versatility of the Idoneth Deepkin. Sun Tzu teaches that thorough preparation and self‐assessment secure victory: in Age of Sigmar terms, this means building a list that leverages synergies between units, abilities, and artifacts while anticipating the threats posed by common tournament archetypes. Likewise, scouting the opponent’s likely composition—and adapting your own to counter it—mirrors Sun Tzu’s emphasis on flexibility: be like water, fitting your deployment to the contours of the battlefield and the flow of the game. Victory arises not from brute force alone, but from the harmony of strategy, list construction, and foresight.

Just as All warfare is based on deception, so too can an Age of Sigmar general employ feints, hidden reserves, and misdirection to unnerve an opponent. Concealing your true intent—perhaps by deploying a fast‐strike unit in a flank zone that ultimately proves a diversion—forces your adversary to commit resources reactively, leaving their main force vulnerable. Sun Tzu’s counsel to appear weak when you are strong, and strong when you are weak finds its echo in judicious use of command abilities and terrain: bait an enemy into committing to a tempting objective, then spring your counterstrike with battalions held in reserve. Finally, the art of timing—knowing when to seize momentum with a decisive charge and when to consolidate objectives—reflects Sun Tzu’s insistence on seizing opportune moments and turning them to advantage. In Age of Sigmar, as in ancient war, victory belongs not merely to the strongest host, but to the most cunning and adaptable mind.
"""

# each entry is (phrase, weight)
tombot_phrase_weights = [
    ("More rats",                           1),
    ("lig",                                  3),
    ("neat",                                 3),
    ("nice",                                 3),
    ("L",                                    5),
    ("Holy",                                 5),
    ("Based",                                5),
    ("Whoa",                                 5),
    ("Where's the nearest Olive Garden?",    0.1),
    ("Miss home.  Where's nearest Panda Express?", 0.01),
    ("Gotta go raid",                        1),
    ("Toms are so smart",                    1),
    ("fish",                                 2),
    ("wow",                                  5),
    ("sad",                                  5),
    ("snap",                                 5),
    ("madge",                                3),
    ("I love junk",                          3),
    ("they call me the compliment machine",  1),
    ("A gentleman never rolls his opponents dice", 1),
    ("give them the business", 1),
    ("Man I love nuts",1),
    ("once in a while i type some of these cringe messages that i crigne while reading back",1),
    (SUN_TZU_AOS_STRAT, 0.000001)
]

# ── One-liners ───────────────────────────────────────────────────────────────
adam_phrases = [
    "I feel like one on one I outnumber most of the SoCal Warhammer scene"
]
aj_phrases = [
    "A magical chaos entitiy spewing vomit 49 feet seems realistic"
]
e_phrases = [
    "Ligmar has low intelligence, high loyalty.",
    "Welcome back Jews"
]
jo_phrases = [
    "(Not knowing context since I'm at work, so quick response) I love a good pp",
    "The best thing here. Turns out anal is a cure all",
    "I ain't got the time for pp unfortunately."
]
tomtom_phrases = [
    "Tom's so smart"
]
tomtomtom_phrases = [
    "Never met a Tom I like"
]

# ── Vallis (AoS Coach server channel/emoji mentions) ─────────────────────────
UNLOCK_CHANNEL      = "<#846210703949037598>"
TTS_PLAY_CHANNEL    = "<#866545623314595881>"
TTS_HELP_CHANNEL    = "<#703922401012088833>"

# Emoji mentions
EMOJI_GARGANT       = "<:Gargantstomp:799483473596383262>"
EMOJI_COOLCAST      = "<:CoolCast:695763331570597958>"
EMOJI_ROCKHORROR    = "<:RockHorror:695129181956210688>"
EMOJI_DABADMOON     = "<:DABADMOON:717233975910727711>"
EMOJI_PETRIFEX      = "<:LaughsInPetrifex:687778273434009601>"



vallis_responses = {

    "tts": (
        f"For TTS, there is a lot of helpful setup info pinned in {TTS_HELP_CHANNEL}.  "
        f"You can find people to play with in {TTS_PLAY_CHANNEL}\n"
        f"If you can't access those channels, go to {UNLOCK_CHANNEL} "
        f"and hit the {EMOJI_GARGANT} to enable the TTS channels"
    ),

    "order": (
        "People in this channel will help if they can, but you'll find more people "
        "familiar with your army in the faction's specific channel.\n\n"
        f"If you can't access that channel, go to {UNLOCK_CHANNEL} "
        f"and hit the {EMOJI_COOLCAST} emote to get access to ORDER channels."
    ),

    "chaos": (
        "People in this channel will help if they can, but you'll find more people "
        "familiar with your army in the faction's specific channel.\n\n"
        f"If you can't access that channel, go to {UNLOCK_CHANNEL} "
        f"and hit the {EMOJI_ROCKHORROR} emote to get access to CHAOS channels."
    ),

    "destruction": (
        "People in this channel will help if they can, but you'll find more people "
        "familiar with your army in the faction's specific channel.\n\n"
        f"If you can't access that channel, go to {UNLOCK_CHANNEL} "
        f"and hit the {EMOJI_DABADMOON} emote to get access to DESTRUCTION channels."
    ),

    "death": (
        "People in this channel will help if they can, but you'll find more people "
        "familiar with your army in the faction's specific channel.\n\n"
        f"If you can't access that channel, go to {UNLOCK_CHANNEL} "
        f"and hit the {EMOJI_PETRIFEX} emote to get access to DEATH channels."
    ),

    "nosense": "It's a horrible way to write the rule.",

    "chainfight": (
        "There are actually a few questions about chain fighting a strike-first. "
        "There's the classic \"can I pull my non-strike-first unit into the strike-first phase?\" "
        "and the \"If I'm the active player and my strike-first unit chain fights, can I get three activations in a row?\"\n\n"
        "Here's the first one:\n"
        "Chain fighting abilities let you change the timing of when another fight-eligible unit can fight, "
        "but it cannot override strike-first or strike-last. If the unit that uses the chain fighting ability has strike-first, "
        "a non-strike-first unit can chain fight only if neither player has any more strike-first units. Likewise, a strike-last unit "
        "can chain fight only if only strike-last units are left to fight on either side.\n\n"
        "Here's the second:\n"
        "If you're the active player and you have a strike-first unit with a chain fighting ability, "
        "you can make a non-strike-first unit fight immediately after your strike-first unit, as long as no player has any other "
        "strike-first units. Afterwards, you get to activate again with your first regularly timed fight, since the alternating "
        "fighting resets to the active player after the strike-first units are done. So you can wind up with three activations in a row."
    ),

    "fighttwice": (
        "Fight twice abilities typically give the unit strike-last for their second fight. "
        "If the unit has strike-first at the same time, which usually lasts for the rest of the turn, "
        "the unit will get strike-first for the first fight. "
        "For the second fight, strike-first is cancelled out by strike-last, so the unit will fight with normal timing."
    ),

    "powerthrough": (
        "Like all enemy abilities, Power Through can affect your opponent's manifestations and faction terrain, "
        "but the ability requires both that the unit using the command has a greater health characteristic than "
        "the target and that the target is in combat with your unit.  "
        "In the End of Turn phase, manifestations and faction terrain with a move characteristic above 0 count for being in combat, "
        "but those with a move of 0 don't.  So you can only use Power Through on mobile manifestations and faction terrain."
    ),

    "strikelastpilein": (
        "If a unit with strike-last piles-in to a unit without strike-last that wasn't in combat before, "
        "the strike-last unit will finish its FIGHT ability, and then the other unit gets to fight.  "
        "It fights before any other strike-last units can be picked to fight.\n"
        "Remember, 4th edition does not have sub-phases of the combat phase.  "
        "Strike-first and strike-last just apply restrictions on when units can be picked to fight."
    ),

    "glossary":(
        "The AoS 4th edition rules include a glossary, and the game is quite a bit poorer for it. "
        "Glossary entries aren't rules; they're just there to confuse and bewilder. "
        "They are misleading or flat out wrong at least half the time.  "
        "It should be called The Quick Reference Guide to Playing Age of Sigmar Wrong. \n\n"
        "And if you search the official AoS app for a rule, be careful that it's not from the glossary, "
        "unless you are interested in how the rule probably doesn't actually work. "
        "Glossary entries come up more often than not, just to mess with players that don't read the actual rules."
    ),
}

# ── GHB missions (/thommoisinadequate) ───────────────────────────────────────
GHB_MISSIONS = [
    "Into the Fire",
    "Bloodstained Coasts",
    "Avalanch of Ash",
    "Caverns of Slaughter",
    "What's Yours is Ours",
    "Warped Ruins",
    "Curse of the Gnaw",
    "Sieze the Embers",
    "Treacherous Ground",
    "Escape from the Coast",
    "Power of the Realms",
]
