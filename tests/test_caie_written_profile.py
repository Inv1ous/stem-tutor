"""Original CAIE written proof uses registered bytes and disposable preparations."""
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import copy_to_vault, read_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extraction'))


def ref(course, role, year=2024):
    return f'Library/Courses/{course}/Sources/PastPapers/{course}/{year}/s/{course}_s{year % 100:02d}_{role}_22.pdf'


def test_original_written_profile_is_available():
    assert importlib.util.find_spec('caie_written_profile'), 'CAIE original written profile is missing'


@pytest.fixture
def profile():
    if not importlib.util.find_spec('caie_written_profile'):
        pytest.skip('CAIE original written profile is missing')
    return importlib.import_module('caie_written_profile')


@pytest.fixture
def sources(tmp_path):
    vault = tmp_path / 'vault'; vault.mkdir()
    for course in ('9701', '9702'):
        for role in ('qp', 'ms'):
            copy_to_vault(ref(course, role), vault)
    return vault


@pytest.mark.parametrize('course,maximum,parts,pages,private,context', [
    ('9701', 15, [('a',2),('b',3),('c',1),('d(i)',1),('d(ii)',2),('e(i)',2),('e(ii)',1),('e(iii)',1),('f(i)',1),('f(ii)',1)], [2,3], [6,7], [1,15,16]),
    ('9702', 10, [('a',1),('b(i)',3),('b(ii)',2),('b(iii)',1),('b(iv)',3)], [4,5], [6], [1,2]),
])
def test_actual_q1_has_complete_native_scope_and_independent_parts(profile, sources, course, maximum, parts, pages, private, context):
    bundle = profile.analyse(sources, ref(course,'qp'), ref(course,'ms'))
    q = next(q for q in bundle['questions'] if q['number'] == 1)
    assert not q['hold_reasons']
    assert q['official_qid'] == f'{course}_s24_22_q1'
    assert q['marks'] == maximum
    assert [(p['part'],p['marks']) for p in q['required_parts']] == parts
    assert [r['page'] for r in q['regions']] == pages
    assert [r['page'] for r in q['context_regions']] == context
    assert [r['page'] for r in q['mark_scheme_regions']] == [2,3,4,5] + private
    assert all(p['public_mark_witness'] and p['private_mark_witnesses'] for p in q['required_parts'])
    assert len(bundle['pages']) == sum(s['pages'] for s in bundle['sources'].values())
    assert bundle['paper_complete'] is False or all(not q['hold_reasons'] for q in bundle['questions'])


def test_rotation_normalized_private_text_and_guidance_are_complete(profile, sources, tmp_path):
    out=tmp_path/'package'
    descriptor=profile.prepare(sources,ref('9702','qp'),ref('9702','ms'),out,dpi=36)
    result=profile.verify(sources,out)
    row=next(q for q in result['items'] if q['number']==1)
    assert 'percentage uncertainty' in row['scheme_text']
    assert 'GENERIC MARKING PRINCIPLE' in row['scheme_text']
    assert '750' in row['question_text'] and '160' in row['question_text']
    assert row['source_verified'] and row['kcs']==[]
    assert row['mastery_certified'] is False and row['teaching_approved'] is False
    assert row['id']==row['canonical_id']==row['official_qid']=='9702_s24_22_q1'
    assert result['metrics']['model_calls']==0
    assert len(result['page_proofs'])==28
    assert all(result['media'][name]['visibility']=='private_answer' for name in row['mark_scheme_media'])
    assert all(result['_pixels'][name]==(out/name).read_bytes() for name in descriptor['media'])
    assert len(row['required_parts'][1]['private_mark_witnesses'])==3
    guarded=profile.verify(sources,out,guard_holds={row['id']:['guard2:preserved']})
    assert row['id'] not in {q['id'] for q in guarded['items']}
    assert {'id':row['id'],'reasons':['guard2:preserved']} in guarded['held']


@pytest.mark.parametrize('fault',['partmax','continuation','privatecrop','guidance','rotation','pixels','extra'])
def test_resealed_preparation_cannot_authorize_changed_source_claims(profile,sources,tmp_path,fault):
    out=tmp_path/'package'
    descriptor=profile.prepare(sources,ref('9701','qp'),ref('9701','ms'),out,dpi=24)
    if fault=='pixels':
        (out/next(iter(descriptor['media']))).write_bytes(b'forged')
    elif fault=='extra':
        (out/'hidden.txt').write_text('unbound')
    else:
        q=descriptor['questions'][0]
        if fault=='partmax':q['required_parts'][0]['marks']=3
        if fault=='continuation':q['regions'].pop()
        if fault=='privatecrop':q['mark_scheme_regions'][-1]['box']=[0,0,1,.5]
        if fault=='guidance':q['mark_scheme_regions'].pop(0)
        if fault=='rotation':descriptor['pages'][-1]['rotation']=0
        (out/'caie-descriptor.json').write_bytes(profile.canonical_bytes(descriptor))
    # The attacker may reseal all submitted files; replay still owns authority.
    seal={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
          for p in out.rglob('*') if p.is_file() and p.name!='COMPLETE'}
    (out/'COMPLETE').write_bytes(profile.canonical_bytes(seal))
    with pytest.raises(ValueError):profile.verify(sources,out)


@pytest.mark.parametrize('course,year',[('9701',2019),('9702',2019),('9701',2025),('9702',2025)])
def test_bounded_registered_additional_years_are_truthful_supported_or_held(profile,tmp_path,course,year):
    vault=tmp_path/'vault';vault.mkdir()
    for role in ('qp','ms'):copy_to_vault(ref(course,role,year),vault)
    bundle=profile.analyse(vault,ref(course,'qp',year),ref(course,'ms',year))
    assert bundle['exam']['year']==year
    if year == 2019 and course == '9702':
        proof=bundle['qp_paper_maximum_proof']
        assert proof['kind']=='complete_qp_whole_totals' and proof['maximum']==60
        assert [w['marks'] for w in proof['question_totals']]==[4,14,10,11,13,8]
        assert proof['physical_pages']==list(range(1,17))
        q=bundle['questions'][0]
        assert not q['hold_reasons'] and q['marks']==4
        assert [(p['part'],p['marks']) for p in q['required_parts']]==[('a',1),('b(i)',1),('b(ii)',2)]
        assert [r['page'] for r in q['context_regions']]==[1,2,3]
    assert bundle['questions'] and bundle['questions'][0]['number']==1
    for q in bundle['questions']:
        if not q['hold_reasons']:
            assert sum(p['marks'] for p in q['required_parts'])==q['marks']
            assert q['required_parts'] and q['regions'] and q['mark_scheme_regions']
    assert bundle['paper_complete']==(not bundle['exceptions'] and all(not q['hold_reasons'] for q in bundle['questions']))


@pytest.mark.parametrize('fault',['course','component','session','role','maximum'])
def test_independent_cover_identity_rejects_forgery(profile,fault):
    raw=read_bytes(ref('9702','qp'))
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        assert profile._cover(doc,{'course':'9702','component':'22','year':2024,'series':'s'},'qp')
        text=doc[0].get_text()
    replacements={'course':('9702/22','9701/22'),'component':('9702/22','9702/23'),
        'session':('May/June 2024','October/November 2024'),'role':('PHYSICS','PHYSICS MARK SCHEME'),
        'maximum':('total mark for this paper is 60','total mark for this paper is 61')}
    before,after=replacements[fault]
    with pymupdf.open() as forged:
        page=forged.new_page(width=1000,height=1500)
        page.insert_textbox(pymupdf.Rect(20,20,980,1480),text.replace(before,after),fontsize=10)
        with pytest.raises(ValueError):profile._cover(forged,{'course':'9702','component':'22','year':2024,'series':'s'},'qp')


def test_mismatched_pair_rejected(profile,sources):
    with pytest.raises(ValueError,match='pair|identity|course'):
        profile.analyse(sources,ref('9701','qp'),ref('9702','ms'))


def test_prepare_requires_fresh_external_folder(profile,sources,tmp_path):
    with pytest.raises(ValueError):profile.prepare(sources,ref('9702','qp'),ref('9702','ms'),sources/'package',dpi=24)
    out=tmp_path/'occupied';out.mkdir()
    with pytest.raises(ValueError):profile.prepare(sources,ref('9702','qp'),ref('9702','ms'),out,dpi=24)


@pytest.mark.parametrize('fault',['partmax','publicmax','missingtotal','continuation','privatecrop','rotation','reference'])
def test_actual_source_corruption_is_held_without_invented_parts(profile,sources,tmp_path,fault):
    from tutorlib.asset_library import write_asset
    role='qp' if fault in ('publicmax','missingtotal','continuation','reference') else 'ms'
    raw=read_bytes(ref('9702',role))
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        page=doc[{'partmax':5,'publicmax':3,'missingtotal':4,'continuation':4,'privatecrop':5,'rotation':5,'reference':1}[fault]]
        if fault=='rotation':
            page.set_rotation(0)
        else:
            if fault in ('continuation','reference','privatecrop'):
                # Remove all displayed content or the lower scheme rows. Raw
                # coordinates require derotation before applying a redaction.
                clip=pymupdf.Rect(0,0,page.rect.width,page.rect.height)
                if fault=='privatecrop':clip.y0=page.rect.height*.29
                clip=clip*page.derotation_matrix
                page.add_redact_annot(clip)
            else:
                literal={'partmax':'B1','publicmax':'[3]','missingtotal':'[Total:'}[fault]
                word=next(w for w in page.get_text('words') if w[4]==literal)
                page.add_redact_annot(pymupdf.Rect(word[:4]))
            page.apply_redactions(images=0,graphics=0)
        changed=doc.tobytes()
    altered=f'Library/InvalidFixtures/9702_s24_{role}_22.pdf'
    write_asset(sources,altered,changed,metadata={'purpose':'disposable invalid source fixture'})
    b=profile.analyse(sources,altered if role=='qp' else ref('9702','qp'),altered if role=='ms' else ref('9702','ms'))
    q=b['questions'][0]
    assert q['number']==1 and q['hold_reasons']
    assert b['paper_complete'] is False


def test_result_uses_existing_whole_rubric_contract_with_semantics_pending(profile,sources,tmp_path):
    from tutorlib.prepared_evidence import WHOLE_ASSESSMENT
    out=tmp_path/'package';profile.prepare(sources,ref('9702','qp'),ref('9702','ms'),out,dpi=24)
    result=profile.verify(sources,out)
    q=next(q for q in result['items'] if q['number']==1)
    assert q['assessment_mode']==WHOLE_ASSESSMENT
    assert result['whole_source_proof']['semantic_status']=='not_checked'
    assert result['whole_source_proof']['profile']==profile.PROFILE
    assert result['whole_source_proof']['descriptor_sha256']==result['preparation_sha256']


@pytest.mark.parametrize('fault',['competing_identity','blank_text','blank_diagram','after_total','after_total_diagram'])
def test_unexplained_source_content_cannot_hide_in_covered_pages(profile,sources,fault):
    from tutorlib.asset_library import write_asset
    raw=read_bytes(ref('9702','qp'))
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        if fault=='competing_identity':doc[3].insert_text((250,600),'9701/22/M/J/24')
        elif fault=='blank_text':doc[2].insert_text((100,300),'Secret extra question')
        elif fault=='blank_diagram':doc[2].draw_rect(pymupdf.Rect(100,300,200,400),fill=(1,0,0))
        elif fault=='after_total_diagram':doc[4].draw_rect(pymupdf.Rect(100,600,200,700),fill=(1,0,0))
        else:doc[4].insert_text((100,600),'Unassigned question continuation')
        changed=doc.tobytes()
    altered='Library/InvalidFixtures/9702_s24_qp_22.pdf'
    write_asset(sources,altered,changed,metadata={'purpose':'disposable invalid source fixture'})
    b=profile.analyse(sources,altered,ref('9702','ms'))
    assert b['questions'][0]['hold_reasons']
    assert not b['paper_complete']


def test_each_mark_witness_binds_its_exact_registered_source(profile,sources):
    bundle=profile.analyse(sources,ref('9702','qp'),ref('9702','ms'))
    q=bundle['questions'][0]
    assert q['maximum_authority']['qp']['page']==5
    for part in q['required_parts']:
        for role,witnesses in [('qp',[part['public_mark_witness']]),('ms',part['private_mark_witnesses'])]:
            for witness in witnesses:
                assert witness['source_id']==bundle['sources'][role]['reference']
                assert witness['source_sha256']==bundle['sources'][role]['sha256']


@pytest.mark.parametrize('number',['1','9'])
def test_repeated_and_unknown_public_anchors_hold_the_source(profile,sources,number):
    from tutorlib.asset_library import write_asset
    with pymupdf.open(stream=read_bytes(ref('9702','qp')),filetype='pdf') as doc:
        doc[3].insert_text((49.6,700),number)
        doc[3].insert_text((72.3,700),'(a)')
        changed=doc.tobytes()
    altered='Library/InvalidFixtures/9702_s24_qp_22.pdf'
    write_asset(sources,altered,changed,metadata={'purpose':'disposable invalid source fixture'})
    b=profile.analyse(sources,altered,ref('9702','ms'))
    assert b['paper_complete'] is False
    assert all('nonsequential_or_repeated_public_anchors' in q['hold_reasons'] for q in b['questions'])


def test_literal_compact_part_variant_is_bounded(profile):
    assert profile._part_label('2c(i)')==(2,'c(i)')
    assert profile._part_label('2(c)(ii)')==(2,'c(ii)')
    for unsupported in ('2','2(c)(i)(a)','answer 2(c)','2c','2(c) or 2(d)'):
        assert profile._part_label(unsupported) is None


@pytest.mark.parametrize('fault',['wrong','missing','duplicate','cover_conflict','notice_extra'])
def test_missing_cover_maximum_needs_independent_complete_qp_aggregate(profile,tmp_path,fault):
    from tutorlib.asset_library import write_asset
    vault=tmp_path/'vault';vault.mkdir()
    for role in ('qp','ms'):copy_to_vault(ref('9702',role,2019),vault)
    with pymupdf.open(stream=read_bytes(ref('9702','qp',2019)),filetype='pdf') as doc:
        if fault=='cover_conflict':
            doc[0].insert_text((45,700),'The total mark for this paper is 61.')
        elif fault=='notice_extra':
            doc[15].insert_text((100,700),'Extra assessment content')
        else:
            page=doc[4]
            total=profile._public(doc)[0][4]['totals'][0]
            box=total['box'];clip=pymupdf.Rect(box[0]*page.rect.width,box[1]*page.rect.height,box[2]*page.rect.width,box[3]*page.rect.height)
            if fault!='duplicate':
                page.add_redact_annot(clip);page.apply_redactions(images=0,graphics=0)
            if fault!='missing':page.insert_text((400,680),'[Total: '+('5' if fault=='wrong' else '4')+']',fontsize=12)
        changed=doc.tobytes()
    altered='Library/InvalidFixtures/9702_s19_qp_22.pdf'
    write_asset(vault,altered,changed,metadata={'purpose':'disposable invalid source fixture'})
    if fault=='cover_conflict':
        with pytest.raises(ValueError,match='cover_maximum'):profile.analyse(vault,altered,ref('9702','ms',2019))
    else:
        bundle=profile.analyse(vault,altered,ref('9702','ms',2019))
        assert bundle['qp_paper_maximum_proof']['maximum'] is None
        assert all('qp_paper_maximum_unproved' in q['hold_reasons'] for q in bundle['questions'])
        if fault=='wrong':assert bundle['questions'][0]['marks']==5


@pytest.mark.parametrize('page_index,point,kind',[
    (4,(100,815),'text'),  # Exact Spec P1: full rendered page exposed this secret.
    (4,(4,300),'text'),(4,(575,300),'text'),(4,(100,20),'text'),
    (4,(100,810),'vector'),(4,(2,300),'vector'),(4,(100,810),'image'),
    (4,(100,810),'annotation'),
    (2,(100,815),'text'),(2,(4,300),'text'),(2,(100,810),'vector'),
    (2,(2,300),'image'),(2,(100,810),'annotation'),
    (1,(100,815),'text'),(0,(100,815),'text'),
])
def test_fix1_full_exposed_pages_hold_unknown_margins(profile,sources,page_index,point,kind):
    from tutorlib.asset_library import write_asset
    with pymupdf.open(stream=read_bytes(ref('9702','qp')),filetype='pdf') as doc:
        page=doc[page_index];x,y=point
        if kind=='text':page.insert_text(point,'SECRET ANSWER 42',fontsize=10)
        elif kind=='vector':page.draw_rect(pymupdf.Rect(x,y,x+12,y+12),fill=(1,0,0))
        elif kind=='image':
            image=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,8,8));image.clear_with(0)
            page.insert_image(pymupdf.Rect(x,y,x+12,y+12),pixmap=image)
        else:
            annotation=page.add_rect_annot(pymupdf.Rect(x,y,x+12,y+12))
            annotation.set_colors(stroke=(1,0,0),fill=(1,0,0));annotation.update()
        changed=doc.tobytes()
    altered='Library/InvalidFixtures/9702_s24_qp_22.pdf'
    write_asset(sources,altered,changed,metadata={'purpose':'disposable invalid source fixture'})
    b=profile.analyse(sources,altered,ref('9702','ms'))
    assert b['questions'][0]['hold_reasons']
    assert any(e['reason']=='unqualified_public_page_content' and e['page']==page_index+1 for e in b['exceptions'])
    assert all(r['box']==[0,0,1,1] for r in b['questions'][0]['regions'])


@pytest.mark.parametrize('literal',[
    'Maximum Mark: 61','Maximum Marks: 61','Max. Marks = 61','Total marks: 61',
    'Maximum possible marks: 61','Maximum mark for this paper is 61',
    'Maximum Mark: sixty-one','Maximum Mark: 60/61','Maximum Mark: 60 or 61',
])
def test_fix1_alternate_maximum_claims_are_not_absence(profile,literal):
    with pymupdf.open(stream=read_bytes(ref('9702','qp',2019)),filetype='pdf') as doc:
        doc[0].insert_text((45,700),literal,fontsize=12)
        assert literal in doc[0].get_text()
        with pytest.raises(ValueError,match='cover_maximum'):
            profile._cover(doc,{'course':'9702','component':'22','year':2019,'series':'s'},'qp')


def test_fix1_exact_reviewed_maximum_reproducer_rejects_pair(profile,tmp_path):
    from tutorlib.asset_library import write_asset
    vault=tmp_path/'vault';vault.mkdir()
    for role in ('qp','ms'):copy_to_vault(ref('9702',role,2019),vault)
    with pymupdf.open(stream=read_bytes(ref('9702','qp',2019)),filetype='pdf') as doc:
        doc[0].insert_text((45,700),'Maximum Mark: 61',fontsize=12)
        changed=doc.tobytes()
    altered='Library/InvalidFixtures/9702_s19_qp_22.pdf'
    write_asset(vault,altered,changed,metadata={'purpose':'disposable invalid source fixture'})
    with pytest.raises(ValueError,match='cover_maximum'):
        profile.analyse(vault,altered,ref('9702','ms',2019))


def test_fix1_identical_raster_with_unqualified_source_bytes_stays_held(profile,sources):
    from tutorlib.asset_library import write_asset
    with pymupdf.open(stream=read_bytes(ref('9702','qp')),filetype='pdf') as doc:
        doc.set_metadata({**doc.metadata,'keywords':'unqualified byte revision'})
        changed=doc.tobytes()
    altered='Library/InvalidFixtures/9702_s24_qp_22.pdf'
    write_asset(sources,altered,changed,metadata={'purpose':'disposable invalid source fixture'})
    b=profile.analyse(sources,altered,ref('9702','ms'))
    assert b['questions'][0]['hold_reasons']
    assert b['public_pixel_proofs']
    assert all(not p['source_origin_match'] for p in b['public_pixel_proofs'])


def test_fix1_native_exclusions_are_fixed_source_bound_witnesses(profile,sources):
    b=profile.analyse(sources,ref('9702','qp'),ref('9702','ms'))
    proofs=b['public_pixel_proofs']
    assert len(proofs)==16
    assert all(p['qualified'] and p['source_origin_match'] for p in proofs)
    assert all(p['registered_origin_sha256']==b['sources']['qp']['sha256'] for p in proofs)
    assert all(p['observed']['margin']==p['expected']['margin'] for p in proofs)
    assert 'full' in proofs[2]['expected']  # Entire blank, including every margin.
    assert 'tail' in proofs[4]['expected']  # Entire width below literal Q1 Total.
    assert 'full' in proofs[0]['expected'] and 'full' in proofs[1]['expected']


def test_fix1_ms_rejects_conflicting_qp_style_maximum(profile):
    with pymupdf.open(stream=read_bytes(ref('9702','ms')),filetype='pdf') as doc:
        doc[0].insert_text((45,700),'The total mark for this paper is 61.',fontsize=12)
        with pytest.raises(ValueError,match='cover_maximum'):
            profile._cover(doc,{'course':'9702','component':'22','year':2024,'series':'s'},'ms')


def test_fix2_actual_rowless_table_continuation_holds_entire_pair(profile,sources,tmp_path):
    from tutorlib.asset_library import write_asset
    with pymupdf.open(stream=read_bytes(ref('9702','ms')),filetype='pdf') as original, pymupdf.open() as extra:
        extra.insert_pdf(original,from_page=5,to_page=5)
        page=extra[0];labels=[w for w in page.get_text('words') if profile._part_label(w[4])]
        assert len(labels)==5
        before_scores=[w['text'] for w in profile._words(page) if w['box'][0]>.89 and w['box'][1]>.13 and w['box'][1]<.9]
        before_answers=[w['text'] for w in profile._words(page) if .14<w['box'][0]<.88 and .13<w['box'][1]<.9]
        for word in labels:page.add_redact_annot(pymupdf.Rect(word[:4]),fill=(1,1,1))
        page.apply_redactions()
        assert all(label in page.get_text() for label in ('Question','Answer','Marks'))
        assert before_scores==[w['text'] for w in profile._words(page) if w['box'][0]>.89 and w['box'][1]>.13 and w['box'][1]<.9]
        assert before_answers==[w['text'] for w in profile._words(page) if .14<w['box'][0]<.88 and .13<w['box'][1]<.9]
        original.insert_pdf(extra,start_at=6)
        pages,_=profile._private(original,'9702')
        assert pages[6]['role']=='mark_scheme' and pages[6]['rows']==[]
        assert 'missing_private_rows' in pages[6]['hold_reasons']
        altered_bytes=original.tobytes()
    altered='Library/InvalidFixtures/9702_s24_ms_22.pdf'
    write_asset(sources,altered,altered_bytes,metadata={'purpose':'disposable invalid rowless continuation'})
    b=profile.analyse(sources,ref('9702','qp'),altered)
    assert all('unowned_private_assessment_page' in q['hold_reasons'] for q in b['questions'])
    assert any(e.get('source')=='ms' and e.get('page')==7 and e['reason']=='missing_private_rows' for e in b['exceptions'])
    page=next(p for p in b['private_page_ownership'] if p['page']==7)
    assert page['owners']==[] and page['owned'] is False
    assert not any(r['page']==7 for q in b['questions'] for r in q['mark_scheme_regions'])
    assert b['paper_complete'] is False
    # Replay must reproduce an explicit hold, never authorize the omission.
    out=tmp_path/'rowless-package';profile.prepare(sources,ref('9702','qp'),altered,out,dpi=24)
    result=profile.verify(sources,out)
    assert result['items']==[]
    assert all('unowned_private_assessment_page' in q['reasons'] for q in result['held'])


@pytest.mark.parametrize('mixed',[False,True])
def test_fix2_private_page_unknown_owners_are_explicit_global_holds(profile,sources,mixed):
    from tutorlib.asset_library import write_asset
    with pymupdf.open(stream=read_bytes(ref('9702','ms')),filetype='pdf') as original, pymupdf.open() as extra:
        page=extra.new_page(width=842,height=595.22)
        page.insert_text((300,22),'9702/22 May/June 2024')
        for text,x in [('Question',68.5),('Answer',408.4),('Marks',741.2)]:page.insert_text((x,66),text)
        labels=['1(a)','99(a)'] if mixed else ['99(a)']
        for i,label in enumerate(labels):
            y=92+i*65
            page.insert_text((78,y),label)
            page.insert_text((160,y),'Unowned assessment content; invalid test input')
            page.insert_text((760,y),'B1')
        original.insert_pdf(extra,start_at=6)
        pages,_=profile._private(original,'9702')
        assert {r['number'] for r in pages[6]['rows']}==({1,99} if mixed else {99})
        changed=original.tobytes()
    altered='Library/InvalidFixtures/9702_s24_ms_22.pdf'
    write_asset(sources,altered,changed,metadata={'purpose':'disposable invalid private ownership'})
    b=profile.analyse(sources,ref('9702','qp'),altered)
    assert all('unowned_private_assessment_page' in q['hold_reasons'] for q in b['questions'])
    page=next(p for p in b['private_page_ownership'] if p['page']==7)
    assert page['owned'] is False and page['question_numbers']==([1,99] if mixed else [99])
    assert page['owners']==(['9702_s24_22_q1'] if mixed else [])


@pytest.mark.parametrize('course,year',[('9701',2024),('9702',2024),('9702',2019)])
def test_fix2_actual_q1_private_pages_have_positive_complete_ownership(profile,tmp_path,course,year):
    vault=tmp_path/'vault';vault.mkdir()
    for role in ('qp','ms'):copy_to_vault(ref(course,role,year),vault)
    b=profile.analyse(vault,ref(course,'qp',year),ref(course,'ms',year))
    q=b['questions'][0]
    assert not q['hold_reasons']
    assert not any(e['reason']=='unowned_private_assessment_page' for e in b['exceptions'])
    assessment=[p for p in b['pages'] if p['source']==b['sources']['ms']['reference'] and p['role']=='mark_scheme']
    assert 'private_page_ownership' in b
    assert {p['page'] for p in assessment}=={p['page'] for p in b['private_page_ownership']}
    assert all(p['owned'] and p['owners'] for p in b['private_page_ownership'])
    for page in b['private_page_ownership']:
        assert page['source_sha256']==b['sources']['ms']['sha256']
        for owner in page['owners']:
            question=next(q for q in b['questions'] if q['id']==owner)
            assert any(r['page']==page['page'] and r['box']==[0,0,1,1] for r in question['mark_scheme_regions'])
