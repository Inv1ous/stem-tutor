"""Read approved immutable source repairs without rewriting historical baselines."""
from __future__ import annotations

import copy
import json
import hashlib


def _reviewed_repairs(sub, library):
    for identifier, record in library.records().items():
        if (record.get('kind') != 'source_repair' or record.get('subtopic') != sub
                or record.get('repair_status') == 'superseded'):
            continue
        manifest = json.loads(library.read('asset:' + identifier))
        if manifest.get('format_version') != 1 or manifest.get('subtopic') != sub:
            raise ValueError('invalid registered source repair')
        for binding in manifest['batches']:
            proposal_bytes = library.read(binding['proposal'])
            proposal = json.loads(proposal_bytes)
            review = json.loads(library.read(binding['review']))
            if review.get('proposal_sha256') != hashlib.sha256(proposal_bytes).hexdigest():
                raise ValueError('source review is not bound to the exact proposal')
            if review.get('reviewer') == binding['author'] or not review.get('reviewer'):
                raise ValueError('source repair requires an independent reviewer')
            if review.get('rejected_corrections'):
                raise ValueError('source repair includes rejected corrections')
            decisions = {item['item']: item for item in review['decisions']}
            if len(decisions) != len(review['decisions']):
                raise ValueError('duplicate source review decisions')
            for repair in proposal['corrections']:
                if repair.get('sub') != sub:
                    continue
                selector = repair['selector']
                if (not isinstance(selector, list) or len(selector) not in (3, 4)
                        or selector[:2] != ['items', {'id': repair['item']}]
                        or selector[2] not in ('stem', 'options', 'explanation')
                        or (len(selector) == 4 and (selector[2] != 'options' or selector[3] not in ('A', 'B', 'C', 'D')))):
                    raise ValueError('unsafe source repair selector')
                decision = decisions.get(repair['item'], {})
                source = library.record(repair['image_reference'])
                library.read(repair['image_reference'])
                if (decision.get('accepted') is not True or decision.get('image_sha256') != source['sha256']
                        or repair['image_sha256'] != source['sha256']):
                    raise ValueError('source repair image/review binding mismatch')
                if not isinstance(repair['old'], str) or not isinstance(repair['new'], str) or not repair['new'].strip():
                    raise ValueError('invalid source repair text')
                yield repair, source['sha256'], manifest.get('question_ids', {}).get(repair['item'])


def overlay(original: dict, current: dict, library) -> tuple[dict, int]:
    """Stage only exact reviewed fields in memory; preserve historical baseline bytes."""
    result = copy.deepcopy(original)
    changed = 0
    for repair, source_hash, _ in _reviewed_repairs(current.get('subtopic'), library):
        selector = repair['selector']
        old_items = [item for item in result['items'] if item.get('id') == repair['item']]
        new_items = [item for item in current['items'] if item.get('id') == repair['item']]
        if len(old_items) > 1 or len(new_items) > 1:
            raise ValueError('ambiguous source repair identity')
        if not old_items or not new_items:
            continue  # additions/deletions still belong to the ordinary no-loss gate
        before, after = old_items[0], new_items[0]
        if any(library.record(item['image'])['sha256'] != source_hash for item in (before, after)):
            raise ValueError('repair source does not belong to this question')
        for part in selector[2:-1]:
            before, after = before[part], after[part]
        field = selector[-1]
        if before[field] == repair['new']:
            continue  # a later pass already started with the repaired source
        if before[field] != repair['old'] or after[field] != repair['new']:
            continue  # unrelated changes remain visible to the no-loss gate
        before[field] = repair['new']
        changed += 1
    return result, changed


def bank_overrides(sub: str, library) -> dict:
    """Reuse source-verified values when Foundry rebuilds extras from an older bank."""
    result = {}
    for repair, source_hash, question_id in _reviewed_repairs(sub, library):
        if not isinstance(question_id, str) or not question_id:
            continue
        entry = result.setdefault(question_id, {'image_sha256': source_hash, 'fields': {}})
        if entry['image_sha256'] != source_hash:
            raise ValueError('conflicting source images for one official question')
        selector = repair['selector'][2:]
        holder = entry['fields']
        if len(selector) == 2:
            holder = holder.setdefault(selector[0], {})
        field = selector[-1]
        if field in holder and holder[field]['new'] != repair['new']:
            raise ValueError('conflicting independently reviewed source repairs')
        value = holder.setdefault(field, {'new': repair['new'], 'old': []})
        if repair['old'] not in value['old']:
            value['old'].append(repair['old'])
    return result
