"""Can this learner solve this question yet?  Deterministic, read-only, no AI.

``assess(state, packs, item)`` compares the ideas (KCs) a question needs with the learner's *started* topics:
``topicals.started_chapters`` = chapters the learner started or completed, plus chapters where any idea has been
answered.  Topic numbering plays no part: a learner may know a later chapter and not an earlier one.

Result ``status``:

* ``solvable``    every needed topic is started.
* ``adapted``     some parts (or the whole question) need an unstarted topic, but something can still be attempted:
                  ``adapted_prompt`` names the sub-parts to answer now, and/or ``given`` supplies the facts of the
                  missing ideas (flashcards / teaching-card notes / reviewed support).  Givens are assistance: the
                  caller must treat the attempt as assisted, not as independent performance.
* ``skipped``     no part is answerable and no given rescues it (the caller logs the exclusion; nothing is deleted).
* ``unverified``  the item carries no usable KC tags (``needs_topic`` is true: the caller may ask the AI to identify them).

Givens come only from the missing ideas' own teaching material, never from the question's key; a line that would
repeat the question's key is dropped.
"""
from __future__ import annotations

import re

from . import topicals

STATUSES = ('solvable', 'adapted', 'skipped', 'unverified', 'topic_pending')


def _topic_label(packs, sub: str) -> str:
    return (packs.subtopics.get(sub) or {}).get('title') or sub


def _kc_label(packs, kc: str) -> str:
    return (packs.kcs.get(kc) or {}).get('title') or kc


def _labels(parts: list[str]) -> str:
    parts = [f'({p})' for p in parts]
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + ' and ' + parts[-1]


def _secrets(item: dict) -> list[str]:
    """Text of the question's key, used only to keep it out of any given line."""
    out: list[str] = []
    answer = item.get('answer')
    if isinstance(answer, dict):
        if isinstance(answer.get('value'), (int, float)) and not isinstance(answer['value'], bool):
            out += [f'{answer["value"]:g}', repr(answer['value'])]
        if isinstance(answer.get('expr'), str):
            out.append(answer['expr'])
    elif isinstance(answer, str) and len(answer) > 1:
        out.append(answer)
    for point in item.get('rubric') or []:
        if isinstance(point, dict) and isinstance(point.get('point'), str):
            out.append(point['point'])
    for point in item.get('scheme') or []:
        if isinstance(point, dict) and isinstance(point.get('point'), str) and 'whole_rubric' not in point:
            out.append(point['point'])
    if isinstance(item.get('review_answer'), str):
        out.append(item['review_answer'])
    return [s.strip().casefold() for s in out if isinstance(s, str) and len(s.strip()) >= 3]


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'^[\-\*•]\s*', '', str(text).strip())).strip()


def given_for(packs, kc: str) -> list[str]:
    """Concrete facts of one idea (a definition or equation), from teaching material only.  [] = nothing concrete."""
    try:
        pack = packs.pack_for_kc(kc) or {}
    except Exception:  # a damaged chapter pack gives nothing; never an error in a read-only check
        pack = {}
    title = _kc_label(packs, kc)
    lines: list[str] = []
    card = (pack.get('teach') or {}).get(kc)
    if not isinstance(card, dict) and getattr(packs, 'vault_root', None):
        try:
            from .lesson import cached_card_data
            card = cached_card_data(packs.vault_root, kc)
        except Exception:
            card = None
    if isinstance(card, dict) and isinstance(card.get('note'), str):
        lines += [_clean(x) for x in card['note'].splitlines() if _clean(x)]
    for flash in pack.get('flashcards') or []:
        if isinstance(flash, dict) and flash.get('kc') == kc and flash.get('front') and flash.get('back'):
            lines.append(f"{_clean(flash['front'])} {_clean(flash['back'])}")
    seen: list[str] = []
    for line in lines:
        if line and line not in seen:
            seen.append(line)
    return [f'Given ({title}): {line}' for line in seen[:3]]


def _scrub(lines: list[str], secrets: list[str]) -> list[str]:
    return [line for line in lines if not any(s in line.casefold() for s in secrets)]


def _graph_conflict(packs, keys: list[str], course: str | None) -> bool:
    """True when the recorded course graph cannot be trusted for these ideas (fail closed, never guess)."""
    visited: set[str] = set()
    active: set[str] = set()

    def visit(key: str) -> None:
        if key in active:
            raise ValueError('cyclic graph')
        if key in visited:
            return
        node = packs.kcs.get(key)
        if not isinstance(node, dict):
            raise ValueError('unknown idea')
        sub, prereqs = node.get('subtopic'), node.get('prereqs')
        if ((course and (node.get('spec') != course or packs.subtopics.get(sub, {}).get('spec') != course))
                or not isinstance(prereqs, list) or any(not isinstance(k, str) for k in prereqs)):
            raise ValueError('incomplete or conflicting graph')
        active.add(key)
        for prerequisite in prereqs:
            visit(prerequisite)
        active.remove(key)
        visited.add(key)

    try:
        for key in keys:
            visit(key)
    except (ValueError, TypeError, RecursionError):
        return True
    return False


def _prereq_subs(packs, keys: list[str]) -> set[str]:
    """Subtopics of every recorded prerequisite of these ideas, transitively."""
    out: set[str] = set()
    seen: set[str] = set()
    stack = [k for key in keys for k in (packs.kcs.get(key, {}).get('prereqs') or []) if isinstance(k, str)]
    while stack:
        key = stack.pop()
        if key in seen:
            continue
        seen.add(key)
        node = packs.kcs.get(key)
        if not isinstance(node, dict):
            continue
        if isinstance(node.get('subtopic'), str):
            out.add(node['subtopic'])
        stack += [k for k in (node.get('prereqs') or []) if isinstance(k, str)]
    return out


def _result(status: str, message: str, **extra) -> dict:
    out = {'status': status, 'message': message, 'missing': [], 'given': [], 'adapted_prompt': None, 'topic': None,
           'skipped': status == 'skipped', 'missing_topics': [], 'parts': [], 'needs_topic': False,
           'assisted': False, 'topic_source': None}
    out.update(extra)
    out['skipped'] = out['status'] == 'skipped'
    return out


def assess(state: dict, packs, item: dict, *, kcs: list[str] | None = None, serving_chapter: str | None = None,
           unassisted: bool = False, topic_source: str = 'tags') -> dict:
    """``item``: any question dict (pack item, reviewed topical, source-verified instance) with optional ``kcs``,
    ``parts`` ([{label, kcs}]) and reviewed ``topical`` metadata.  ``kcs`` overrides the item's own tags (the
    AI-identified ones).  Pure: reads state and packs, writes nothing."""
    started = topicals.started_chapters(state, packs)
    meta = item.get('topical') if isinstance(item.get('topical'), dict) and item['topical'].get('reviewed') is True else None
    reviewed = {c for c in ((meta or {}).get('requires') or []) if isinstance(c, str) and c in packs.subtopics}
    support = (meta or {}).get('support') if isinstance((meta or {}).get('support'), dict) else {}
    own = [k for k in (kcs if kcs is not None else item.get('kcs') or []) if isinstance(k, str)]
    tagged = list(dict.fromkeys(k for k in own if k in packs.kcs))
    raw_parts = [p for p in item.get('parts') or [] if isinstance(p, dict) and isinstance(p.get('label'), str)]
    parts = [{'label': p['label'], 'kcs': list(dict.fromkeys(k for k in p.get('kcs') or [] if isinstance(k, str) and k in packs.kcs))}
             for p in raw_parts]
    mapped = [p for p in parts if p['kcs']]
    if kcs is not None:  # AI-identified ideas describe the whole question, not its sub-parts
        parts, mapped = [], []
    if not tagged and not reviewed and not mapped:
        return _result('unverified', 'This question has no topic tags, so it cannot be checked yet.', needs_topic=True)
    if not tagged:
        tagged = list(dict.fromkeys(k for p in mapped for k in p['kcs']))
    course = packs.subtopics.get(serving_chapter, {}).get('spec') if isinstance(serving_chapter, str) else None
    if meta is None and _graph_conflict(packs, list(dict.fromkeys(tagged + [k for p in mapped for k in p['kcs']])), course):
        return _result('unverified', 'The course graph for this question is incomplete or conflicting, so it cannot be '
                                     'checked; it stays open.')
    topic = [_kc_label(packs, k) for k in tagged] or None
    exempt = {serving_chapter} if serving_chapter else set()  # the chapter being served now counts as started

    def missing_of(unit_kcs: list[str], extra: set[str]) -> tuple[list[str], list[str]]:
        subs = {packs.kcs[k]['subtopic'] for k in unit_kcs}
        absent_subs = sorted((subs | extra) - started - exempt)
        return [k for k in unit_kcs if packs.kcs[k]['subtopic'] in absent_subs], absent_subs

    secrets = _secrets(item)

    def rescue(miss_kcs: list[str], miss_subs: list[str]) -> list[str] | None:
        """Facts that stand in for the missing ideas, or None when any of them has no concrete fact."""
        if unassisted:
            return None
        lines: list[str] = []
        covered = set()
        for kc in miss_kcs:
            facts = _scrub(given_for(packs, kc), secrets)
            if not facts:
                return None
            lines += facts
            covered.add(packs.kcs[kc]['subtopic'])
        for sub in miss_subs:
            if sub in covered:
                continue
            fact = support.get(sub)
            if not (isinstance(fact, str) and fact.strip()):
                return None
            if _scrub([_clean(fact)], secrets) == []:  # a reviewed fact that equals this question's key is not a hint
                return None
            lines.append(f'Given ({_topic_label(packs, sub)}): {_clean(fact)}')
        return lines

    units: list[dict] = []
    if mapped:
        for p in parts:
            if not p['kcs']:
                units.append({'label': p['label'], 'state': 'unknown', 'kcs': [], 'missing_kcs': [], 'missing_subs': []})
                continue
            mk, ms = missing_of(p['kcs'], set() if meta else _prereq_subs(packs, p['kcs']))
            units.append({'label': p['label'], 'kcs': p['kcs'], 'missing_kcs': mk, 'missing_subs': ms,
                          'state': 'blocked' if ms else 'ok'})
    else:
        mk, ms = missing_of([] if meta else tagged, reviewed | (set() if meta else _prereq_subs(packs, tagged)))
        units.append({'label': None, 'kcs': [] if meta else tagged, 'missing_kcs': mk, 'missing_subs': ms,
                      'state': 'blocked' if ms else 'ok'})
    for u in units:
        if u['state'] == 'blocked':
            u['given'] = rescue(u['missing_kcs'], u['missing_subs'])
    requires = sorted({packs.kcs[k]['subtopic'] for u in units for k in u['kcs']} | reviewed
                      | {s for u in units for s in _prereq_subs(packs, u['kcs'])})
    base = {'topic': topic, 'topic_source': topic_source, 'requires': requires,
            'parts': [{'label': u['label'], 'state': ('given' if u['state'] == 'blocked' and u.get('given') else u['state']),
                       'kcs': u['kcs'], 'missing': [_topic_label(packs, s) for s in u['missing_subs']]} for u in units]}
    blocked = [u for u in units if u['state'] == 'blocked']
    if not blocked:
        return _result('solvable', 'You have started every topic this question needs.', **base)
    miss_subs = list(dict.fromkeys(s for u in blocked for s in u['missing_subs']))
    labels = [_topic_label(packs, s) for s in miss_subs]
    common = {**base, 'missing': labels, 'missing_topics': miss_subs}
    rescued = [u for u in blocked if u.get('given')]
    free = [u for u in units if u['state'] in ('ok', 'unknown')]
    if not free and not rescued:
        return _result('skipped', 'Skipped for now: this needs ' + ', '.join(labels) + ', which you have not started.', **common)
    given = list(dict.fromkeys(line for u in rescued for line in u['given']))
    if units[0]['label'] is None:  # the whole question, one block
        prompt = ('This question needs ' + ', '.join(labels) + ', which you have not started. Use the facts marked '
                  'Given; they stand in for that topic, so this attempt counts as assisted.')
    else:
        now = [u['label'] for u in units if u in free or u in rescued]
        later = [u for u in blocked if u not in rescued]
        prompt = f'Answer parts {_labels(now)} now'
        if later:
            prompt += '; ' + '; '.join(f"({u['label']}) needs {', '.join(_topic_label(packs, s) for s in u['missing_subs'])}"
                                       for u in later) + ', which you have not started, so leave ' + (
                'it' if len(later) == 1 else 'them') + ' for later'
        prompt += '.'
        if rescued:
            prompt += (f' For {_labels([u["label"] for u in rescued])}, use the facts marked Given in place of '
                       f'{", ".join(_topic_label(packs, s) for s in dict.fromkeys(s for u in rescued for s in u["missing_subs"]))}'
                       '; those parts count as assisted.')
    return _result('adapted', prompt, adapted_prompt=prompt, given=given, assisted=bool(given), **common)
