"""A printed question is shown as its pictures (in page order, once each) with one line saying which parts to do;
parts of one printed question that the chosen topics all cover are served together."""
import copy

from solvability_support import OTHER, THIRD, TARGET, tutor_for, vault_with_flashcards
from test_topicals import item as topical_item, publish
from tutorlib import question_display as qd
from tutorlib.asset_library import write_asset

PAGES = [f'Library/Courses/9702/Questions/Media/Long/9702_s23_22_q03_p{n:02d}_long_{n:012x}.png' for n in (4, 3, 2, 1)]
MCQ_IMAGE = 'Library/Courses/9702/Questions/Media/MCQ/9702_s23_22_q02_mcq_00000000abcd.png'


def part(label, kc, chapter, marks=2, **extra):  # one mark point per mark, as the bank requires
    row = topical_item(
        id=f'topical-9702_s23_22_q3-{label.replace("(", "").replace(")", "")}', kcs=[kc], kind='structured', marks=marks,
        stem=f'Part {label}. Read the full question in the source image. Long text copied from the PDF about {label}.',
        answer=f'answer {label}', images=list(PAGES), scheme=[{'point': f'mark {m} for {label}', 'label': f'M{m}'} for m in range(1, marks + 1)],
        source={'type': 'past', 'qid': '9702_s23_22_q3', 'part': label, 'ref': 'CAIE 9702 · Q3'})
    row.pop('options')
    row['topical'] = {**row['topical'], 'chapters': [chapter], 'requires': [chapter], 'support': {}}
    row.update(extra)
    return row


def vault(tmp_path, parts, extra=()):
    root = vault_with_flashcards(tmp_path)
    for n, path in enumerate([*PAGES, MCQ_IMAGE]):
        write_asset(root, path, b'\x89PNG\r\n\x1a\n' + bytes([n + 1]) * 40, metadata={'course': '9702', 'kind': 'Questions/Media'})
    publish(root, [*parts, *extra])
    return root


def serve(t, **options):
    t.start('practice', scope='chapters', sources=['topical'], count=5, **options)
    view = t.next()['items'][0]
    return view, t.session['presented'][str(view['n'])]


def test_instruction_wording_and_page_order():
    assert qd.instruction(['a(iii)']) == 'Do (a)(iii).'
    assert qd.instruction(['a(i)', 'c']) == 'Do (a)(i) and (c).'
    assert qd.instruction(['a', 'b(i)', 'c']) == 'Do (a), (b)(i) and (c).'
    assert qd.instruction(['a', 'b'], whole=True) == 'Do the whole question.'
    assert qd.page_order(PAGES) == PAGES[::-1]
    assert sorted(['b', 'a(ii)', 'a(i)', 'a'], key=qd.part_key) == ['a', 'a(i)', 'a(ii)', 'b']


def test_one_part_is_shown_as_pictures_in_page_order_and_a_short_instruction(tmp_path):
    t = tutor_for(vault(tmp_path, [part('a(iii)', TARGET + '.1', TARGET)]))
    view, _ = serve(t, focus=[TARGET])
    assert view['stem'] == 'Do (a)(iii).' and view['image_only'] is True
    assert view['images'] == PAGES[::-1] and view['image'] == PAGES[-1]
    assert 'Long text' not in view['stem'] and not view.get('figure_text')


def test_two_parts_in_the_chosen_topics_are_one_question_with_all_their_marks(tmp_path):
    rows = [part('a(i)', TARGET + '.1', TARGET), part('c', OTHER + '.1', OTHER, marks=3),
            part('d', THIRD + '.1', THIRD)]
    t = tutor_for(vault(tmp_path, rows))
    view, p = serve(t, focus=[TARGET, OTHER])
    assert view['stem'] == 'Do (a)(i) and (c).' and view['marks'] == 5
    assert p['merged_items'] and p['do_whole'] is False
    assert [pt['label'] for pt in p['inst']['scheme']] == ['(a)(i) M1', '(a)(i) M2', '(c) M1', '(c) M2', '(c) M3']
    assert set(p['kcs']) == {TARGET + '.1', OTHER + '.1'}
    assert view['scheme_points'] == 5


def test_every_part_of_the_question_chosen_says_do_the_whole_question(tmp_path):
    rows = [part('a', TARGET + '.1', TARGET), part('b', OTHER + '.1', OTHER)]
    t = tutor_for(vault(tmp_path, rows))
    view, p = serve(t, focus=[TARGET, OTHER])
    assert view['stem'] == 'Do the whole question.' and p['do_whole'] is True


def test_answering_a_merged_question_marks_every_part_seen_and_serves_none_again(tmp_path):
    rows = [part('a', TARGET + '.1', TARGET), part('c', OTHER + '.1', OTHER)]
    root = vault(tmp_path, rows)
    t = tutor_for(root)
    view, p = serve(t, focus=[TARGET, OTHER])
    assert t.session['blocks'][0]['merged'] == ['topical-9702_s23_22_q3-c']      # not served again as its own question
    result = t.answer(f"{view['n']} pts=1,2,3,4")['results'][0]
    assert result.get('event')
    answer = [e for e in t.vault.events() if e['type'] == 'answer'][-1]
    assert answer['merged_items'] == ['topical-9702_s23_22_q3-c'] and answer['marks'] == 4
    seen = tutor_for(root).state['items_seen']                                   # after a full refold of the log
    assert 'topical-9702_s23_22_q3-a' in seen and 'topical-9702_s23_22_q3-c' in seen
