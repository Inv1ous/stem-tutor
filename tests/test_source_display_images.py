"""Source-verified questions show each figure once, context first, and never the PDF text beside their images."""
import io

from PIL import Image, ImageDraw

from solvability_support import TARGET, register_bank, source_item, tutor_for, vault_with_flashcards
from tutorlib.asset_library import write_asset
from tutorlib.source_questions import display_images, to_instance

MEDIA = 'Library/Courses/9702/Questions/SourceVerified/Media/'
HEADER, KEY, QUESTION = MEDIA + 'header.png', MEDIA + 'key.png', MEDIA + 'question.png'


def page(lines, height):
    image = Image.new('L', (600, height), 255)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((40, 20 + 30 * i), line, fill=0)
    draw.rectangle((40, height - 60, 560, height - 20), outline=0)
    return image


def png(image):
    out = io.BytesIO()
    image.save(out, 'PNG')
    return out.getvalue()


def ref(path):
    return {'path': path, 'original': path, 'decision': 'keep'}


def item_with(question, context):
    return source_item('S-dup', 'mcq', [TARGET + '.1'], stem='Section B For each of the questions ... (PDF text)',
                       media={'question_media': [ref(p) for p in question], 'context_media': [ref(p) for p in context],
                              'cover_dropped': [], 'mark_scheme_media': []})


def vault(tmp_path):
    root = vault_with_flashcards(tmp_path)
    header = page(['Section B', 'For each of the questions in this section ...', 'The responses A to D ...'], 220)
    write_asset(root, HEADER, png(header), metadata={'kind': 'source_verified_question_media', 'course': '9702'})
    write_asset(root, KEY, png(header.crop((0, 70, 600, 220))), metadata={'kind': 'source_verified_question_media',
                                                                           'course': '9702'})
    write_asset(root, QUESTION, png(page(['33 Carbon can exist as allotropes ...', '1 ...', '2 ...'], 160)),
                metadata={'kind': 'source_verified_question_media', 'course': '9702'})
    return root


def test_context_first_each_image_once_and_a_cut_out_strip_dropped(tmp_path):
    root = vault(tmp_path)
    item = item_with([QUESTION, KEY], [HEADER, KEY])                    # as the 9701 w19 P12 Q33 bank row
    assert display_images(item) == [HEADER, KEY, QUESTION]               # without the vault: order and exact repeats
    assert display_images(item, root) == [HEADER, QUESTION]              # the key strip sits inside the header
    inst = to_instance(item, root)
    assert inst['images'] == [HEADER, QUESTION] and inst['image'] == HEADER
    assert inst['stem'] == ''                                            # images only, no PDF text


def test_distinct_figures_are_all_kept(tmp_path):
    root = vault(tmp_path)
    assert display_images(item_with([QUESTION], [KEY]), root) == [KEY, QUESTION]


def test_an_unreadable_image_is_never_hidden(tmp_path):
    root = vault(tmp_path)
    missing = MEDIA + 'not-registered.png'
    assert display_images(item_with([QUESTION, missing], [HEADER, KEY]), root) == [HEADER, KEY, QUESTION, missing]


def test_a_question_without_images_keeps_its_text():
    item = item_with([], [])
    assert to_instance(item)['stem'] == 'Section B For each of the questions ... (PDF text)'


def test_practice_serves_the_cleaned_images(tmp_path):
    root = vault(tmp_path)
    register_bank(root, [item_with([QUESTION, KEY], [HEADER, KEY])])
    t = tutor_for(root)
    t.start('practice', focus=[TARGET], scope='chapters', sources=['source_verified'], count=1)
    view = t.next()['items'][0]
    assert view['images'] == [HEADER, QUESTION] and view['stem'] == ''


def test_an_image_flagged_junk_is_never_shown_but_a_question_keeps_its_last_picture(tmp_path):
    from tutorlib.asset_library import register_asset
    root = vault(tmp_path)
    register_asset(root, HEADER, metadata={'junk': True})
    assert display_images(item_with([QUESTION], [HEADER]), root) == [QUESTION]
    register_asset(root, QUESTION, metadata={'junk': True})
    assert display_images(item_with([QUESTION], [HEADER]), root) == [HEADER, QUESTION]   # all flagged: nothing vanishes
