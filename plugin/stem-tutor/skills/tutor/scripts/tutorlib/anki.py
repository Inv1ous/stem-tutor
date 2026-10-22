"""Export pack flashcards for introduced KCs as an .apkg (Anki owns facts; its FSRS schedules them).

Obsidian uses $…$/$$…$$ but Anki's MathJax uses \\(…\\)/\\[…\\], so text is converted on export.
GUIDs are stable per pack and card id, so re-importing updates notes instead of duplicating them.
"""
from __future__ import annotations

import html
import re
import zlib

from . import deps

MODEL_ID = 1607392319
TEMPLATE_CSS = ".card{font-family:-apple-system,Helvetica,sans-serif;font-size:20px;text-align:left;line-height:1.45}" \
               ".src{color:#888;font-size:13px;margin-top:1em}"


def to_anki(md: str) -> str:
    s = html.escape(md, quote=False).replace("\\$", "\x00")  # Anki fields are HTML: "a<b" would open a tag
    s = re.sub(r"\$\$(.+?)\$\$", lambda m: "\\[" + m.group(1) + "\\]", s, flags=re.S)
    s = re.sub(r"\$(.+?)\$", lambda m: "\\(" + m.group(1) + "\\)", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s.replace("\n", "<br>").replace("\x00", "$")


def guid(card_id: str) -> str:
    deps.ensure("genanki")
    import genanki

    return genanki.guid_for("stem-tutor", card_id)


def _deck_id(name: str) -> int:
    return (1 << 30) + zlib.crc32(name.encode()) % (1 << 30)


def export(tutor) -> dict:
    deps.ensure("genanki")
    import genanki

    state, packs = tutor.state, tutor.packs
    done, sent = set(state.get("anki_exported", [])), state.get("anki_hashes", {})
    hashes: dict[str, str] = {}
    model = genanki.Model(
        MODEL_ID, "STEM Tutor card",
        fields=[{"name": "Front"}, {"name": "Back"}, {"name": "KC"}, {"name": "Source"}],
        templates=[{"name": "Card 1", "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}<hr id=answer>{{Back}}<div class=src>{{KC}} {{Source}}</div>"}],
        css=TEMPLATE_CSS,
    )
    decks: dict[str, genanki.Deck] = {}
    new_ids = []
    for subtopic in sorted({packs.kc(kc)["subtopic"] for kc, k in state["kcs"].items() if k["n"] > 0 and kc in packs.kcs}):
        pack = packs.pack(subtopic) or {}
        for card in pack.get("flashcards", []):
            kc, uid = card["kc"], f"{subtopic}:{card['id']}"  # packs reuse fc1, fc2…: the pack makes an id unique
            if state["kcs"].get(kc, {}).get("n", 0) == 0 or card.get("in_anki"):
                continue
            h = card_hash(card)
            if uid in done and sent.get(uid, h) == h:  # exported, and not corrected since (Q-019)
                if uid not in sent:
                    hashes[uid] = h  # exported before fingerprints were kept: this is what it says now
                continue
            hashes[uid] = h  # new, or corrected: sent again under the same GUID, so Anki updates the note it has
            meta = packs.kc(kc)
            topic = next((t for t in packs.subtopics.values() if t["id"] == subtopic), {})
            name = f"STEM Tutor::{meta['spec']}::{topic.get('title', subtopic)}"
            deck = decks.setdefault(name, genanki.Deck(_deck_id(name), name))
            deck.add_note(genanki.Note(model=model, guid=guid(uid),
                                       fields=[to_anki(card["front"]), to_anki(card["back"]), kc, card.get("source", "")],
                                       tags=["stem-tutor", meta["spec"], kc.replace(".", "_")]))
            new_ids.append(uid)
    if not new_ids:
        if hashes:  # no file to make, but the fingerprints of cards exported before are worth keeping
            tutor.log({"type": "anki_export", "cards": [], "path": None, "hashes": hashes})
        return {"cards": 0, "path": None}
    now = tutor.now()
    stem, k = f"Anki/STEM Tutor {now:%Y-%m-%d %H%M}", 1
    rel = f"{stem}.apkg"
    while (tutor.vault.root / rel).exists():  # a second batch this minute: the first may not be imported yet
        k += 1
        rel = f"{stem} ({k}).apkg"
    out = tutor.vault.root / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(list(decks.values())).write_to_file(str(out))
    tutor.log({"type": "anki_export", "cards": new_ids, "path": rel, "hashes": hashes})
    return {"cards": len(new_ids), "path": rel, "decks": sorted(decks),
            "updated": sum(1 for uid in new_ids if uid in done)}


def card_hash(card: dict) -> str:
    """What a card says (front, back, source), as a short fingerprint: a correction changes it."""
    import hashlib
    return hashlib.sha1("\x1f".join(str(card.get(k, "")) for k in ("front", "back", "source")).encode()).hexdigest()[:12]
