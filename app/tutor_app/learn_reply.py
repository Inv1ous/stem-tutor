"""Validate structured learning replies before any part is displayed.

This verifies a narrow class of explicit equalities, not the truth of a proof
or natural-language explanation. Unsupported calculations must be withheld.
"""
from __future__ import annotations

import ast
from fractions import Fraction
import json
import re
import unicodedata

from tutorlib.teach_actions import SCHEMA as TEACH_ACTIONS_SCHEMA

from .learn_math import check_equality

LEARN_REPLY_SCHEMA = {
    "type": "object", "properties": {"blocks": {"type": "array", "items": {
        "type": "object", "properties": {"kind": {"type": "string", "enum": ["text", "equality"]},
        "text": {"type": "string"}, "left": {"type": "string"}, "right": {"type": "string"}},
        "required": ["kind", "text", "left", "right"]}}}, "required": ["blocks"]}

# Either the older list of section IDs or, preferred, teaching actions (tutorlib/teach_actions.py): the program checks
# and draws whatever is asked for; the model never supplies text to show.
CARD_SELECTION_SCHEMA = {"type": "object", "properties": {
    "sections": {"type": "array", "items": {"type": "string"}}, "actions": TEACH_ACTIONS_SCHEMA["properties"]["actions"]}}

_NUMERIC_WORD = re.compile(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                           r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
                           r"fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
                           r"dozen|score|half|quarter|twice|thrice|times|product|sum|difference|"
                           r"plus|minus|equals|multiplied|divided)\b", re.I)
_MATH_CHARS = re.compile(r"[0-9$=+*/^\\<>≤≥≠≈∑∫√²³₀-₉×÷−±∞∈∉]")
_SYMBOLIC_MINUS = re.compile(r"(?<!\w)[A-Za-z]\s*-\s*[A-Za-z](?!\w)")


def relevant_form_suggestion(question: str, card: dict) -> int | None:
    """Suggest a uniquely close title; never infer or render a worked answer."""
    stop = {'using', 'prove', 'proof', 'show', 'find', 'what', 'with', 'that', 'this',
            'from', 'your', 'their', 'have', 'does', 'doesnt', 'which', 'about', 'example'}
    def words(text):
        return {word for word in re.findall(r'[a-z]{4,}', text.casefold()) if word not in stop}
    if not isinstance(question, str) or not isinstance(card, dict):
        return None
    # Negation of the learner's understanding is not negation of the claim.
    # Its scope is ambiguous here, so let the normal tutor selection handle it.
    if re.search(r"\b(?:(?:don['’]t|do not|can['’]t|cannot|can not)\s+"
                 r"(?:understand|know|see)|not\s+sure)\b", question, re.I):
        return None
    query = words(question)
    negated = bool(re.search(r"\b(?:no|not|never|without)\b|n['’]t\b", question, re.I))
    matches = []
    for i, form in enumerate(card.get('forms') or []):
        if not isinstance(form, dict) or not isinstance(form.get('name'), str):
            continue
        if bool(re.search(r'\b(?:no|not|never|without)\b', form['name'], re.I)) != negated:
            continue
        title = words(form['name'])
        overlap = len(query & title)
        if overlap >= 4 and overlap / max(1, len(title)) >= .7:
            matches.append((overlap, i))
    matches.sort(reverse=True)
    return matches[0][1] if matches and (len(matches) == 1 or matches[0][0] > matches[1][0]) else None


def explicit_misconception(question: str, card: dict) -> str | None:
    """Match an explicit assertion to an exact card misconception, not a question about it."""
    match = re.fullmatch(r'\s*i (?:think|believe) (.+?)\s*[.!]*\s*', question, re.I)
    if not match:
        return None
    def normalise(value):
        return ' '.join(unicodedata.normalize('NFKC', value).casefold().rstrip('.! ').split())
    statement = normalise(match.group(1))
    hits = [m.get('id') for m in card.get('misconceptions', [])
            if isinstance(m, dict) and isinstance(m.get('idea'), str) and normalise(m['idea']) == statement
            and isinstance(m.get('id'), str) and m['id']]
    return hits[0] if len(hits) == 1 else None


def try_first(question: str, kc: str, card: dict, session: dict, state: dict) -> str | None:
    """Offer a card question for a broad first request when the probe supports it."""
    probe = (session.get('probe') or {}).get(kc) or {}
    text = card.get('self_explain')
    if (not isinstance(text, str) or not text.strip() or not probe.get('ok')
            or (probe.get('conf') or 0) < 3 or kc in state.get('gaps', [])
            or session.get('goal') == 'scratch'
            or (state.get('kcs', {}).get(kc, {}).get('active_misconceptions') or [])
            or (session.get('learn_history') or {}).get(kc)):
        return None
    if not re.fullmatch(r'\s*(?:how (?:should|do) i (?:approach|start)(?: (?:this|the idea|a proof))?|'
                        r'where (?:should|do) i start)\s*[?.!]*\s*', question, re.I):
        return None
    return text.strip()


def card_selection_options(card: object) -> dict[str, str]:
    """Make a model-facing catalogue without examples, checks or their answers."""
    if not isinstance(card, dict):
        return {}
    options = {key: card[key] for key in ("plain_words", "establish", "connect", "self_explain")
               if isinstance(card.get(key), str) and card[key].strip()}
    for key, prefix, fields in (("terms", "term", ("term", "meaning")),
                                 ("misconceptions", "misconception", ("idea", "fix"))):
        entries = card.get(key)
        if not isinstance(entries, list):
            continue
        for i, entry in enumerate(entries[:1000]):
            if isinstance(entry, dict) and all(isinstance(entry.get(f), str) and entry[f].strip() for f in fields):
                options[f"{prefix}:{i}"] = ": ".join(entry[f] for f in fields)
    return options


def related_card_options(cards: object) -> dict[str, str]:
    """Catalogue only explicitly supplied cards, with unambiguous card-qualified IDs."""
    if not isinstance(cards, dict):
        return {}
    return {f"{kc}|{section}": content
            for kc, card in cards.items() if isinstance(kc, str) and kc and "|" not in kc
            for section, content in card_selection_options(card).items()}


def exact_term_selection(question: str, current: str, cards: dict) -> dict | None:
    """Resolve a direct definition request only when the named term is unambiguous."""
    match = re.fullmatch(r'\s*(?:what (?:does (.+?) mean|is (.+?))|define (.+?))\s*[?.!]*\s*',
                         question, re.I)
    if not match:
        return None
    def normalise(text):
        return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())
    requested = next(x for x in match.groups() if x is not None).strip()
    name = normalise(requested)
    def find(term_name):
        return [f'{kc}|term:{i}' for kc, card in cards.items()
                if isinstance(card, dict) and isinstance(card.get('terms'), list)
                for i, term in enumerate(card['terms'])
                if isinstance(term, dict) and isinstance(term.get('term'), str)
                and normalise(term['term']) == term_name]
    hits = find(name)
    if not hits and name.startswith('the '):
        hits = find(name[4:])
    if not hits:
        # Symbols are case-sensitive: normalising ℤ to Z or s to S can
        # change their meaning. Only match a complete notation, not a fragment.
        symbol = unicodedata.normalize('NFC', requested.strip('$').strip())
        hits = [f'{kc}|term:{i}' for kc, card in cards.items()
                if isinstance(card, dict) and isinstance(card.get('terms'), list)
                for i, term in enumerate(card['terms'])
                if isinstance(term, dict) and isinstance(term.get('notation'), str)
                and term['notation'].strip().casefold() != 'none'
                and unicodedata.normalize('NFC', term['notation'].strip().strip('$').strip()) == symbol]
    local = [hit for hit in hits if hit.startswith(current + '|')]
    chosen = local if local else hits
    return {'sections': chosen} if len(chosen) == 1 else None


def active_misconception_selection(question: str, current: str, cards: dict, state: dict, *,
                                   prerequisites: tuple[str, ...] | list[str] = ()) -> dict | None:
    """Select recorded misconceptions for the requested idea or its prerequisites."""
    earlier = re.fullmatch(r'\s*what earlier misconceptions should i review\s*[?.!]*\s*', question, re.I)
    if not earlier and not re.fullmatch(r'\s*(?:what have i misunderstood|what misconceptions (?:do i have|should i review))\s*[?.!]*\s*',
                                        question, re.I):
        return None
    selected = []
    for kc in dict.fromkeys(prerequisites if earlier else [current]):
        active = (state.get('kcs', {}).get(kc, {}) or {}).get('active_misconceptions') or []
        entries = (cards.get(kc) or {}).get('misconceptions') or []
        for ident in dict.fromkeys(active):
            hits = [i for i, entry in enumerate(entries) if isinstance(entry, dict) and entry.get('id') == ident
                    and all(isinstance(entry.get(k), str) and entry[k].strip() for k in ('idea', 'temptation', 'fix'))]
            if len(hits) == 1:
                selected.append(f'{kc}|misconception:{hits[0]}')
    return {'sections': selected[:6]}


def published_related_cards(tutor, kc: str, limit: int = 8) -> dict[str, dict]:
    """Read current, prerequisite and same-subtopic cards directly from packs.

    Publication is a provenance boundary, not proof that content is correct or
    safe to show before a future question. Never use an AI cache or fallback.
    """
    graph = tutor.packs.kcs
    point = graph.get(kc)
    if not isinstance(point, dict) or limit < 1:
        return {}
    candidates = [kc, *(point.get('prereqs') or []),
                  *(key for key, value in graph.items() if value.get('subtopic') == point.get('subtopic'))]
    result = {}
    for key in dict.fromkeys(candidates):
        if key not in graph:
            continue
        pack = tutor.packs.pack_for_kc(key) or {}
        card = (pack.get('teach') or {}).get(key)
        if isinstance(card, dict) and card.get('source') != 'ai':
            result[key] = card
        if len(result) >= limit:
            break
    return result


def selection_prompt(question: str, cards: dict, history: str = "", exchanges: str = "", *,
                     recent_questions: str = "") -> str:
    """Ask for references only; the model cannot supply text to the renderer."""
    return ("Choose relevant section IDs only if the supplied material directly addresses the learner's "
            "question. Select at most six section IDs. If it does not, return an empty sections array. Return only the JSON selection. "
            "Give a short explanation first: select only the most relevant material needed to answer the question. "
            "Include more detail when the student asks for it; avoid repetitive or unrelated sections. "
            "When the learner is confident and has no gap, consider the self_explain question to invite an attempt; "
            "when the learner is new or has a gap, choose an explanation. "
            "Never include explanations or an answer to an unattempted question.\n\n"
            + "Teaching material:\n" + json.dumps(related_card_options(cards), ensure_ascii=False)
            + "\n\nRecent learning context:\n" + history[:4000]
            + "\n\nRecent question context:\n" + recent_questions[-3000:]
            + "\n\nRecent conversation:\n" + exchanges[-4000:]
            + "\n\nLearner question:\n" + question[:2000])


def render_related_selection(data: object, cards: object) -> tuple[str, str | None]:
    invalid = ("", "The tutor could not select a supported explanation.")
    if not isinstance(data, dict) or set(data) != {"sections"} or not isinstance(cards, dict):
        return invalid
    sections = data["sections"]
    if sections == []:
        return "", "No matching explanation was found in these teaching cards."
    if (not isinstance(sections, list) or not 1 <= len(sections) <= 6
            or any(not isinstance(s, str) for s in sections) or len(set(sections)) != len(sections)):
        return invalid
    rendered = []
    for section in sections:
        kc, sep, ref = section.partition("|")
        if not sep or kc not in cards:
            return invalid
        text, problem = render_card_selection({"sections": [ref]}, cards[kc])
        if problem:
            return invalid
        rendered.append(text)
    return "\n\n".join(rendered), None


def render_card_selection(data: object, card: object) -> tuple[str, str | None]:
    """Render only named card content; never display model-supplied prose or answer keys.

    This does not establish that the card itself is correct or that the selected
    material answers the learner's question. It is an experimental building block.
    """
    invalid = ("", "The tutor could not select a supported explanation.")
    if not isinstance(data, dict) or set(data) != {"sections"} or not isinstance(card, dict):
        return invalid
    sections = data["sections"]
    if sections == []:
        return "", "No matching explanation was found in this teaching card."
    if (not isinstance(sections, list) or not 1 <= len(sections) <= 6
            or any(not isinstance(s, str) for s in sections) or len(set(sections)) != len(sections)):
        return invalid
    out = []
    for section in sections:
        if section in ("plain_words", "establish", "connect", "self_explain"):
            value = card.get(section)
            if not isinstance(value, str) or not value.strip():
                return invalid
            out.append(value.strip())
            continue
        match = re.fullmatch(r"(term|misconception):(0|[1-9][0-9]*)", section)
        if not match or len(match.group(2)) > 3:
            return invalid
        kind, index = match.group(1), int(match.group(2))
        entries = card.get("terms" if kind == "term" else "misconceptions")
        if not isinstance(entries, list) or index >= len(entries) or not isinstance(entries[index], dict):
            return invalid
        entry = entries[index]
        fields = ("term", "meaning", "notation", "spoken") if kind == "term" else ("idea", "temptation", "fix")
        if any(not isinstance(entry.get(f), str) or not entry[f].strip() for f in fields):
            return invalid
        if kind == "term":
            notation = entry['notation'].strip()
            line = f"**{entry['term']}**: {entry['meaning']}"
            if notation.lower() != 'none':
                line += f"\nNotation: {notation}."
            line += f" Read: {entry['spoken']}."
            out.append(line)
        else:
            out.append(f"**Common misconception:** {entry['idea']}\n\nWhy it is tempting: {entry['temptation']}\n\nFix: {entry['fix']}")
    return "\n\n".join(out), None


def _math_tex(expr: str) -> str:
    """Render the already-verified arithmetic AST without changing its grouping."""
    def group(text: str) -> str:
        return r"\left(" + text + r"\right)"

    def precedence(node: ast.AST) -> int:
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, (ast.Add, ast.Sub)):
                return 1
            if isinstance(node.op, (ast.Mult, ast.Div)):
                return 2
            return 4
        return 3 if isinstance(node, ast.UnaryOp) else 5

    def render(node: ast.AST) -> str:
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Name):
            return node.id if len(node.id) == 1 else r"\mathrm{" + node.id + "}"
        if isinstance(node, ast.UnaryOp):
            sign = "-" if isinstance(node.op, ast.USub) else "+"
            value = render(node.operand)
            return sign + (group(value) if precedence(node.operand) < 3 else value)
        if isinstance(node, ast.BinOp):
            left, right = render(node.left), render(node.right)
            if isinstance(node.op, ast.Div):
                return r"\frac{" + left + "}{" + right + "}"
            if isinstance(node.op, ast.Pow):
                base = group(left) if precedence(node.left) <= 4 else left
                return base + "^{" + right + "}"
            symbol = {ast.Add: "+", ast.Sub: "-", ast.Mult: r"\cdot "}[type(node.op)]
            level = precedence(node)
            if precedence(node.left) < level:
                left = group(left)
            if precedence(node.right) <= level:
                right = group(right)
            return left + symbol + right
        raise ValueError("unsupported verified expression")
    return render(ast.parse(expr, mode="eval").body)


def checked_identity_request(question: str) -> str | None:
    """Check a specifically requested polynomial identity, not an equation to solve."""
    if not isinstance(question, str) or len(question) > 270:
        return None
    match = re.fullmatch(r'\s*check identity\s*:\s*(.+?)\s*=\s*(.+?)\s*\??\s*', question, re.I)
    if not match:
        return None
    left, right = (part.strip().strip('$').strip().replace('^', '**') for part in match.groups())
    result = check_equality(left, right)
    if result is None:
        return None
    try:
        expression = f'${_math_tex(left)} = {_math_tex(right)}$'
    except (SyntaxError, ValueError, KeyError, TypeError):
        return None
    verdict = 'This is an identity for all real values of its variables.' if result else (
        'This is not an identity for all real values of its variables; it may hold for particular values.')
    return f'{expression}\n\n{verdict}'


def checked_arithmetic_request(question: str) -> str | None:
    """Answer an explicit, bounded exact-arithmetic request after a SymPy check."""
    if not isinstance(question, str) or len(question) > 150:
        return None
    match = re.fullmatch(r'\s*calculate\s+(.+?)\s*[?]?\s*', question, re.I)
    if not match:
        return None
    expression = match.group(1).strip().strip('$').strip().replace('^', '**')
    if not expression or len(expression) > 128:
        return None
    try:
        tree = ast.parse(expression, mode='eval')
        if len(list(ast.walk(tree))) > 40:
            return None
        def calculate(node):
            if isinstance(node, ast.Expression):
                return calculate(node.body)
            if isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) <= 10000:
                return Fraction(node.value)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = calculate(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if not isinstance(node, ast.BinOp):
                raise ValueError('unsupported expression')
            left, right = calculate(node.left), calculate(node.right)
            if isinstance(node.op, ast.Add): value = left + right
            elif isinstance(node.op, ast.Sub): value = left - right
            elif isinstance(node.op, ast.Mult): value = left * right
            elif isinstance(node.op, ast.Div): value = left / right
            elif isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant) and type(node.right.value) is int and 0 <= node.right.value <= 8:
                value = left ** node.right.value
            else: raise ValueError('unsupported operation')
            if value.numerator.bit_length() > 512 or value.denominator.bit_length() > 512:
                raise ValueError('result too large')
            return value
        result = calculate(tree)
        answer = str(result.numerator) if result.denominator == 1 else f'{result.numerator}/{result.denominator}'
        if check_equality(expression, answer) is not True:
            return None
        return f'${_math_tex(expression)} = {_math_tex(answer)}$'
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
        return None


def render_reply(data: object) -> tuple[str, str | None]:
    """Return a checked reply or a reason to withhold it; never return partial text on failure."""
    blocks = data.get("blocks") if isinstance(data, dict) else None
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 20:
        return "", "The tutor returned an invalid response."
    out = []
    for block in blocks:
        if not isinstance(block, dict):
            return "", "The tutor returned an invalid response."
        kind = block.get("kind")
        if kind == "text":
            text = block.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > 3000:
                return "", "The tutor returned an invalid explanation."
            if _MATH_CHARS.search(text) or _NUMERIC_WORD.search(text) or _SYMBOLIC_MINUS.search(text):
                return "", "The tutor placed unverified mathematics in its explanation."
            out.append(text.strip())
        elif kind == "equality":
            left, right = block.get("left"), block.get("right")
            result = check_equality(left, right)
            if result is not True:
                return "", "A mathematical step was incorrect or could not be verified."
            out.append(f"${_math_tex(left)} = {_math_tex(right)}$")
        else:
            return "", "The tutor returned an unsupported response."
    return "\n\n".join(out), None
