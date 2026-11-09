"""Conservative original CAIE 9701/9702 Paper 22 written-source preparation.

No semantic approval or publication lives here. Every proposal and PNG is replayed
from registered bytes; unsupported/shared-page layouts remain explicit holds.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import time

import pymupdf
from tutorlib.asset_library import AssetLibrary
from tutorlib.prepared_evidence import WHOLE_ASSESSMENT
from prepared_scope import _physical, _read_json, _words

PROFILE = 'caie-original-written-v1'
# Literal 140-word UCLES publisher notice present in the authenticated 2019
# final pages. A competing word invalidates this bounded non-assessment role.
_PUBLISHER_NOTICE_SHA256 = 'db5412bd8b2e037694def063e2c732f3164c85a9e83fc55b88d37e3f3006bf84'


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _identity(path, role):
    match = re.fullmatch(r'(970[12])_([sw])(\d{2})_' + role + r'_22\.pdf', Path(path).name)
    if not match:
        raise ValueError('source_identity: original 9701/9702 component 22 source required')
    return {'course': match[1], 'series': match[2], 'year': 2000 + int(match[3]), 'component': '22'}


def _maximum_declarations(text):
    """Read maximum-mark assertions before interpreting a QP field as absent."""
    labels=list(re.finditer(r'\b(?:maximum|max\.?|total)(?:\s+(?:possible|available|number|of|total))*\s+marks?\b',text,re.I))
    markers=list(re.finditer(r'\b(?:maximum|max)(?:\.)?(?=\s)|\btotal\b(?=.{0,80}\bmarks?\b)',text,re.I))
    if any(not any(label.start()==marker.start() for label in labels) for marker in markers):
        raise ValueError('cover_maximum: unsupported maximum declaration')
    values=[]
    for label in labels:
        tail=text[label.end():]
        tail=re.sub(r'^\s*(?:(?:for|of|on)\s+(?:this|the)\s+(?:paper|examination|exam)\s*)?(?:(?:is|are)\b|[:=])?\s*','',tail,flags=re.I)
        token=re.match(r'\S+',tail)
        if (not token or token[0].rstrip('.,;')!='60'
                or re.match(r'\s*(?:marks?\b\s*)?(?:or\b|and\b|to\b|[-/–])',tail[token.end():],re.I)):
            raise ValueError('cover_maximum: conflicting or unsupported maximum declaration')
        values.append({'label':label[0],'value':60,'token':token[0]})
    return values


def _cover(doc, exam, role):
    text = ' '.join(doc[0].get_text().split())
    if not re.search(r'Cambridge International (?:AS\s*(?:&|and)\s*A Level|Advanced Subsidiary and Advanced Level)', text):
        raise ValueError('cover_identity: native Cambridge AS & A Level required')
    codes = set(re.findall(r'\b(970\d)\s*/\s*(\d{2})\b', text))
    if codes != {(exam['course'], exam['component'])}:
        raise ValueError('cover_identity: course/component differs')
    subject = {'9701': 'CHEMISTRY', '9702': 'PHYSICS'}[exam['course']]
    if subject not in text or not re.search(r'Paper 2 AS Level Structured Questions', text):
        raise ValueError('cover_role: AS structured Paper 2 required')
    is_scheme = bool(re.search(r'MARK SCHEME', text, re.I))
    if is_scheme != (role == 'ms'):
        raise ValueError('cover_role: QP/MS role differs')
    sessions = {(s, int(y)) for s, y in re.findall(r'(May/June|October/November)\s+(20\d{2})', text)}
    expected = ('May/June' if exam['series'] == 's' else 'October/November', exam['year'])
    if sessions != {expected}:
        raise ValueError('cover_session: printed source session differs')
    maxima = _maximum_declarations(text)
    if not maxima and role == 'ms':
        raise ValueError('cover_maximum: contradictory or missing independent maximum 60')
    return {'page': 1, 'role': role, 'text': text, 'text_sha256': _sha(text.encode()), 'exam': exam, 'maximum': 60 if maxima else None, 'maximum_declarations':maxima}


def _region(source, page):
    return {'source_id': source['reference'], 'source_sha256': source['sha256'], 'role': source['role'], 'page': page, 'box': [0, 0, 1, 1]}


def _position(word):
    return (round(word['box'][1], 4), word['box'][0])


def _body(words):
    return [w for w in words if .06 <= w['box'][1] < .94 and .06 <= w['box'][0] <= .94]


def _graphics_intersect(page, box):
    displayed=pymupdf.Rect(box[0]*page.rect.width,box[1]*page.rect.height,box[2]*page.rect.width,box[3]*page.rect.height)
    boxes=[pymupdf.Rect(info['bbox'])*page.rotation_matrix for info in page.get_image_info()]
    boxes += [drawing['rect']*page.rotation_matrix for drawing in page.get_drawings()]
    return any(rect.intersects(displayed) for rect in boxes)


def _blank_proved(page, words):
    # Production barcodes can emit comma glyphs near the page heading. The
    # actual blank body must contain no other glyph, image or vector evidence.
    extra=[w for w in _body(words) if w['text'] not in ('BLANK','PAGE',',')]
    if extra and _sha(' '.join(w['text'] for w in extra).encode())!=_PUBLISHER_NOTICE_SHA256:
        return False
    return not _graphics_intersect(page,[.1,.06,.9,.94])


# Populated only from fixed, independently inspected registered originals. A
# candidate can match these witnesses; it cannot generate its own exclusions.
_PUBLIC_RASTER_BASELINES = json.loads(r'''{
    "9701_s24_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2024/s/9701_s24_qp_22.pdf",
        "source_sha256": "02463479abb9dd19ef2bbc8297bf832f083bc6a52b95977119c3a7260d69580c",
        "pages": [
            {"size":[596,842,3,1788],"margin":"e03d34822f188d4c83c50d992d165a518f15a261f1cbab5be780efe3480d1fb8","full":"68c509e96c24b05622e2eb17bf2d4daa647d000f01eb25642cedeee299f1f7b5","objects":"84e881a26f56bab697a80a508870558a5a521c48cbc23e0bb6e7f67e71eeaf45"},
            {"size":[596,842,3,1788],"margin":"54a152c2d67d09b225a2f30491e12d7cf74f8ad2584dacae3a4a18ddc5b44661","objects":"2e94db7c9bf7bb68b47741227bc35c914a2bff29fa10badd4e70c1d11b706eda"},
            {"size":[596,842,3,1788],"margin":"7f78c46d26c8a93807a12823793aab2da5adc95746ddc573ccfd004cd0910558","tail":[726,"025b1fa30cd53e64b1c8201fcada2ee6e17ca40096bcbde20f524470a16027af"],"objects":"fd45eedcd36105e1c4f76935cb4303eb370b7d5ed6294b1f02a1d9604ce73b16","total":{"marks":15,"literal":"[Total: 15]","box":[0.8365042738153767,0.8490995990726662,0.9166247906412338,0.8621654425896447]}},
            {"size":[596,842,3,1788],"margin":"b70f2073ad5c5a478aed381846d9330e9decca36b375d1bdecaa80dc6f11a18a","objects":"bfa3d89eb766c9f22f207ba0ad98d4880ce9c3b320bc19ae73613f2f2a4b285c"},
            {"size":[596,842,3,1788],"margin":"80ac482b0bfd520b881ff4b708f8f3e0e270d2d8aaac37ff502f7984a61a8c15","tail":[722,"b8e3af9e948bd8a72fd5ce606029e7c3384c46326739187474bda734bbf7123e"],"objects":"49d7eafb46894735cb12ad106416e311e2b74fa65803b7ae678bbe5ca11b93c9","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365084776522493,0.8442442764074324,0.9166289944781064,0.8573101199244109]}},
            {"size":[596,842,3,1788],"margin":"a6bf46a0c2f3bb40be3828c30ba801f1b0e7824fd70863f04224702b92d3f110","objects":"466da5baa3ced6f69fb1d496a647625a7f126d30224faa1799b643a1fbe266a6"},
            {"size":[596,842,3,1788],"margin":"79cb7b8dfa5d8dffad9ceb9cd4f106f430250c0dac2ccc345d58eb599a5d30ba","objects":"05b70bd3bef54f5065964a75457bbe60bba022c6a456a0193a37ac0d3b83c22d"},
            {"size":[596,842,3,1788],"margin":"5094d840203a46f31e0e1fe1377b5123e482412216c566f71525143cee1352a4","tail":[428,"79617f2ee36c3924b5e32294dfa32b4a5241b364827d28a531e842950c3552f5"],"objects":"8ec3985b90d07027fda15c1d0453824bf91ec2fb1b7f357fa73c0405b0277a17","total":{"marks":12,"literal":"[Total: 12]","box":[0.8365055554729598,0.4954672562961077,0.9166261235651203,0.5085330998130861]}},
            {"size":[596,842,3,1788],"margin":"e2de5888817e7ded5bca0342178bf7cfbf46629bf51163b00a43561c8a5ec831","full":"94ab5e34ffc2c3689d9987a962d5cb2387634c4282b41a55bd85317326be1e20","objects":"32e5145861450fc71ad0ffc7c95661649b01bb36d918faa888c11dc2500414fe"},
            {"size":[596,842,3,1788],"margin":"92c27d50893988c4e7df9700697b6db08fdb25e469430070ae2e932c55646439","objects":"d73d2cb22a64c5996f4a1d142a5376b5275511e8a6193d1f9cb49fb3e3a0801e"},
            {"size":[596,842,3,1788],"margin":"8d99b436d2160aa46d3563a20dc48413e9b54d686d08ad79ff313f0273b9f883","tail":[667,"ebf517d108995a919e0221b2ffd38358b6fb71d008903fa7c4602ba4490fc58d"],"objects":"eabee62f6c0ef449a403ae7f6162ad103ef70f564df6268fec4a1bfc14920ed2","total":{"marks":15,"literal":"[Total: 15]","box":[0.8364934053590718,0.7785851938322932,0.9166139221849289,0.7916510373492717]}},
            {"size":[596,842,3,1788],"margin":"24c0c3ff1570308a47e3a6be69aff31ad97f2fa8a22cc3b77241796c3bb206e5","objects":"a8dcfc69ecb94fdc61594d2237d4d2f6fb13f9890066a3f5559a9fee09f463c3"},
            {"size":[596,842,3,1788],"margin":"007cc2acdf734cb5717880c8e8e2caf91ddcb5ac3befee7e7ec8a83598037dcb","objects":"6e72e524119b54720e6a036877c1fba94d452513b8a64a029678463c6bf8d184"},
            {"size":[596,842,3,1788],"margin":"f4bf8732f5d9eef14ee07ad31e89b66e6d2697c72b013027f7843225c9fbfdf8","tail":[640,"d456aeb8d83e17f4c21f7707759667368f892c7f0041e32a2fc485eda7d52152"],"objects":"fa3798d03b0a2cd0d4dd9b07f169a3d7dca9761702f7bacdb341496847dbf68d","total":{"marks":8,"literal":"[Total: 8]","box":[0.8467747599583513,0.7474615257800002,0.9166210994673943,0.7605273692969787]}},
            {"size":[596,842,3,1788],"margin":"97a077fe068739ff44371e436702ffbcca41748335756fde6b158159b28952f0","full":"9ce48490b144942be187f4b582c947fc2f4380fd689c3348d0c0d5c2619904ad","objects":"75adf9ce21e00aab3ced67743b9d82c86955f251ef970b903622b961b36ab72c"},
            {"size":[596,842,3,1788],"margin":"b6d308e09bcc41b647b6b9f730d89d193ae3fc3ad94a4d28b461b3cc0b0f14f9","full":"c77091d087cd86ab8ff3d5962d94101f480963a8b9be60b9215b21e6b473c20a","objects":"553cabb4a8d34c729f004317cf8ed50d7fc88e8cd1e45832af95968f3fafa3d4"}
        ]
    },
    "9702_s24_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2024/s/9702_s24_qp_22.pdf",
        "source_sha256": "fe32f083bbe655738ca7765b3f45d7d5dadc7654727a3070f351fea88b963eaf",
        "pages": [
            {"size":[596,842,3,1788],"margin":"2f6baf4ef4b31bead03520fe751ed06648ef85c13efe8a8ff0a2c33a0aae3f34","full":"f29af9935c1f94927b4fdefbbcdbc51e31c2afeaffef812f99890634f7cf271d","objects":"33100001c9fb75592419344871ad3150197bdbf5a1dd4cb9e49a857cc952eb2e"},
            {"size":[596,842,3,1788],"margin":"6d8d1b7fbb4378e086204f7d4caa16248bcabaa58d458ec973804619e29ef7b0","full":"1b076f2a6442e938257333ea8a3fc42743ac39442c0ec7a92c93ec9f3665f86e","objects":"d09a7bbd393e9b21ef31761df4e8383187a5a9bebf305f014a17ca2ed710d310"},
            {"size":[596,842,3,1788],"margin":"05e28e2c18668a3f43348bbd7dd1cfb2049abbd208b942f4865676c8a8de90c8","full":"0fd6e70a3f71b2b04dafb0ac7bf5837ba26ebf272346a9279ebcc15d64e2487e","objects":"e485e1d52b9352a162a7d9aee362a9435ae92742c6fbefd71bd12fb866cc11ad"},
            {"size":[596,842,3,1788],"margin":"ee7c40d84084f9a7febb1780efd72dbf56b8b327f4e968b2eb7238573ae022e3","objects":"a91c1f73e8c7a299a912543106534e9103951142a4d7450dd2a917c7d73d10c9"},
            {"size":[596,842,3,1788],"margin":"c110e718dddf1869cded68c576c6cc8fed219d6f9e7d9ae4d39acbe2ab46d313","tail":[462,"d55fe49ac8428a2ff732e6ad3129436c1b93f2ff25d5f9ecdbd3880c2ce73adb"],"objects":"552c00afb92e1fbdcc15ad42f63645ce5c0c9c063075be117e1a44e37b98bb6b","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365117586956622,0.5354522579512325,0.9166322755215193,0.5485181014682109]}},
            {"size":[596,842,3,1788],"margin":"1419f1ad676929bb965edd5a5bb6b5682cd83544bacbe15fc3bd996ab751d739","objects":"2d5d2c8c667d564e3fb440ef1a093c4cd4d7f9c5802c013e087fbbcce5aad053"},
            {"size":[596,842,3,1788],"margin":"b1220d733dc3523ba3afbb35d3923b42bd6fbcd5d9bfb5e09c9943d4f163e984","tail":[696,"c78629e7bd15823f15aebf39545c07ed17b3099d2b43321a4c2e4e0374273071"],"objects":"b9d0a5146c6c055e498df6a8537bef6ab24cd267c24c33d1af3c2bff957b6def","total":{"marks":10,"literal":"[Total: 10]","box":[0.8364965326035746,0.8133508613681117,0.916617100695735,0.8264167048850902]}},
            {"size":[596,842,3,1788],"margin":"25785fe0196f26354bd5b628287ec34d3b704da5fad2a3e968939b44e727fc82","objects":"00b2e858903d7bb66c4f530783ba75d3d06608b7a7ddb762fa06d7b7664c0a4d"},
            {"size":[596,842,3,1788],"margin":"8f6f369bfc432594a3be3f9c8c026ead9be1156702545906a15458b3c374344d","tail":[774,"2258e241d279c51baf477bb8ac095ed74072ff70103f1dcb902e57f475bb3f39"],"objects":"50ca9703a50ee731ca8cab790338b2db069230510de05a19efe33faa6ae335d5","total":{"marks":11,"literal":"[Total: 11]","box":[0.8378794411357742,0.9057523524448651,0.9166306349998129,0.9188181959618436]}},
            {"size":[596,842,3,1788],"margin":"20b39186948836982cf417f5c4393b6a244008d24d104f7a8dd57f95062d0ae9","objects":"fd4ae71199d175339297598a65b8e28c13ad40e775f1f39d804342f865db72de"},
            {"size":[596,842,3,1788],"margin":"1f6b58dee0de7d025e001eeb168f23b193493abccab2f255505e7498d3e32930","objects":"fe116cf75e2129a25de313ca95c9bd7a59a00cf97936ac5b3d8fd3c0376ea4a5"},
            {"size":[596,842,3,1788],"margin":"d4887dceeadc63f14667e3595e476e758b009c6192a0535269b8fc233a6034ca","objects":"6e220f4a55c8671933da77f3f2e7f294b2e6f2e500c85603498846c559682102"},
            {"size":[596,842,3,1788],"margin":"76d86d2b1ddb719c522b7f926053f74e465eaccdba9ce1b2f47ddbabb3c8759f","tail":[696,"939882dee7e9767625ecc045cb3bc10efec077767b0d82320a0e2bc0048f26b5"],"objects":"8e80c330572de4b6ec8c017d786925245ad4a0b50fc04d8b5dfeeb79a9e432df","total":{"marks":9,"literal":"[Total: 9]","box":[0.846772042844275,0.81340189981935,0.9166183310870148,0.8264677433363284]}},
            {"size":[596,842,3,1788],"margin":"3520fb4ffbb3bc8a2a61613e6d5f7eb2161a7c17ce9c7f6c3840b3e6467c2a2b","objects":"14d22f3ac7cbc1babc637f5f160acfb5fa41ee645cd1a8cc2db9f62c37aabc4c"},
            {"size":[596,842,3,1788],"margin":"979f12a458c99d18ec9b529747187b9da35ccaf26ad5e4c00d77bed64ef372b1","tail":[319,"5554da5c0ef76967edba659033681268fe1a5b4c2e36e2e7e7adc55ed9e8cc42"],"objects":"d403f94143e9a8f052e53fadb56dfa85bec5f1230582751b4c017ab65517425f","total":{"marks":6,"literal":"[Total: 6]","box":[0.8467858847461729,0.3655833513732026,0.9166321729889126,0.37864919489018106]}},
            {"size":[596,842,3,1788],"margin":"54c7630275a79c956f0b0cafc13354f5b1eb8f43f485f891706ab8bbd5f416c6","tail":[371,"cd947c9e17d824b0397d1a18c800f6928c8403ff0e2cb4aeb27b24a5086b99d7"],"objects":"84e33a44625645b24914e947757b02e41c35ecc4409b449ebd31d9807dc9367b","total":{"marks":3,"literal":"[Total: 3]","box":[0.8467839878929498,0.42744576040840043,0.9166303274019929,0.44051160392537886]}}
        ]
    },
    "9702_s19_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2019/s/9702_s19_qp_22.pdf",
        "source_sha256": "30d62fa91f29c021b2aeb9804be215707d69b4e7f913d6f601bccec73ac48f4d",
        "pages": [
            {"size":[596,842,3,1788],"margin":"481cf271adaf634cbe1fa79398b3c411190be4266f9a843262c61dab8bc8899a","full":"1cf02052e09736c8b586a98ae0c8c3e8b326c60fed7c0fc8a54ba50b72c1a305","objects":"9a8ae1346eda531bfccac570a7b5fa9f16b20868bcd64ffc1cd733b3c98570a7"},
            {"size":[596,842,3,1788],"margin":"b73bfd929518e625080a9721931903e30ef47b04e8e05d3a1c1d58b5f3fac70a","full":"d761676fb8fb3daf63d80c80dc5f4375bf310db9ceec8497e042606a1b3e50f1","objects":"7fa7a149bfa351217643f8d7643cf3d46cd3dfa15b26a24f6231b18234aa349f"},
            {"size":[596,842,3,1788],"margin":"74cc71a9365b6183e5c46a1f1dcb071cf3e0c04b22bf80a87eb9a4d6308b6080","full":"25957390df1fb053ec0420993bdd9f5a9e52ad6c5cbc3b131165589164e0fe1f","objects":"c106e8af7201271f21992c179d337528d8f3cdcde7b32684bf9b4efe42d80996"},
            {"size":[596,842,3,1788],"margin":"7f3358d9ade681919dbe21c72db3aaa318d4024bfd4075df979541122f3e3f4d","full":"074513c73d591c54b04c12609367f843332de416f74df93f4e62d6b383cfefc6","objects":"9e1bad1242bb70a5b970b4c42c9a4aa0ebc5c811f34d72e2c9febe01162c1ee9"},
            {"size":[596,842,3,1788],"margin":"e431734d327302ebdfb5d985cc913d6fa1a3493f9c05c5ad27812caa647f0d36","tail":[629,"8a4cefba35968398d541e517dd43465861a423db2cfa4b166a3c822bd4a14ae5"],"objects":"f0b696b913b7389a24208a1c0a97c34c275d1c6c7b28832bbdfe6c97c928eb11","total":{"marks":4,"literal":"[Total: 4]","box":[0.8468268539266166,0.726027195656861,0.9166731433050049,0.7469717315210048]}},
            {"size":[596,842,3,1788],"margin":"00168a0d1a8a6f2005a6e9046351e7ab56deb5e951932bd6b8d3140f7be720d4","objects":"fc342763f6127e5027eb91afc8dc2bf0296554960640f765cc7e058e70753b76"},
            {"size":[596,842,3,1788],"margin":"af7148baf3cb6a70023f6396a2a7902001976b116baaf88002d96cba1dfe4eb7","objects":"379fea11de7617bbe6052e29f77d26096cf52e5dd1eaeed5ceaf456117d6b527"},
            {"size":[596,842,3,1788],"margin":"88ce785c9739ae517be9be4e1562334c61280f4510fff726da483f74a5f7d2ed","tail":[644,"086794064c9460fe5a5f9d10988a0eeb09d8fe3ed5095ffabc413d6d145f4e1e"],"objects":"f68be3748366d7b2a3a55c7349b23ea0f0c91590c21cbeb385a658b23d5085a6","total":{"marks":14,"literal":"[Total: 14]","box":[0.8365575030129185,0.7438449748091968,0.9166780648665919,0.7647895106733406]}},
            {"size":[596,842,3,1788],"margin":"b7e7d73b22e62c8945d235ce3524767a418d2c5ea2abdc4dfd795c3eafa7547e","full":"6ad8b4bab963120e1019800bbbd03c5344045ada4d459ca0590fad26c0b0276d","objects":"898a84e6f3c91b66de59d78675bbd1aea2454169d2fb7cfb076f10ac8ccd1bf2"},
            {"size":[596,842,3,1788],"margin":"01a7cbd3516dd5d52c8a03e128e8b6389bc8eb0a705f69b996cb8df2e6f39872","objects":"d1a6709bc83457c8b2d4cff692d2016e2642d9a28a04401f12c12a578e368b98"},
            {"size":[596,842,3,1788],"margin":"d2bef0c7f2c3e834ca4e63980d454e01ea78c4e0ea98641fae2da38ec9ad0c91","tail":[630,"ba3862d7aae0537c5f594f222e542bfc5d8ed318fb83645096aad07b0c0d20eb"],"objects":"12fd37572b1c6143894147376ba285cf79de1c41035cf9e006ed10de97d62733","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365311008856555,0.7271904950191851,0.9166517140055954,0.7481350308833289]}},
            {"size":[596,842,3,1788],"margin":"b9d5598dfd1be14297848ecebb100e202c39ec44b899a93741caecaafc309060","objects":"e9ede390f966a7027035bd9255e919cad56b9870013944e0b9012bb33d896673"},
            {"size":[596,842,3,1788],"margin":"ba9a9218c81b581dd25341ecb490b3807a2da429953512b2b9d0af7d993d156f","tail":[471,"214656c030e9b9a5ce8222db8be1ac0b1facd5cc492496fb74938a5ff0d41825"],"objects":"2eb1e4302bcc09b78ab425e2810425d4a2f8f0b1058fcf08e6439f578c56a33f","total":{"marks":11,"literal":"[Total: 11]","box":[0.837916007809698,0.537978940265165,0.916676629411129,0.5589234761293088]}},
            {"size":[596,842,3,1788],"margin":"1e6353dee716758e4b7da74a679727f18519fc9fed28fe05c7d5db6a1adbd938","objects":"390a8efdc4bbcd6b8b640eec2d69344894a0f5f3c7df60c87206fc6bf4671343"},
            {"size":[596,842,3,1788],"margin":"725cf2a3fb1145d6721aa237757c399b61670a2814eee22c46733cef534b9090","tail":[704,"cd5cd7a12a305c58b00032e13d9c190032c4a67b3812a206f4db5397ff8c0f3a"],"objects":"5d345327803aabdbbfffe2562f72594f3bafc0455e4b93579d388a17e180f3f9","total":{"marks":13,"literal":"[Total: 13]","box":[0.8365426357956248,0.8153306848444698,0.9166631976492982,0.8362752207086136]}},
            {"size":[596,842,3,1788],"margin":"d3330627414253c2e152f0238f8a7da0bb8f2d863935e764826e2c722212bc75","tail":[682,"85539454e8c3ac4ba70a313da01c34290af701e5c06eb8d750ae94f772776cb0"],"objects":"d534924311f8ef020ff3b67b9ef67313d0fb1304dd9861a527b0730a1bdb543b","total":{"marks":8,"literal":"[Total: 8]","box":[0.8468485395573588,0.7889741172779172,0.9166948802020137,0.809918653142061]}}
        ]
    },
    "9701_s19_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2019/s/9701_s19_qp_22.pdf",
        "source_sha256": "cc49218fcf765acb5c526754b5a85c3c86ab7f3840a5b137ccd52b4f1d888934",
        "pages": [
            {"size":[596,842,3,1788],"margin":"f51f7dcb781c31888e7b95fa186582d3bfbedd5352756f700a87d87d09dba3c4","full":"4a9d6932effdfb8741cd7351a0601b94dff97c0d65a00cd3e7557bc0dc49d36d","objects":"8364865b5bfa199ff4b1733ccaede60b19b3c30b4a249b28e36263ba1ac66365"},
            {"size":[596,842,3,1788],"margin":"a50ef60ccccf15467c8910080c48d76230eb6cdb018856885651c4be41968a0e","objects":"83c7af52c9dc9c4922dde7772d74fe83b20711fa6222395349367fe51d986a76"},
            {"size":[596,842,3,1788],"margin":"5130f94c021d644c91464d622271f7d6bdeb3434d3d90d47bc7c6fef4891a14d","tail":[783,"1c49f39983ab0e0ad617e41f171331fac6fd9de76437993e9aa20208ba221e41"],"objects":"b93518996a195695190e172de808c650748f19ed936527cff97159dfb4fbbad8","total":{"marks":10,"literal":"[Total: 10]","box":[0.8367066878485209,0.9122638402972525,0.9168272497021942,0.9296544625355402]}},
            {"size":[596,842,3,1788],"margin":"c2c2d2414fc67f54f2216188cea61ff41802f82553ca8050176df628d7e98df3","tail":[777,"1cc36c493b9bb2ea2952f642626f4c392923486ed08058e58d886d00cf74ddf5"],"objects":"d64fc70d89ee9a33129260f00e79952a9484a14d0249ecf7334397da8465df1e","total":{"marks":11,"literal":"[Total: 11]","box":[0.8379098045914478,0.9042971318573656,0.9166610444661039,0.9216877540956533]}},
            {"size":[596,842,3,1788],"margin":"abc99a2baafb81ca42e44dbcb9bd1b6f4c72dfcbe4b69a326922b6b7f2bd9e35","objects":"b23d6121ba00210483a54ab3e49df28ae7e1979a9b2b54c60f5ffa2e018cd111"},
            {"size":[596,842,3,1788],"margin":"7680484d3b0fefb42579208bb12d4f0d425b6a6eaddde831d7b579aa210deeb1","tail":[517,"16fb76d691532b872b998e7d0df7de184bef33db476e60a5e9e6f9f12073ca4e"],"objects":"956764f6582086dd07655a650ffc2bf213f585e0f9a41ef9aee0d02a67f26042","total":{"marks":13,"literal":"[Total: 13]","box":[0.8365937995296218,0.5963330550868574,0.9167143613832951,0.6137237135740347]}},
            {"size":[596,842,3,1788],"margin":"9c13dd8983f079f4e8f350f7f7ce0a1f5955163d28e20e10cdac8f6d0f023dd2","objects":"72ff2641161ec880d6c7a98427656400722d9f235b2f13b2883130255fd8e237"},
            {"size":[596,842,3,1788],"margin":"be2e19458395757c124f89a9cfd893cb9bb21b159799e8184cba9f71004cbef5","tail":[739,"e7aa48847a065b680898aa4a6794ea8ebdbe39e638685a67fb39e52259912148"],"objects":"adb537ff2f682fd39dac0053d48fdaadfc4df38d47560d81fd8fc79444f54959","total":{"marks":14,"literal":"[Total: 14]","box":[0.8365486852150753,0.859264991416988,0.9166692470687486,0.8766556136552757]}},
            {"size":[596,842,3,1788],"margin":"95558d437bd16cb3802c5e9fbe7a7cc3d10aaefffdc9e2b70d36393caab84bb9","objects":"1480d25c57a31c8983fc140c22c3b6932efd4eeb64f15b63c10f3215132a1194"},
            {"size":[596,842,3,1788],"margin":"6d13d2107ed8ff6acf2ad194529c60bfc07466023b079f143e4cc73b8fc0f108","tail":[615,"94d16fdc9cec2a1607b9bac8f835ecb5dd1d41454ab5fdf08d9def1aed03ce40"],"objects":"61530d7f9e5b71e4a432e24955fd273b4f21563188a75a33b6e1579d7f0a0f7c","total":{"marks":12,"literal":"[Total: 12]","box":[0.8365673461360923,0.7124237848973497,0.9166879079897656,0.7298144071356374]}},
            {"size":[596,842,3,1788],"margin":"d9f950be0835ae3d123a835a48439cf1c4d83616c08465946e7ef531ef9a1cc9","full":"66ab5362919be43bdc3f36cb2a33ea4e838d78a6cf86d52844d4e3adbc319d2a","objects":"6ccc9a68c178e50941617c0bde5dad76f22afcfb9e7bc5b7b568ac268c593248"},
            {"size":[596,842,3,1788],"margin":"d94f0f491171f687408eca645eba7ee46035a0e4ad3b3c95746cbec598e5accc","full":"844d632755cb722dcacb6549f3466b449c6b0e43c90835cc1ff588849a34f323","objects":"dc6801eb5a0efba079a9fa320852f384f651c77799314cffd2291ed433480eab"}
        ]
    },
    "9701_w19_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2019/w/9701_w19_qp_22.pdf",
        "source_sha256": "9f565167380a5825c5b5eebf2464b2cab0c2a49a90503a8c6871b325f3473e6d",
        "pages": [
            {"size":[596,842,3,1788],"margin":"bf80ac5dcd709ce9ea11974f4096efc5b8b78e2e3a9654bd09321e2afa60dbd7","full":"9f77efe53e670ea6f1e97e86a275610e6b776d6fcfbf57a75eff63b3eab64430","objects":"508ed72aec0caaca0c4d8b6e9057322fd3942de309b603868332e0049511e83b"},
            {"size":[596,842,3,1788],"margin":"c4ff92b2de881df27842eeb47aeae13eef31db15f829b53e8ef7d5118a161c1d","objects":"5748f181c89c56f2b853f2de34f0de5838289bd8b22d215de12da6e204c63914"},
            {"size":[596,842,3,1788],"margin":"98a730a00292038364c0ee26928ca4bf8688aeac5b329537d13623b4be9dd41e","objects":"73d987abe042125f2c27170167022f6000ca968962a9a9675745cab846a5cfe1"},
            {"size":[596,842,3,1788],"margin":"bb2114803394c76e2944806fa7a23e3df168f63b601f2cabf243d02ace1c1c16","objects":"4de08b61c9f7b7f4fa5504be57c48492e2e8ef4fb12fa63f53fc75bd64c55aa2"},
            {"size":[596,842,3,1788],"margin":"2fbd387e19b88a5a66b3f4442116e02d79923a81b76c9944b72acca1b1d5a51d","tail":[673,"964a26c593d480ca291373c0603bc1f4fe4c6e1f6c229bd7bc15fe73b4886989"],"objects":"6d53c890022003327fb8877ac7f6ffbe7b3743d879d7757bf0686153d0063e82","total":{"marks":19,"literal":"[Total: 19]","box":[0.8367133524631698,0.7807727335273084,0.9168339143168431,0.7981633557655962]}},
            {"size":[596,842,3,1788],"margin":"0cca95cd3a99df4282ef11e716337bdbedc85bccdd585f84c98908161fe8ef99","objects":"2729efd190a82bd6aead8d9222dc041fffd7d5bc71c1075667bf30e1b6da9170"},
            {"size":[596,842,3,1788],"margin":"152dcaa918e04df71de1ba5e1985eea33a75d051efc6b71b423c1fc74e54cb50","tail":[672,"0c403e9bb1f200bc048bcf950c2ba647808df974fe212d94cc1652152d7b3f7a"],"objects":"3ab5f82819dd31f912c2905ffb6834b211cc87265172382cc08584324a8e5616","total":{"marks":11,"literal":"[Total: 11]","box":[0.838082469377121,0.780202103508559,0.9168337092517771,0.7975927257468467]}},
            {"size":[596,842,3,1788],"margin":"a309ec18cf5db37494b2139496d6b202a9d36e80154b4e322980926b4ac6cd8c","objects":"37a79c78072a6e343a109c4f6d05a0dd3e47ebe790665a8e2628533d8e9ea6eb"},
            {"size":[596,842,3,1788],"margin":"f9dfd46a40d9bb3fa427a8c9c667b328bb874988804f03143b8162185180818b","tail":[542,"5a150f3c7cf82a2bab82c67357a887ff335465e4b5eb28ff8f0a6773c2f46449"],"objects":"f48365e4e46d319f7546509f8794ccec92858e5fc47711d6feada6452612e1b0","total":{"marks":13,"literal":"[Total: 13]","box":[0.8367050473279919,0.6257923463514695,0.9168256091816653,0.6431829685897572]}},
            {"size":[596,842,3,1788],"margin":"afb1e4d2b10c796e7228ca783af5db95d86ffa98a47b1b0f54a5c2ea7d388d8f","objects":"d1010ebde5fa709376624b1bd7229e90fe33ac0ed286ea448d7e06037c059ab0"},
            {"size":[596,842,3,1788],"margin":"1259f819c7866fd4730589e4a21493e951a983667e76e0a306d77a81eb266ca3","objects":"dacae092b63784a76013cf121433aa7b33c5cfa4ebb46453314ad44b4b589723"},
            {"size":[596,842,3,1788],"margin":"68ce7b5adb1cc4371bea3f28266a81c3a858e829630358e0e1fb6596520ffb02","objects":"d788c0cfc36b505ec557b1e0c88214d0ff8ce0a2b8e2adbb85360651748af8d0"},
            {"size":[596,842,3,1788],"margin":"90f770052251a06248cec4c4962df4d54ecaf9df7425abfa9cf83328cb1d4b45","tail":[580,"b9b65ef0a35343b564c3c0a1fabb59ab9b893f616a7193213a1bc8c558aada52"],"objects":"9b55a8fc0e042e091b2cc4948669e475421a5dcad2048b4a5985f882cc4d74ea","total":{"marks":17,"literal":"[Total: 17]","box":[0.8366902826432313,0.6706836961049698,0.9168108444969046,0.6880743183432576]}},
            {"size":[596,842,3,1788],"margin":"46e49df31eee87e00fa7caf83936c04f830715121fcfc9bd5be70b72f38ecf1e","full":"7b233cb3709f061c976a4e68eca15b703927ad3013b24463adefc3ac7cd3c0eb","objects":"390ed3f03ce111cb66668ff78f86ee5f1e5667ab5334d99d300a0b79f72516ee"},
            {"size":[596,842,3,1788],"margin":"95b8cf7115f2521ce67972b89fc856e22aab1868ee77b4aafb7e0d35c5850bb2","full":"bd9cc7caaecc7dd68bfa73ed8d9d297225ad510984e06eee9f932495e217223c","objects":"e23873e310ca663eaf53337d8980f89a5a62b3bab2e4ca3fe6cd4d6ae9785de0"},
            {"size":[596,842,3,1788],"margin":"82429f0046ca91744efb25704cec9243de22d3c58d080d01855b1fdc5153d5ac","full":"9051401bca97a58b508b67dd3df2378fad36c9c97dd8e5dce61dacaebb36937d","objects":"5e024a6f4453fffc96745c126015adb36c0ff0dc16e795dddb70dd6efbe9bb12"}
        ]
    },
    "9701_s20_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2020/s/9701_s20_qp_22.pdf",
        "source_sha256": "630b2d0c535a722c20dd7198a1c10d2811164ae01d5764b0deed2d451e8407ea",
        "pages": [
            {"size":[596,842,3,1788],"margin":"beeac3025c8676f5cdcc61022a799d2ae86685adc187311e9091220547a8a79a","full":"05d1bfb8984d7e01b65b470a551a23b2b45431e0749de1d9ed6d310aa60008be","objects":"a27cc8e935351285097820ab5c03dc3b76b8cd9f4d7d2b05d25a74452a0a3b76"},
            {"size":[596,842,3,1788],"margin":"4d20f5f4ec092e417894cd285f3104ffe0d27c72a85be1f260f2c2643b963f6a","objects":"d3abed81e8ea575c65c59f704fbd6184569d6111de82276b89b8f3a9fa4f6a03"},
            {"size":[596,842,3,1788],"margin":"307dd16507bd911ea6aaad89a189b70dfa7629d49932a2fe476a14355c0e73cb","tail":[439,"5673f8864c4915e7e56a8a070f9cc907b312b180e7948eeb078b105ad3d30bef"],"objects":"232b9896e2b792a455605091bcbf037f5a6bcfe70a0bbd0dba0de24868bdb7ec","total":{"marks":12,"literal":"[Total: 12]","box":[0.836711917007707,0.5028218673020952,0.9168324788613803,0.5202125257892725]}},
            {"size":[596,842,3,1788],"margin":"6b3bc43b956722b2d34cc3b6949585a7453e7b77a2dbbe4793d6217e41caf302","objects":"29390fd2ba0981112912c2520f712d7f4b3ced50cce3d14feeb58035d11b49c4"},
            {"size":[596,842,3,1788],"margin":"9fb45800620dedc62266b4eb457676fb39475cf708c0a6b9b3655dec37ceb024","tail":[582,"2df09c4cf5369e0cd61304945818e68aa1af90a06ac29cf3c050c6b48989a30a"],"objects":"970fa204c216e37ac1ec00f58dd71c0f9ce5ce8c3e68d24a9a2a82583889ae28","total":{"marks":12,"literal":"[Total: 12]","box":[0.8367258614322032,0.6726766600505194,0.9168464232858765,0.6900672822888071]}},
            {"size":[596,842,3,1788],"margin":"e5d51845b6d5269cae80d1a347b232172e15e5bd96283a38e0f9b04b55e0c3c8","objects":"a64e5b5035dc7a38ab09f7bdad8570409645b698b2465a7b9d610a9e85c2a29d"},
            {"size":[596,842,3,1788],"margin":"dadc405a6994e8335611e9290e7ea66acbff831d16061332b5cbe881ab5a5c01","tail":[775,"13bb8f4223f1a2ace3050b4b663236e6d05c37ca01a1ac39cb4d222579ef688c"],"objects":"48ff9f4da6c29fefd95c9cd9369c16edf4da50c89892342cae192b2a4e17d393","total":{"marks":12,"literal":"[Total: 12]","box":[0.8367074055762523,0.9026612919713205,0.9168279674299257,0.9200519142096082]}},
            {"size":[596,842,3,1788],"margin":"0d692cc6c6cc42ba31137587b0502335dad23eb6bf8450e54b6f5654600ec307","objects":"27a0d5b1fedea5ab080f43096b120225d9a3f687d64a43414816a83fc3471c9b"},
            {"size":[596,842,3,1788],"margin":"24d8c833aec2ea0e93d109fe7a8a7c369cdf3ba0f839e953c8987b698a46cdc6","tail":[399,"76e7d7056f26eb44e23aa49ff93cf599c498814b8075078a23118a8a7dd235ed"],"objects":"0c42f10f65bd6a825276fee615a129e14d4d8b6db0c3188097681c8ba7672be2","total":{"marks":12,"literal":"[Total: 12]","box":[0.8367604148958444,0.455963906545723,0.9168809767495177,0.47335456503290024]}},
            {"size":[596,842,3,1788],"margin":"21d84037f1baa3b12ae91d55894813ce96cb0067236d777070eb2a97db38cad4","objects":"d51ac3d9b24ea20e908b8037c1c7a6a0224ceedd248fa7bbff639c8c1b70e6a4"},
            {"size":[596,842,3,1788],"margin":"eb59fd240ed2da120e256772d65dd6152f79d4e8bd6bb24f8c1ddb9cf1861c48","tail":[477,"53f39868d7dc2ba873a76fcfe898ca0bce94d25eaa465b70951b6aad674c3a29"],"objects":"71407f99aef351f76a8133bedefdfd160ac08fdec98a032ae2e907af9003da50","total":{"marks":12,"literal":"[Total: 12]","box":[0.8367073543099858,0.5486570293919045,0.9168279674299257,0.5660476878790818]}},
            {"size":[596,842,3,1788],"margin":"92c17d9359fcb9ce3af242624cce5497e3550c2a767b2abafea488b942cf7fc8","full":"735e4fdc7612c50b907fc83809c640454058102e23e4b00bf9b5eb86f48a3f92","objects":"c168d0a60ef7c133e97486cf3b041b83a88aaecc9f0c8bf5b6ff4ee31ced9782"}
        ]
    },
    "9701_w20_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2020/w/9701_w20_qp_22.pdf",
        "source_sha256": "4c224519910c0384a85e1eadcfd898643a1074fac938696fc9003e29bed40e5e",
        "pages": [
            {"size":[596,842,3,1788],"margin":"90faadfe8e2b14f374d758a88df58247aa3284b32359fe688df4b3c3332da409","full":"0c46b374921912c443f44358d1806549d022c3ae5e6dab057523a471746d3919","objects":"5dcc840ba54ca153a4a7a2e4462dd20b64aa5fa050b10feb0ae3350651c30702"},
            {"size":[596,842,3,1788],"margin":"11d4147a8aa3e917463102f87a305ac76a2e4c0caee8959f4292154f522e29e6","objects":"ed800e9c4954165538dca7441858a217ed92a064eae7504fb644eaf9d40f674e"},
            {"size":[596,842,3,1788],"margin":"6df13bd5f9b51e76776e264e30e585af7e5a68ecd0843de570e4c4a1976a64ac","tail":[696,"bb11fe6c82203664b9ff16812403223e6b424f82d972af15aed4ed0d7bb6de04"],"objects":"cef4dbc74ec06d83d3bcc55472f6f29abfa8012074b839e4c96c5ad9920b1377","total":{"marks":12,"literal":"[Total: 12]","box":[0.8366865914720412,0.8077245078597017,0.9168071533257145,0.8255593964878886]}},
            {"size":[596,842,3,1788],"margin":"cdc3ea9a2590c79a904a6f3030c982b4c06f7bcaf2bbeb647ac932a21b13ae7b","objects":"4d71051041472411d4d6b460555c56e2b6f4f69cbf9c3abe2bd2126dad4105d0"},
            {"size":[596,842,3,1788],"margin":"4773102292a88f9f4bf93466d9bf5163904d7bf01c690d48d434c97aba5618a0","tail":[582,"98b3b2be9b14b16fc18e1d346c4aafe0fa4cd55db4746e2a316f2d710a53f2ca"],"objects":"4dd774fcd7c3d975f896006c1707cbd51e44fa3fd2bef436c68f0220e5708048","total":{"marks":14,"literal":"[Total: 14]","box":[0.8367097638245127,0.6722335536250847,0.916830325678186,0.6900684422532716]}},
            {"size":[596,842,3,1788],"margin":"3113b3ae4ff62082d00a5568f10dff5da8c1ad44e07f8909d23e267cb631d441","objects":"45de4138eb14e135d5e757ec7d6bb6fa8253fcba4c4dbf4da030479a37f96fca"},
            {"size":[596,842,3,1788],"margin":"c69a24a0c079ff64a4b0b165ef833f143066a399c8f43c9b8796c69a989e400c","objects":"bb59f97673fd8bd250e7f7e8c73937809df099fd67fe8a80b63675958e8ad639"},
            {"size":[596,842,3,1788],"margin":"bd344d9481f5b8c4ca99bf74628fe18c3cbb3f6866b87ee3be37958a88034ebf","tail":[737,"e9f0b971ae1638bd1ecb8739b6a317459746ae773cf1a5dbcb0d34d11a594873"],"objects":"314486d53005eb06885de85d7af282b4c64f08c6a0d0688d4577b902923b824c","total":{"marks":17,"literal":"[Total: 17]","box":[0.8365542732381271,0.8569591270571426,0.9166748863580669,0.8747940156853294]}},
            {"size":[596,842,3,1788],"margin":"e61e082c129c99fe200b6a4c4a6fd9e56836ad6130f5d5467b3c9a2392829190","objects":"c99775ef481aacbe9fadede1cb5206ee5788b24146e7db670b6bf777bb6dbf09"},
            {"size":[596,842,3,1788],"margin":"2d54f893b62c695e6638cc167e075f02a28d721c32e0da19b34d69a69ed5a589","objects":"09797561312dbc42a76445d4c8a4e5ae7bcadc6ab4c48c57ad3b49865b7bef85"},
            {"size":[596,842,3,1788],"margin":"dec89524b633195c92ba9ee593e81e8139d91acb9495e753e77d1c352ac37cc4","objects":"9b656dfbe755cd4da21b4356f8f3727056b5628d77702209b379fc20c89cb2e1"},
            {"size":[596,842,3,1788],"margin":"603ba7cc7b4896c4057dbee8a035f3af6569025daf494a65a924afdfe9c3b267","objects":"bdc8badf06509c8d9c9516a265749f7b468b1bc641e7eb2585624085b2693ba9"},
            {"size":[596,842,3,1788],"margin":"cf27a8971e2992f75e3903e63562c40bf798411272e790733c5998ae272e05af","tail":[401,"cb9e74ba53b0bbf57bbfcfa3fd91299136ebab6d4d817f80083d3eb718d03bff"],"objects":"00cfb9e67d3c85794d27cdfe575a78c941a707eaa1f938e291eb5a34f37b2aba","total":{"marks":17,"literal":"[Total: 17]","box":[0.8367398058566993,0.457524892474919,0.9168603677103727,0.4753597811031059]}},
            {"size":[596,842,3,1788],"margin":"7075da9f13a368f20bff1a28bce149432e47da54e1dd71e450f3c234ff712d88","full":"398baa24a839b6c1580a4b89da6188e488539e2f6ef1e2a7b4a5615e588c6a92","objects":"04b0b5d9657e58b5045dfaf59eed48d576393c5d8d26c5bbaf06a46113685b4b"},
            {"size":[596,842,3,1788],"margin":"61a13e29aace47c878c79fec034dca15488eb00d7dad2098631805c84e4eaeaf","full":"26ca4a3cb6f33cba228ca0342be0829a73cf86c7cfb48197e67e6386882c1f96","objects":"e5bac43868fb0ac6ca136af047f1162627b991f5438d878a46cd481ec3408b46"},
            {"size":[596,842,3,1788],"margin":"6025dcbc308dbd181dfcee135126f8008042b1ef18b78e946328bfcfa34f4ff5","full":"ebe2dfd6f83ecb6736aa40aa93bd2da61b5759697924d0e3dfdcb3344432253c","objects":"a82026ff37caead5f949b7a0652063a3280de7a676b404fc3f1223311876e85e"}
        ]
    },
    "9701_w21_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2021/w/9701_w21_qp_22.pdf",
        "source_sha256": "69e73c0843ae5f54de89a2d30527ef6b07ce307b1b27fb676dcfdaeccd97b792",
        "pages": [
            {"size":[596,842,3,1788],"margin":"16c6b2facfbebfbaf96b8d5899f89bb43fe428246332982730058bf5e8842af0","full":"6460140c1ee7a06a1d95ebea0bb753a7feeaaa6a76d0dba2006c5f97fe53c902","objects":"f7e91fb861132dc46bd5e02227c7f3a1f2a30477dda5dc6a444a18b0ba8ded63"},
            {"size":[596,842,3,1788],"margin":"08fb8b71946199f2fb020219acd8a4a7fe4d043544036c89b99b3148f6a12fe1","objects":"a4b225869eb1d7f6fdc8091cdfacd0183b361253b8515497b96d9702be306a31"},
            {"size":[596,842,3,1788],"margin":"dc454f815252e3146805c63e855fad6f8b3bffee6e5522fa72eb83ca16fd3a31","objects":"b134ceb8837cc3a7b13f009d665aa73b652af9f70f089fbdae6bcae3325a1ddb"},
            {"size":[596,842,3,1788],"margin":"536e1e972b6610a448e23810bc4981a0ea85a03478ed47c0ac94d5604e6ac3ad","objects":"36ab8a7af596a868b0b6a763ea08ebc91c86923325e97ab85d9940b2ae23caf8"},
            {"size":[596,842,3,1788],"margin":"584b4af0d5ba7a9feed0fd0e52383ed026f6e9062b1c7a42bc1af418152ffabd","objects":"55d8b6929b7a40cb4202d2432cbd2d4e80a77d86ea5d6ff34029531883a7ab34"},
            {"size":[596,842,3,1788],"margin":"f67618bdda3a4681a163befcdf5aa536fe84da508f702e19219bf958bbffef02","tail":[470,"d9048e00606d71366b95b8db20cb425f34d75b29c0d260b3ac4cf269e2251e1c"],"objects":"1e86a6eb724ea31f2d9025daeb75de5647412fe78eb70b31397316cd07531dbb","total":{"marks":26,"literal":"[Total: 26]","box":[0.8365486339488087,0.5393459946354543,0.9166692470687486,0.5571808832636412]}},
            {"size":[596,842,3,1788],"margin":"d55503688f143869bc59e4b8f7276aa6d19942ab3f19f4f3c23725cf8b3c5d14","objects":"624860c40417f9b6187373cab7e3aa5e008d5e8afa3f837f1bb6b668db8818f4"},
            {"size":[596,842,3,1788],"margin":"4cab5b86e3f2ae7a3ee08606e6f9c7adbd418bf88cb4550391cfee4cf0385aaa","objects":"585b8ee5c686ee32e2131c586cce3c497967e1c014fe0732545a30bc27ca4e7b"},
            {"size":[596,842,3,1788],"margin":"813b35eb4165a76d6efba5b57523feb8b894f4af1dbe9bad67bc245a666c970b","tail":[477,"9902238794f0e314783e754c665dff125770d3c6d79e062d1584b57f15be533f"],"objects":"c68593c97eb39222efbe0598667e1f2ec96b237ab65035e1e5bb2cbee2cd7768","total":{"marks":17,"literal":"[Total: 17]","box":[0.8367040220026614,0.5481289918183356,0.9168245838563347,0.5659638804465226]}},
            {"size":[596,842,3,1788],"margin":"69baffdbfb217f56227a163e45fd056163aa611a37265b08d58a642da7c23014","objects":"846a6a28ae420a070303ae2004ce9a17744e62a0e586167999f71d706e9c9600"},
            {"size":[596,842,3,1788],"margin":"d0978597c7ae1dd155a603622591ede8f8e6fb6d0c67a44d2cb18840c6f7bc00","objects":"e0d36b8e38d8318f949f17cf47af4af896c95a90dfee4be6d77b9fd5743a51e2"},
            {"size":[596,842,3,1788],"margin":"fe120ae06de2d687d6b7cac1093cf3cfcb46e58a1349aecf1dc34e734018063c","tail":[686,"c163b770bc8a80797b30ae63f1694e2111aea48fbfcaca0790fb4d77b01ca90d"],"objects":"a81efa47126f40cb593900e206c33404a4ad757d34c92879c39ce57bd1963cf1","total":{"marks":17,"literal":"[Total: 17]","box":[0.8365671410710261,0.7963061076623917,0.9166877029246995,0.8141409962905787]}}
        ]
    },
    "9701_s22_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2022/s/9701_s22_qp_22.pdf",
        "source_sha256": "b448d04ca4638853cc80f63e6d594cc185004f0ff66abece3ff6376d90613193",
        "pages": [
            {"size":[596,842,3,1788],"margin":"c08c4341fc80530d79a0a5ed53adaf659ce727e1b7244f5228a8cb2ac02b4061","full":"751050242e759a071f35d3b57fa00d0ee1218829749ee93800090c2deccf530d","objects":"c8343dc2ff56ca63da68f6f3c65482cfc8572aca0287a0553b685621950bb6fd"},
            {"size":[596,842,3,1788],"margin":"5e392ee9c088d8ded54df6978c989e849f0ba58a219c1d427641d6ff1d61d423","tail":[747,"1e71a78bf82923b55fd1cf9123a1b8672d1600f3888d972e1f42defcb572625f"],"objects":"9fbcc64150681100022d11a320c4534af265222da6738542e0f6413f2355a873","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468270077254162,0.8690252949100904,0.9166733483700711,0.8868601835382773]}},
            {"size":[596,842,3,1788],"margin":"80655e20e6030a495d6ea5a9e660337c333d40c57bd9a0f11b367ab215fda6fa","objects":"3e09f16b36886a0964efdce5d499c3dd12345307f3c5170c63e77d67af372e38"},
            {"size":[596,842,3,1788],"margin":"01ef946c42e3b3479bf034a6416a5ecb97fc70781ca01cca58e2d9710da962a0","objects":"b7a776ea78c9981e75049623066ba3abaf05e13ef5e04c58cb856518aa408813"},
            {"size":[596,842,3,1788],"margin":"24e49cbe595057bd712f3617f05cfe45ece7f2987e9d043291090057ef2a911f","tail":[534,"7f8e256dbb879290d44b711a8da6a5f2aaf4aa4350f73b70f9d4f0a37af5d0d8"],"objects":"6c52daa4c3fe193458b08036bed8d342886704f61a0309bd9a23b0ade97b7a89","total":{"marks":11,"literal":"[Total: 11]","box":[0.8380816491168566,0.6162813627204531,0.9168328889915126,0.6341162513486399]}},
            {"size":[596,842,3,1788],"margin":"4a714880258100770edaa3ef14e5a01ada8a92b9d30477632c29cd7454009e5f","objects":"ffeffea598dc550cb99d59421bb06f051af105a971a2416d5dcdea743052b5d4"},
            {"size":[596,842,3,1788],"margin":"e53b6fe1fca66ce03007b17e6f9c73e896ddbf1dc08455ed2dc7d8e636b72f42","tail":[648,"64aad5b356290d0e1978f5102f430dcd887082ff3cec1b95bd03c47b6fbab425"],"objects":"c7a2b12080aa41c405e04631e049d00e0550d6890f3e4a454705f6eaa524a80d","total":{"marks":12,"literal":"[Total: 12]","box":[0.8367098663570458,0.7516525506241116,0.9168304282107191,0.7694874392522985]}},
            {"size":[596,842,3,1788],"margin":"9d624eb6394f155c94fe24d4f178da7bec3f99fdb3dd2c19c8087e661bddf6ee","objects":"bd4d82c3cffb2c265bcab7987d4e09e154c53a7bdb3cb9137d5812f4e4e4b066"},
            {"size":[596,842,3,1788],"margin":"26d011d11ae245645faa319dc19135697046c0e50bcbb5ac1f4888fcd259e993","tail":[556,"50627d6643ef211ad7a5b82d6e7331bbfdd31bf4b6d90c17a7e37f33680197d3"],"objects":"07b6638e28aae9f58e993b871090f7889b68a6f84de99da536213ffa7c49bed6","total":{"marks":8,"literal":"[Total: 8]","box":[0.8470123352789223,0.641613029184851,0.9168586246573106,0.6594479178130378]}},
            {"size":[596,842,3,1788],"margin":"8bb9a464b00ffa6246f951a69538c94c1c156bde0c04c0dee89682b7a905d9a3","objects":"0ca812c4ad031b9f504e504eeb054ee9e1cef1d197239e11101b5f57d12efc6f"},
            {"size":[596,842,3,1788],"margin":"f124b6eb762030925dd83b1b9bf45edb91126dbe606e405dbfbb4936a06f9ec6","tail":[663,"832a2679c2e88111d765a5748198121293a1d4a011ae6aa753d8d915668a3141"],"objects":"619bded2179044021ade25c2657a0bd75a11667013ca606aed2463283d00ce69","total":{"marks":13,"literal":"[Total: 13]","box":[0.8367197094802196,0.7688258245208658,0.9168402713338929,0.7866607131490527]}},
            {"size":[596,842,3,1788],"margin":"89d5d32622fec8aad7c8bcd7480077378dfe1fb1bf5612afd2b6c571627dd811","objects":"b10d09e7df8c4a7d07991dba5922d372eeac41924c417aa2ea68a8a2dce94b60"},
            {"size":[596,842,3,1788],"margin":"a61aecab3a4721e4369fa031c8c21997042448a99f118c16e388c7439522a832","tail":[663,"5e664079702f8f72609dba90a8f30f2bd4cdd360d412623592b1e4243e981926"],"objects":"3c6cb38c5c3457e8dd33e8d82980555c2be844956e105a33acba00baa4605a70","total":{"marks":7,"literal":"[Total: 7]","box":[0.8468377736413876,0.769253416421588,0.9166841142860424,0.7870883050497748]}},
            {"size":[596,842,3,1788],"margin":"876d9acc2ff3cda252f4ac1ea3fbd752d1601f12f6ad3b4aed77aba4d23b6b47","full":"e75a1e40a19c49ca1529d864ee827a255f2631d908d6501ea7137e760bdc4650","objects":"ecddd3a34b6b0b2fa9169a1f002de69e6b7618f11c703b45bff9f3475b09d017"},
            {"size":[596,842,3,1788],"margin":"46e237a23349010e024c2747588bac17a6b5f34bbc991a040adebf73d4b23f59","full":"2fac370d9e4d16e41f8783fd7b3c51444281ec5c7094a88030baf8a1c6e47d5c","objects":"06e9ae47bde5d87ac8b1e5d4dd3ebb1104aab7796867767a5c802e81d08eb1b1"},
            {"size":[596,842,3,1788],"margin":"3c4b600a5a5384e2875fdca6be7ed6bd2e7b3f175448169d2e6432ef2c0af2af","full":"349b2acc1a1d82dc1c79638224113769da760fab6b8848329abc1b69cdeb341c","objects":"f1a3c7c69ec17b6a1c9aa7cd85096fe853e46f2776e316fa64810f031e3f4672"}
        ]
    },
    "9701_w22_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2022/w/9701_w22_qp_22.pdf",
        "source_sha256": "ab053120a1017025f0d45a0765a226d8fcde295b758ba24ee1caf916b110c290",
        "pages": [
            {"size":[596,842,3,1788],"margin":"5f6c4495035ccb5ba61292c655893935eb0cef3057f3cfaf8b5c588efadfe721","full":"a2135ff472602d4ac5a67f9bfb9f8df7071274f578c1c87a5f2bca919014efd4","objects":"f37362ce0c6fc2185561d222e15ba97e9b24dd15e55a943122bb0ac829467047"},
            {"size":[596,842,3,1788],"margin":"81177b7a0da65cca66d6ab5a573776bb5d5ab6040aa7ba31676b55c1ccb62235","objects":"7acac55eaf03294a2ae15ac4234d68c20c50be8b9ae8141bf39fac14bc08a680"},
            {"size":[596,842,3,1788],"margin":"52b6216e588e3bbd11ccc4831558b2a58c0ac4af7606571ba040e961488b9e02","objects":"ddaf9cc9b45b937c5742f50fa6a3505859b0f38cf2e1a5a2743b66bf62179bc8"},
            {"size":[596,842,3,1788],"margin":"1bcd09da1117a51c110bf730fcd895bfb5e6606859af01a05321ecad7954bf20","tail":[651,"7ae42fc08eb380c42da928b8190b61c6fb663e7ca016fb8496fc35f157db74b7"],"objects":"b7ebbab2ed6b3d89f79f86cb18ed8bc4f41b9b5ae4419f8dee1efdf3a59fc9ca","total":{"marks":17,"literal":"[Total: 17]","box":[0.8365486339488087,0.7542742878071931,0.9166692470687486,0.7721091764353799]}},
            {"size":[596,842,3,1788],"margin":"744707579897f7b3becaf84a1a592f3c5825dd7ae272d9080240af675e3d360f","objects":"f665eaffd5feedbcc2cc5c61174732d8bb98f81f7c722b7aae16a3baa6b7f757"},
            {"size":[596,842,3,1788],"margin":"4071a9b95a84b1d10e5f85373e1a12b147585b465fca8e2f2a3d46bba0353bd7","objects":"6e6220ed9e11176922c1e9b8655e441256507b81b5d51cfb572c1653687a3dd0"},
            {"size":[596,842,3,1788],"margin":"7ffabec53be90d94d295d50cba61d3b9e3962670dc733e282912b9ba6bae4d39","tail":[750,"9b5504f53546a9faa5ec15c486a891e16593309fcdd7b4705e8888b3029c047e"],"objects":"743d5435f0544a0b1cb6765a65f5373d166fb8db8369cd91808bb74893fb6cd0","total":{"marks":21,"literal":"[Total: 21]","box":[0.8367096612919797,0.8724112311819328,0.916830223145653,0.8902461198101196]}},
            {"size":[596,842,3,1788],"margin":"d4403791ba9c99dcaf090f7fa3fa21cb30285de7fa690a8b918b7b05b13eb728","objects":"e989ca44f1a1e1af771f9247be52fe7b49ce9f888cb1481f0179df6bde060df4"},
            {"size":[596,842,3,1788],"margin":"ecbbc9cd208d9a5716f8bc5d56c08b3305f577460e1ad878a920312a4bae02b7","objects":"df598ca06ad11eab43aa98504591377147afd30606071b91de8341d9d04edf40"},
            {"size":[596,842,3,1788],"margin":"980e90367709051a9d28a3fc40c0dacdedbd773b183607f90e45f7c1c5ad5bb1","objects":"758aa437520b081c623543494355588392dffe6015b15fe8aac8ee2f56c9a846"},
            {"size":[596,842,3,1788],"margin":"2a940f31ce9ac1648b413d4a90d648f9b0e5945d5a3109d6e84724de08149589","objects":"a512a4f285e2b5979e661a2508b845250840bf33c7dce5041ba4f98912756211"},
            {"size":[596,842,3,1788],"margin":"0d2aa108bd2808adfd084c8e89b50802b1125a2f4c7c3f50975cff6796a7feb6","tail":[618,"b6b77c6b97680b94adfe829b297c657e917ef558cfbc4433d7ae06e643d554e5"],"objects":"52eb55ae1dc239529138162de1c292cccaf14c0dccaa28b3a8fb096db87b5101","total":{"marks":22,"literal":"[Total: 22]","box":[0.8365485826825423,0.7156001300900147,0.9166691445362156,0.7334350187182016]}},
            {"size":[596,842,3,1788],"margin":"e3ca2de4c03d62b33e0a155806b606735cceb1d20a68ecbe9a044641679560c1","full":"a0ce1bbe5eeb7176c3d9d2f07c4d636838d4202fb0b55dd7e95323cedec7f682","objects":"abdfdc210fe07b0884e2c025fc845795b03d04a2eacd650b32c0a9681c7b73f3"},
            {"size":[596,842,3,1788],"margin":"340497835b2ff54fb7da7ddf6f681a884a97a8309345d560a2a8e4cf2731022a","full":"f38df49b8a97f7218df305987ce6b3a55fb7cf8dcefe2ede7b6e2146470aff27","objects":"e280694be11591f7983b7dd838c27eab176a6895147cf2f9d8a67f0443c08dc6"},
            {"size":[596,842,3,1788],"margin":"0095989c28ab046bb8fe7b400f4cb7660f26ee4baf03bd16a7defdb6e7eed4fa","full":"1eed53abac8ef35d3931cd54325e31b2e9ac767b3b2fbfd2e5c49020207a4b6e","objects":"f8205dcdc9613e8896faa609606b2d1acf1a2fef4c645c2b9c8b6adec862834e"},
            {"size":[596,842,3,1788],"margin":"029f8729f97e6d92da817dcbbdcc223383a7788c2962b81e02b09ee0e44253c3","full":"1319beaef651d810bd38f64890de164d68aafc236b5d7f205d9d5455f081f363","objects":"ad04ef61a188acfc31b36c12f5ed8d02bb0f2d242df3aa31e63d47d11eff7e38"}
        ]
    },
    "9701_s23_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2023/s/9701_s23_qp_22.pdf",
        "source_sha256": "c1a1c180a1718523abd06f9162af5935e68f0ab790a0d247bf49f2f351786a6d",
        "pages": [
            {"size":[596,842,3,1788],"margin":"018adeedbbf4ce6f7830be21c8f6f556a0983b0842bd4ac21c90f72da522b47a","full":"7c3b02cb744b8c6e9892b409ba72f10fd48aed04a0f51a10383754063bdf6d74","objects":"99c3b006cd157311953ae80c82cb429b07ea6d3355d5e252ad8d039abe234922"},
            {"size":[596,842,3,1788],"margin":"e2a51e96f016f25b780e0ee2b9e199954a2f16cf6421e04545d35def7bd0a763","objects":"713a102761f5275d96cb77c0d77a31389d38b9e25f2e5b1144b941b3319754d3"},
            {"size":[596,842,3,1788],"margin":"998b9b3aa7b71c6a2a57ffbbb735378239f46985fe54088af893a1422cefd5c3","tail":[594,"c429901c652f06c6d8c124c36f09046bf0a6d703605850f479bccb21d27259ea"],"objects":"5e4ba8f95b973356c19718903781df24ef09170e31ddd70c468f96409d832556","total":{"marks":12,"literal":"[Total: 12]","box":[0.8365649366215654,0.6875197103336739,0.9166855497415052,0.7053545989618608]}},
            {"size":[596,842,3,1788],"margin":"13b01237bd2b25aa23b49cae77d572ac3135504034a0511de2034335bd3d7464","objects":"9b15a5d66fe91bd71935aed068473a7b6b1875125eb5e0d70f1fb01ecb716a42"},
            {"size":[596,842,3,1788],"margin":"ee6c51c68d11caf09d21d024de742c581daf415120412a4d10625e86965d243c","tail":[630,"25b2f9f70c03e33ee70537154cd47c62a84f73aa2bb2a85ee1859f0c037e8e9d"],"objects":"853a78e233a397946bb84b4333d350d1e713719e51178b8e2c6b7e5081ede619","total":{"marks":13,"literal":"[Total: 13]","box":[0.8365452503752178,0.7295986537452425,0.9166658634951577,0.7474335423734294]}},
            {"size":[596,842,3,1788],"margin":"faad5a9bb63eeeb142093f2d862525e304b10976ac89c5d70c79074affd85786","tail":[667,"b3ce84cb07966731c59f858e370ad40d613c324f93fc43ac4dbdd9d6dd6126e9"],"objects":"a9a4f6e1bae7cfc14cb6257a5d8aa3ae29280e1c86c517ab59431d0c89e35efd","total":{"marks":8,"literal":"[Total: 8]","box":[0.846824854542222,0.7733409137011088,0.9166711951868768,0.7911758023292956]}},
            {"size":[596,842,3,1788],"margin":"386d083a958660fdcd0ebbbbece621859d64c76897ba7dadae9c0b9ba2fd7194","objects":"0d6a7d2308370a211a2a6fbfc660e6ffdfcf0e8a2df61b0df38f7279f40dd51f"},
            {"size":[596,842,3,1788],"margin":"73ac28089819e80aadd952e87e3ffb7838bb3cc04fdc5f2780f863ce5c1e33ab","objects":"dd3ac58f7892cfd6c9c7b34058deb766a570989c6bab12f117ec3dbd9a8ad586"},
            {"size":[596,842,3,1788],"margin":"292ea0fd0ef29197cb136179d15d49843b5f0ed5fe6d223a621b3c9a6352112a","tail":[792,"3a79be96cf5bf8289d18d6d9a54e6730bdfcbad0dcb8d84d4ed1d518e84e7a2f"],"objects":"2d82bc349c91407c62f8b236d159b4df71ca4fbf329bbdad145be2b0c605df48","total":{"marks":15,"literal":"[Total: 15]","box":[0.8365624758407719,0.9220256662437146,0.9166830889607118,0.9398605548719015]}},
            {"size":[596,842,3,1788],"margin":"67a552148541f86b32e4d9605e775d06849ce06a4aa29d74d848b5997599c7f8","objects":"5631a2ec99b4a26cdc12c49b47c45f7432a654ba5ee98cac7b9e853e9a4af029"},
            {"size":[596,842,3,1788],"margin":"1b656bdc3dbe901d23c5b9705b45ad05666f94ddc582deb8b38cf0807fee3dc7","objects":"eaf36d2938c115ae31c3b4bdbf863f271b81ee96b08da1a0fdedfb2a8205c812"},
            {"size":[596,842,3,1788],"margin":"8f1de78638aebce279289e44261c6f3a4a26296f55ad29d457123b0cd5ea9223","objects":"ca1142d90bf49d95ba2139e781d798393ddcec8a190f766816ceede83ff88377"},
            {"size":[596,842,3,1788],"margin":"4e0a18422ddc99ab015b346302d1d5732ec7d95f17c5449db4caa2ea7cf7732c","tail":[757,"adf06deb9ae32e816366241f1985353f2ca5d50dd6bf710baad8533911081beb"],"objects":"479c380dff199b84e4b272a233bee86df5272aff9e3bd4e67e66803c5e6e308c","total":{"marks":12,"literal":"[Total: 12]","box":[0.8365420206004264,0.8809932282724519,0.9166626849866328,0.8988281169006388]}},
            {"size":[596,842,3,1788],"margin":"068934a2b216f4b0b7967e78f2db3dc4ed8fa0b900aa83d99194d50355583313","full":"57bff657e2921048519e59f8e2ee56964ff2bdf7c0330bfbcdaf72c752b3397e","objects":"c6eb0fca2c1c2badb83ca58ff00aacc731b38d1842e635ab2e8b787078d0d05c"},
            {"size":[596,842,3,1788],"margin":"2105a4cb27ea9b76f086bdda80260c36d614e2747765c9e422fb1e9cb41e7d3e","full":"406ea74da95d4187ab3b03ba609c436717084af4b4f32c05106c178a18f59436","objects":"27e3623b71fc19c3a9193007b94990f1e48274396fbc3e61e8c1ac8c3ec49eda"},
            {"size":[596,842,3,1788],"margin":"139308b8d6182c60d458cf42168a091308e650793bfc0a5716ad8ce0ba3591f9","full":"9ccf4af2d6e53ae370161e5cc617684b4ebc8ab56807acbd8d57289e251e22dc","objects":"c54b974d6c988aa700408845d18e4bfd6b24f34e19e1bd453d6aaed14d4cbbb9"}
        ]
    },
    "9701_w23_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2023/w/9701_w23_qp_22.pdf",
        "source_sha256": "8696ca0cfe71e48f70b783502eb0a804b9241b73a7055742e9a2048af32ff0af",
        "pages": [
            {"size":[596,842,3,1788],"margin":"8750b22f2e8a2cf139fbf628f7232d096be20da07a3dc236dac7a632fd0bec58","full":"7c5e7e013c2685a0ce93b73f5079d9f96a874ae19a1b4e320ce60c854970738b","objects":"98444e7937ecc8766c31feba4a9243172eb6d4e1b794656a42eef650942c248c"},
            {"size":[596,842,3,1788],"margin":"dbcbc8d2f6746f3d6fc59e359d0338221e687217d65898909d64bd033670fc28","objects":"acde7bf8b17eae7e8f6b157597018dc8e1e67348aef1ddce6eea06d4fd3cf230"},
            {"size":[596,842,3,1788],"margin":"edd9e52356cd0e7a7766333d24079852b93583b71f06ccc73ff84da2a9866996","tail":[493,"77237f3a71f0dec6309ecb483a9b8d18bfc67a6af33febc82c2cba98f80c56cd"],"objects":"441eadb41fdca584c94d61f03c810a7406206ad0e90a2b3a5c0226ee2e623db0","total":{"marks":13,"literal":"[Total: 13]","box":[0.8365405338786971,0.5668275102392238,0.9166611469986369,0.5846623988674107]}},
            {"size":[596,842,3,1788],"margin":"617b8beccad350eb86ee832b03c44779f622ee0616ae2066f2d5297cb0a681f3","objects":"ed233310805ffe21d7dac937c63765fee07d0261a02129e57b93bbbb92c11c2a"},
            {"size":[596,842,3,1788],"margin":"1715d82756506b2d3c81466abbe55b5ecbe395cee260b6b793090b0ff824426a","objects":"bd42adffc7c23567d0daae0fe28fbd241710c28455f5214e968669fba013a47a"},
            {"size":[596,842,3,1788],"margin":"2d984a399c2701f4cf132a806f9fc18ce68c7c0bc2f43c9aa655781a8083d519","tail":[584,"b6e82e7810f8dc77f4d35cc7211922edd5c396867c022b2415e8160c3fdd241b"],"objects":"d043f59499678fca8be0d20adbb99a6d3a380a6502e15c4db49fc5e29a2a9431","total":{"marks":15,"literal":"[Total: 15]","box":[0.8365423794642921,0.6749639649789329,0.916662992584232,0.6927988536071198]}},
            {"size":[596,842,3,1788],"margin":"5a7a84573d6f4924864025297ba4c5190fa5533db072683869b8da4b7f21c987","full":"aefb211b318f8344e2fd9133f0a6836cce32126a0015f6ddb55d0c1210ac71c2","objects":"b1119982dba63334d9489e4050487c246244263963c7b92734091916c4b89f94"},
            {"size":[596,842,3,1788],"margin":"beb3d3d256a205d93ba78970e890f9efb06ed576a6c99bcb73e7b9f899aefdf9","objects":"5d39257ccd35c1bc3b45323300ccb362afa6c8632fa31748c335bc409b1e0025"},
            {"size":[596,842,3,1788],"margin":"37761c21c00eef15d08232b6db03de397c5e0d2e30cce843e875a27b7d21179c","objects":"652f52f70bc86919a2ca87a5a6033c74a6e1f0a0f60eca5d03890e4e7e23f53d"},
            {"size":[596,842,3,1788],"margin":"0e68f06ebe02fceebfd9e548ed9a6b9b3b8e09f1c8dbbff0e959324c9d0867f1","objects":"c836cbc1771e297b07b0512ace743792e6f810c94ffa1ff8079aa3c58cc5b780"},
            {"size":[596,842,3,1788],"margin":"73eea634082d7bb93215ccaa2ebdb0fb0e21a925a5f19d8d0c0c45bae1a0a8fa","objects":"aabce7cb808ce06a11c2f8fffbe886eca35bf122d545baa965802a286eb99393"},
            {"size":[596,842,3,1788],"margin":"72ca90123f21b0a00fffa7f6c50a269e0eaf8c46e69e7ee42e4c5a1877edae64","tail":[756,"ddd4404f21c1e691fac1206b8f55563b745cf05a4bda1129d31ef82b9f763ad1"],"objects":"88dfc3391fe4c01a1d8ac42f748b0a579800206a573e113cb73e3e7b4dc5980f","total":{"marks":19,"literal":"[Total: 19]","box":[0.8365754974724705,0.8798856072044233,0.9166960080598774,0.8977204958326102]}},
            {"size":[596,842,3,1788],"margin":"73629b2c80b2a7a43c5803addec146f873af1692eb553edf11b55213a2df84df","objects":"5945d103b31ab7b545f8e223f368b4d61055ad47e32c8ebf44f98a712570237b"},
            {"size":[596,842,3,1788],"margin":"d7842a91b8f49d306e51b092c9a54d4541272834b1f7e500b6bee665fd023c3b","objects":"7268b3f1c5a722a45386a5515dbd3a2f2dbf2a8d6f8f061a767064360499f207"},
            {"size":[596,842,3,1788],"margin":"bfaf1e17ecda66101d0735c3458b521c8d8af52c84cae5d17c86f7081233d94d","tail":[328,"ec211cb1dd46fa27579561eaa446072678e0b63b69b234e0bce52bcebfa45f00"],"objects":"56b7cfd7a932dd4e86cd71ed479779ee479ae569b5dd63e1b5d20089540711b7","total":{"marks":13,"literal":"[Total: 13]","box":[0.8365473522921455,0.3716671864757423,0.9166679141458189,0.3895020751039292]}},
            {"size":[596,842,3,1788],"margin":"f0d6bbe16408c113822a8bf0151fa09124fafba2e1616e2b6f81fe49dd69561b","full":"1fd8b63d4ad4679d73a023cc63911450abefc25f2be74fa6f369f9923dc93aba","objects":"6f2bda2df6781d2f5bbfeaf3561bd32e66a0c520f75b16a4a985386520f0898e"},
            {"size":[596,842,3,1788],"margin":"5559d2326acd2e539f58537660664324efd6dbac766ba87e18b6debcac7dfae6","full":"42d84fa58357c9110eb913020b930ac1f80ab703b10f41501a8fcc25903eeca3","objects":"13834343e8bd9f7143533569827955632580c95150b23a4e35e485c16f7e1285"},
            {"size":[596,842,3,1788],"margin":"08c0805579efce2304ca2bb22323b955c8f4eea5fb90dae7b72ed73d3dd7c4cb","full":"404008b229513755cfbc3f09a78b4974c5c1ad3919e0baf5e6dea206d0ec82c7","objects":"8ac97a67f386016a82898e2320014edbe0e725bc920f65fe33caee971276d75d"},
            {"size":[596,842,3,1788],"margin":"6ce1b466a2d320417e0cee86766f5915315b7664c18b00745cccbad5c8e5c442","full":"6b49da863f8ab48713881176b8607371d1ee2e6ef12227c32a52a44fe9bd19ba","objects":"18eb82d33faf7636d1887d738272d2c81d781055c4736a130011ccfa0e114dd6"},
            {"size":[596,842,3,1788],"margin":"8ff75979b58ddf981af8fd0e88ddfeac666a457bdb273457d89d91b8ecfe173c","full":"4808c7229cf328761436ae4334f26b979fa365d8f6113c0a38ce9153895d3732","objects":"6ffcfc4f81ac826520e25dfb52efe7bb50067d6be4a58c39852e17d5b7290a99"}
        ]
    },
    "9701_s25_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2025/s/9701_s25_qp_22.pdf",
        "source_sha256": "dea8f17527e2bd62bcca8be4c885f0bb4fe136ee4b7c3f7049129efc6d73ddd5",
        "pages": [
            {"size":[596,842,3,1788],"margin":"05e3cc664860defeb07263378b0f32da5841043c714aeaf93a46fb38595a4abf","full":"7b6a99bcddee9bc4ee59ea559b93fc7f2025fc85cf5d8bd26644b6201067b6c7","objects":"ed72db2b17ff22e2798c9f09c507a749efff52c77be64327d0e442cba593026c"},
            {"size":[596,842,3,1788],"margin":"a4c6db8459490bdbab944bb40dce38ec6f25fb2ea10c3ab64c87e629ce21ec4a","objects":"f6f5efdabcbf011da513353a10bb869454bb32b5b1b6fa1d043fcb3f990d33d5"},
            {"size":[596,842,3,1788],"margin":"8cf6d458a1ddcddd6ca73003dbe5f7554644acff794c6158ac4a7db85bd4221d","tail":[664,"b8360fb88bb5d707adb847b1bf876ee07b06abe2cf3b14617d73692162a1afbc"],"objects":"1e422922e5045bbbf527a577d3a155b0bcfbcbf0b445da4dad4a99db508fcfa3","total":{"marks":16,"literal":"[Total: 16]","box":[0.8366531511602333,0.7744294749375831,0.9167737705186971,0.7874953184545614]}},
            {"size":[596,842,3,1788],"margin":"971776cfd4b08ffb25d67342d10c833517e51d021799fa8ccbe2400388a11987","objects":"a3c3ed8ce158de0fdad176b308b1e99eeb237b28a5abbd4fcc7955f7821bb05c"},
            {"size":[596,842,3,1788],"margin":"99b6166c63a2884d6eaaa5ba58432b5c2f7674d5fb3194ffb16cdff821f65ed4","tail":[425,"b443287b8215c38dfa726582d9730643cfbe47428ee8374d6e358bdb0a030059"],"objects":"aa29afce9195459d0e4fe8261e32ea3993bb30a4d553f7041494e0e0f5001903","total":{"marks":10,"literal":"[Total: 10]","box":[0.8366196229978586,0.49079183692170864,0.9167402423563223,0.5038576804386871]}},
            {"size":[596,842,3,1788],"margin":"7d312b94d40029e4153107773ac7ffaa145a929691c87e867e28d270a8fa7ba4","objects":"0f072e58defb8dfc98dc579ccf96fc37b1d0c227b5a0e7a323bb3aeffb3bc0e6"},
            {"size":[596,842,3,1788],"margin":"bbafa1808991bd33f9b982b0b5496286c596b6c43c930defd4a79e6a09e27665","objects":"fc48a831cda8822b9c3f06c9d628e07db579c3e11151b713782804aa3be7b6d9"},
            {"size":[596,842,3,1788],"margin":"1854149b986a5962cc5bbb7c652b2f3ac7158c4e42c4f5313dfa8475176b094f","objects":"856cfed6a2fb79a4fe9006cd99b8f176891b35b91b50c2d8410534ec7a8683c7"},
            {"size":[596,842,3,1788],"margin":"d6a529f380aa4326ee0a826c963bf37622015dbf3fa2148f981ef84331000fe7","tail":[736,"d125825daf6f5b9dc5bb4c898951730e23b7423ff9880cf60e092eca915225cb"],"objects":"f817a463dd25b87519ddf3131562ce66952b2b7faf64131dbe0c1db26e10e8e9","total":{"marks":16,"literal":"[Total: 16]","box":[0.8366154191609859,0.8609248602351162,0.9167360385194496,0.8739907037520946]}},
            {"size":[596,842,3,1788],"margin":"704b84ce3bc1f167ab21b3fe837dbf2f91af0a4523255bff634fb05715cd1953","objects":"a9975cacca1514fd6de382be78dd48bd883b03f06d77a362bc321d91108740c4"},
            {"size":[596,842,3,1788],"margin":"0e50669b33be329decf026e0da1a3632b7a51b517c79636a13088b3d1d959c45","tail":[653,"deba77b71f8ac2ae9566c09a6e1378e5ffb884c12c06527ce9bfe09a95b6f1b8"],"objects":"2167f5d5154565a09a7b202b28a1a4f446cee470c620df47450f4f8da28a1a28","total":{"marks":13,"literal":"[Total: 13]","box":[0.836606293758994,0.7616388330696106,0.9167269131174578,0.7747046765865889]}},
            {"size":[596,842,3,1788],"margin":"fe6fbb28edeb3b01d2a031daaaa316584b6ba07497c87f19b75111e761a0b2f1","objects":"36d46e9b9d53d7a5f238c9e0b5364342c355bdd719ee3bcb757dbda249b49e58"},
            {"size":[596,842,3,1788],"margin":"0f428b8cb22069582a03bf9977622714f69550707d7c089d5d574b14aaa55e6d","tail":[792,"1079680566779b90f4b5172b16f5beb5bc99e1730baa58dbfb8580bfc75fd0ce"],"objects":"ada984dc99265e7bad04dab3373eb04149562b29e46459db57d1e73a7c090867","total":{"marks":5,"literal":"[Total: 5]","box":[0.8468867255648137,0.9264267675797377,0.9167330650738568,0.9394926110967162]}},
            {"size":[596,842,3,1788],"margin":"6b6de226d128fc37096c32d24d267cbd7841251d91bf805c5b6afd8c6730f2eb","full":"3679810a49eaf9e0f8ff2eece0994f852f957d3d649573f6bbcfdd92af683752","objects":"4262b662929bdccc1cf64538049cbac01a9f35cc75db83c29eda4fe43a113bb3"},
            {"size":[596,842,3,1788],"margin":"eee90d2d127b98291073f976829e51d56a184889b103934a35d60502fb71e6f7","full":"3c5a1c53cc130acf7248a8d4b321932bd9772cfa001683fa29a23ef5db6b9a2b","objects":"537b9d73eb2966366b159385aef35700a95c09a2f12d040f30e80b553f71d45e"},
            {"size":[596,842,3,1788],"margin":"85652e519cab8d4db8ce98cc12b5ba776d356a639a7d0594e47b7508862eb7e6","full":"1f1ad9b97e0049b5ce56c4e0867bba2cb8f8a2957a7885d3a89a34f3230dab52","objects":"64657c436f290b4e7d9d1c0a1d00097e8906d7ab19716eb86e3331561ce9730b"}
        ]
    },
    "9701_w25_22": {
        "source_reference": "Library/Courses/9701/Sources/PastPapers/9701/2025/w/9701_w25_qp_22.pdf",
        "source_sha256": "ef853c40beacdd8bb12bd59eca7015d08d837100c200866d00cb5bd2acc785c9",
        "pages": [
            {"size":[596,842,3,1788],"margin":"a8890342e9f5eedeb04c44137e9837cb183c2231e53d8364b0f6cab7d0075058","full":"6baf84ce88e4daa7818bdf02392275f6cf5f1d57969616c5d12673820a3288e7","objects":"2055890e322f67c9ecf6dcc99151770113cbcfec9cb0c94c7e130fdc52b6a19e"},
            {"size":[596,842,3,1788],"margin":"dcc8497b0496d5f3e7c5c42c3691fcbc93755081e6e8412f5550bbd5e581469d","objects":"954c52badbe2b6fbc1c43208aa01b316cd92ea24a8c66dfa2f03036a6ae37680"},
            {"size":[596,842,3,1788],"margin":"c03db62dab3136f91b8eb31294752f8ee1ab16eea59d3caf2b19848e699ea543","tail":[466,"96dc6243dfcf6a32c6db71d8cedc064cfcb98fe44f3c75b30f987550220a3715"],"objects":"f233b33f9d50bf7ab0cf9a2c6911324f1c7371b61ee1d9991d127eecf6bd9647","total":{"marks":10,"literal":"[Total: 10]","box":[0.8366050633677142,0.5394298497512093,0.9167256827261779,0.5524956932681878]}},
            {"size":[596,842,3,1788],"margin":"f79e943ac67328c1eba39edce9544169ca3c5a9bbf31ae84244732193dd359df","objects":"0071c7c7680b535002b7405cb5eaf515bb4d642e8ac2452c3396f6f7d1489d34"},
            {"size":[596,842,3,1788],"margin":"e4171670aa1bac180f8a4f1e84bdad8f2c60187730777e1135f128710ef29319","objects":"5901d4f3a54276a8a6d53cb1d119fa689ac12f05e6106320c09a1823bb5654cb"},
            {"size":[596,842,3,1788],"margin":"a8202dc58eed26273a70d448000703bff7d152437822ce74ed3c1134cdb80fd2","tail":[673,"a25c85d31079cff9d2eeafbf2b941e1ac7f4fc8b741cb4154525b2c74dbed3e2"],"objects":"ea954b735c6075c5352a90fb549d4b8592874041eab2d3b55830bb8d9e088c20","total":{"marks":20,"literal":"[Total: 20]","box":[0.8366091646719802,0.7861474393559528,0.916729784030444,0.7992132828729313]}},
            {"size":[596,842,3,1788],"margin":"26c1dfec5492ec56b974ab72bccf152d2fe9ae85770d6d9bf6a9e2e841187a86","full":"c3fcb109692bd1210466817ff867d8bbb3640543e6471d05ca5603ff609bf66f","objects":"6f7cbf40a390bd9604ff7b149f195a31a31e4c303e5d85b9be1e0d2bf71a1f56"},
            {"size":[596,842,3,1788],"margin":"7053bd8721e3e7fb5c4ab20ca328312dbee342cafeac9370dfa3c687e4dcf06c","objects":"186d489048fa9cb04d059ce27e6c671191114a8900a5ef5132ae4ed0e7668727"},
            {"size":[596,842,3,1788],"margin":"d48a77b27095467788759c01778dee3c8ca5a863c7e210a6edc3cb92a80e07d7","tail":[794,"55c3e4fdc8c1da10a0a30753971a523b72e28df4a0042d11584b8b19528387e7"],"objects":"160cb35d9fc3966412de2427c1108f69a9ff84e7a2d8271cf9ec392ad04605d4","total":{"marks":14,"literal":"[Total: 14]","box":[0.8366093697371936,0.929301087858489,0.9167299890956573,0.9423669313754675]}},
            {"size":[596,842,3,1788],"margin":"2e3a0d943725a901eb3b0466516408b2c519f3c2d6766f4b42d53b7cc5125c91","objects":"35b8902750b35fd637dacd3db0b803da6b8e0660a9bfa2287ecb3db8cd793b72"},
            {"size":[596,842,3,1788],"margin":"7c7f7d9b6e93efbca41b813ac3620f57cd98cef6a46a8e8ceff76fa139d39e1d","objects":"c4336861dc730a0a870c0395c692cd5101d2b518ff46c4837edbf8f522e45eb5"},
            {"size":[596,842,3,1788],"margin":"1240df208c92d8262626b2bf85c61d2ad0541d8f36b010813e997205c2c76983","objects":"8ddcf4b9dfe576fcabb1259e942013e6ef64151a78c904014f43b5d112147418"},
            {"size":[596,842,3,1788],"margin":"3d2a55a167f638ad4a4a0bd9179195e8d9ba4d48a4ec9f7b401d9ce64f9335da","tail":[578,"a0b1a5b2355e59cf02bad485a41b17aadcee17b23255143e4fc2dffb3bffe1c9"],"objects":"75411a789556a2a2dda35e4ec3b9561937d2a583c81fa93c78163b4d7cadd725","total":{"marks":16,"literal":"[Total: 16]","box":[0.8366197255304653,0.6725785481039578,0.916740344888929,0.6856443916209363]}},
            {"size":[596,842,3,1788],"margin":"bed1a646055fd788b0c1564bca468a39dc003ccbe9f1051006f6f1f4a927d05c","full":"11fbc88279db52bbd1f3e28de6b160199bef1240c725de41f0d89713f398408a","objects":"2165a07a7f65d3280ff5686638485e8bb6f46e0a0f1c1149a8b933b76bf5578c"},
            {"size":[596,842,3,1788],"margin":"96ad7a81250783d2fac70bd5ec5a66e9c85c7c99567cef04a095b0af9b4ce9b7","full":"29fe4eb3c5a06125ec11db3fc3360778d7f41a78161bf3758577e6e36e3952c4","objects":"743b3a78e987ed68e79bd65019e9ade913ff5b64ce49329f9871a6a68d4168c0"},
            {"size":[596,842,3,1788],"margin":"1439b65e303e102b21b2d381a591c06d60a1da3f10f13cf8d09a0c37b8a7d10c","full":"41391a963ca92f60a7ea05f0e9a8d50ed2a1d972ad9d63d6a48c6bb4d07cc334","objects":"58aa4d917c83a741124f1b90b9dff87cd77e99b60fbf4285a02a12f29b66fa2b"}
        ]
    },
    "9702_w19_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2019/w/9702_w19_qp_22.pdf",
        "source_sha256": "310cbce9d0150976a515fd45855017170320097071207d6bbc988c639bbf955d",
        "pages": [
            {"size":[596,842,3,1788],"margin":"aac49c7d53c195b4456b631660c56a1be3b2b7878f23621c48974998d7543caf","full":"9d8006eb4a4958f169e7b9bc166692c32e803ae2d60ab3d0933f2695ecf20c60","objects":"f8eef5fb1094f1df41dd4f78c2bb2b5a34e05686dc61cb58e028ebc3c6b13a20"},
            {"size":[596,842,3,1788],"margin":"4fe047c496ea6e2ad0f5c2872f39945fb33e2a10afa5a636fa490928ff7eb111","full":"561594c30cbabbfdd2970a1371c33ea5782e6b72acd154ab72a68f58a186d3d5","objects":"a6d7fb2db43b5cecee6886f4b9d83be9a3875c54492ca9234f2a1ba8232d08b5"},
            {"size":[596,842,3,1788],"margin":"9fe8fba39c8e4589be00f8a75445c807698445f1e745445c8e2713a6642df388","full":"818d8e7fc499a7a0549b6bb932052e46530a3f34ebeb643ac35994407539b868","objects":"dcdfd2208fc268d80ea9a30fe7121f217ee875b5d410464c97cf10baa59c9781"},
            {"size":[596,842,3,1788],"margin":"989d7219edd8819391ba8ee225806d06de1a6581fb6a7703b8e2875b41775ea1","full":"adb2e580cb06f6b86482b9d8fe0a8a9ffc5d4d56887b20c084cb547d83784068","objects":"d8c3059e0f479b2bf65cec61de214c1d6371610fc8c9551424bfeabe18fdaeac"},
            {"size":[596,842,3,1788],"margin":"e349fafa0a81b2e9c55b87fdebe295aaf3656c386466f1ceb56542184cbc4ce9","tail":[651,"72a0ad3457ec6e1f2e7805306c2b14edfe1e84e10ede6dd58486fa6826c93316"],"objects":"b0deb78082b0dfbda1333da9b830a5aafe3a9d1c0bb092635dff61b5cfa1babd","total":{"marks":6,"literal":"[Total: 6]","box":[0.8468192665191702,0.7513429851076512,0.9166655558975585,0.772287520971795]}},
            {"size":[596,842,3,1788],"margin":"b08aa6b7399a1d9c6a1716a4cda0f2ae06c7f054e7908396c27e0cf137061231","objects":"1d03b75bea6ce7e0230a2ea89418a4619995b4f026bf2f7123742b2f9806a6a8"},
            {"size":[596,842,3,1788],"margin":"b63de5514b20e6f9c791fa28e536773bba8ed2584728d3ce1c03db40a8521a45","tail":[495,"464bacd36e4dbbbbac52972a41290ce995897f5579ebe0989d5d265b148882dc"],"objects":"0da14ffcc328db7fbdf41a4b81e003780da67d9d52a547690ffd5169c0294fce","total":{"marks":8,"literal":"[Total: 8]","box":[0.8468228038915607,0.5660704884305869,0.9166691445362156,0.5870150242947307]}},
            {"size":[596,842,3,1788],"margin":"7a26a2b1261b4d1015a4708e6d939c453b9b535abc8e41aaa05f4ab3dc6ff0a3","objects":"54993a8b4a98e78d31ebadcc4754a081011b7d7eb2570380f28d256a4110466f"},
            {"size":[596,842,3,1788],"margin":"71c0615787bd5a581cf92b062ba3f37505dbcd2ec986af3e29f5ad5211cd636d","tail":[696,"8115f43284032498c03bc26abdea961c602f33d6756c084c0180d4ac395eeac4"],"objects":"11eaabf873daf1321df0dfb54cebe18cbc8bac84d027927d3234b0564a749a70","total":{"marks":14,"literal":"[Total: 14]","box":[0.8365424307305587,0.8055585642133853,0.916662992584232,0.8265031000775291]}},
            {"size":[596,842,3,1788],"margin":"c8211485d3494d59df51c3d9d498d0b3e1ac49ba7fc9671b4e11cc05e0258cdf","objects":"cff685272aabf291b6a988e1dfd28e89ec7130c638cdc61370e825ee8d7ac48b"},
            {"size":[596,842,3,1788],"margin":"0e3e7b73bb022314907c90e4eb77dea4a39ba7cade3da80c094daedf234d319c","tail":[417,"5f01d2c6a231e81dc1424306906daf55278f1626292af8636276d42f4a919d57"],"objects":"0f27bab89b2d0e0fb31c9b771341f84c3bbfc8cf593c7775b523fdce153459b4","total":{"marks":8,"literal":"[Total: 8]","box":[0.8468199842469016,0.47339211888243804,0.91666627362529,0.49433665474658184]}},
            {"size":[596,842,3,1788],"margin":"5fa05e8cf6b110666eeaa76f67df5b2de6ed1294edde01108b75e1320fbc453f","objects":"ecffc0b8661c21f0d6397526a71cee9b3e5d5ce39eaefc6ab5e3b8a8f392ff13"},
            {"size":[596,842,3,1788],"margin":"a51ff3f31643756582dbc8862a857a98f3956609822996a1fd6f1c8f56cc4a07","tail":[794,"b781d9d2aacd4411b16c5881eb914243bcc62529039805f61e26e9b54abbc443"],"objects":"83013db26afd315a2a354a6bbb66dbae08a9533da1121273e793f1140f4db567","total":{"marks":9,"literal":"[Total: 9]","box":[0.8467972220245623,0.921359484152203,0.9166435114029506,0.9423040200163468]}},
            {"size":[596,842,3,1788],"margin":"69b7464b13dcb8fb1a404512b71fe73a397972de2ac8cf4deee8e0bb7764e7e3","objects":"cd86999e85b3e61c4f1e06f4727e41e4eab6cd2fbf9b1d7d80487b5c828896f7"},
            {"size":[596,842,3,1788],"margin":"c64504e4305f48d80608f7bd8bc1e4ad022475b06ed5c862ccc13a8c0c835f7b","tail":[797,"e6a10d93ed3a4712b219ff8b202930e156ecad3851aceb5ac758efbc661c6956"],"objects":"b073aadb04ad97d2a107e05411744c1a388ae329126418b281c7a6f8a5164296","total":{"marks":11,"literal":"[Total: 11]","box":[0.8379097533251814,0.9250457787225689,0.9166703749266123,0.9459903145867127]}},
            {"size":[596,842,3,1788],"margin":"65d8af146dd8638f51eadb02085258825c27be152c87d5382e39f67c11c5db29","tail":[473,"be423e02030f4a21094858284ad68572ce00d008a484ce1a8a1ebbe6857a0c59"],"objects":"de0e23a479c0d306be6a66ec1147fb01c645176ddb08aeda33b551240a8b6441","total":{"marks":4,"literal":"[Total: 4]","box":[0.846818958921571,0.5398357171328056,0.9166652482999593,0.5607802529969494]}}
        ]
    },
    "9702_s20_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2020/s/9702_s20_qp_22.pdf",
        "source_sha256": "eb7600b15093c31a43721a22e1be0d50107ef56b82aeca224232882a6fe3d71e",
        "pages": [
            {"size":[596,842,3,1788],"margin":"f154d7f388cc56e55c3e63a31879a60c346781bbfe3413b1be7f1a65b5819203","full":"b99f60fc2df8aebe9091a4d83f8b2dbdb424735c15dc0a323ec473e3b01124bc","objects":"1ea35f5a3e9bd6b3d9b578c14f204970157b8b316314ac6a701bb6942875d1e3"},
            {"size":[596,842,3,1788],"margin":"3e543a648d51212282863cf06d917848959bbffe639a71968fb239f6c064b79b","full":"57d11bed51b9aeb76d280575b11b7aa81a167535ec86bb9f7ac0e40a7e44601f","objects":"10d0e20e5a7827dfe415e96484e8a0b80ba2561a3dc483daa22d1bd4a705ec46"},
            {"size":[596,842,3,1788],"margin":"f038ef01b33d1e10f637ea71719f2db9e61faa685666d909cfce4b943cb56a7e","full":"576a150b97285fb4a94e6151cf7b73bcc6cd89b7fe71b6f6cf6c0e9f8faf1d05","objects":"e27a71ddcb7de0498d1a8b65ba28ea69eeaefb1f1ac8fc7126dba2c8e95dfc42"},
            {"size":[596,842,3,1788],"margin":"a2851ed4a846e272657538c13bcb3f42f045bdff2e96c82c6d0f33a96c867fa2","full":"f7c980b5610ba42f583895ff38d4fff1aef259a9dfaac5728ca49214d57d2e72","objects":"9bb41ac835a68b646e8947c974de25a6df6d06cb99378ed885863a2c19789be8"},
            {"size":[596,842,3,1788],"margin":"c3403663f64edfd7b66b423ddf7483e467817eb43f4a24519617cf7830022ce9","tail":[724,"a4d5f27e5fa1523434108694bee3c13f872ddfb50f717889d6f261aa9c5cb031"],"objects":"44571c8eb9208ace853731e0bf0a4cbf3f7bd0e3677ed76c062b3614ac55cca2","total":{"marks":6,"literal":"[Total: 6]","box":[0.8468238292168914,0.8417572127677868,0.9166701698615463,0.8595921013959738]}},
            {"size":[596,842,3,1788],"margin":"acf0a1b3500910b89c4c6b0359d36053c173b3f23139f96f1a421d65701b3f2e","objects":"65cdfe129d5da48693b56248c0b678336d9bacfe4eb95f22919670d9928c16d6"},
            {"size":[596,842,3,1788],"margin":"1537d25a53e71adc68ff8a2f3e2d8920fc2435bd1b5505295497306c8725657c","tail":[758,"08b72321128b839e429b96c585b39a22f53974d2bb97315ff2d680bfbf58ab3f"],"objects":"70a34f9adfde3dd9b2f768b674a043e284fa7ae1f629ac2266127227dca90c72","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365496080078728,0.8823972202611573,0.9166701698615463,0.9002321088893441]}},
            {"size":[596,842,3,1788],"margin":"8b867c02abcf8e1746d4c0ceedf0362473ae09f17ff4d2427d9bed042db68681","objects":"ea05bf3859b90f1d1c7f19c6f9e420efd58588bf023903efeeecf427d964fe1f"},
            {"size":[596,842,3,1788],"margin":"b3219ce9ab0f157a52d801b26a5924978db793065d550b1d5a4210b89bbc76e8","tail":[363,"e5cb2a0386363e978013d17e7d9fbe55fed9d152fb79cf833b9a90edefa04abb"],"objects":"31505117dd4397534a46ffb3dc7b7e4ace89fb4ce72adbd1ade8a8cef0009bf6","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468164468745111,0.41211086998349805,0.9166627875191659,0.42994575861168494]}},
            {"size":[596,842,3,1788],"margin":"ba9f5790ed8adeee4ca6777cd83bd1ada59ae281f4047b12205065f6665b359d","objects":"d812f124d037949f42b54fd6e2039e1a62de5bfd48b307264da524298805b7d6"},
            {"size":[596,842,3,1788],"margin":"6dd08ddbd2500d9dbabdd930e9eba48411def44fb5a9f3d0f02816b5009802cd","tail":[792,"5407540931d1dc99420a147e2d675f43a4fa99748c94cdc561ac558d217c200d"],"objects":"363ff74a223f18abdbb73e0d8cf682c6e10fda40d406c1a43ca1562b725c77d4","total":{"marks":11,"literal":"[Total: 11]","box":[0.8379098045914478,0.9220153715590923,0.9166610444661039,0.9398502601872791]}},
            {"size":[596,842,3,1788],"margin":"4ce4aa2ce7226c1c68bafcc2f5ca1be68afd302e398ad483d5b505d1c23a4374","objects":"35ff278dc1454562ea28f09a53423881b9b0b73181afb49fbd919290b7ba7a4a"},
            {"size":[596,842,3,1788],"margin":"c4724b704dd3c83f5896178d5729096681334f3cf9dd05f2fbdc64a3df552bee","tail":[429,"66360805b5cc2d353997a38f49499638892454033ae9f61db3d274fc2adc3e70"],"objects":"b8a76b285277e31c8c45de282fe3957ad32e0f8bd91cd4322fe45112f5b90102","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468402856884475,0.4912163140882179,0.9166865750668358,0.5090512027164048]}},
            {"size":[596,842,3,1788],"margin":"37291e99417e386f1f2d7488d932ef32c4e9c0ef8846eafa4e115cca5e9deaf3","objects":"debff0a9e2dad29a8e03a125ee38c04b07c4e2eb58541b338281887693aa22db"},
            {"size":[596,842,3,1788],"margin":"25cd2e37f3b11b74e187016cf0789aa09c999b5c4b7dfd2ac91530ecab5c4770","tail":[604,"a719a1091f23a045d60e22915af6f0c4391a370107c9fe271e4a768d32d334ef"],"objects":"c578754ec44501d9361519e9020d94308353e953d968fe28f7cf49547df27811","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365445839137529,0.6989479702289321,0.9166651457674263,0.7167828588571189]}},
            {"size":[596,842,3,1788],"margin":"575f2c5dd36ac169641ff0c5dcfbeb34914a0afe6124de61800200e753e114ba","tail":[524,"6b6d6f3831b3b4cb4c7b2e00b365bcfb8d2a1d6aa2a3992811fb8a43f3808ce3"],"objects":"d26e37f8ae93bd239f5cf7bd26cbebf1756d5bc062199d401a648955d72392bc","total":{"marks":5,"literal":"[Total: 5]","box":[0.8468230089566269,0.6033097701051928,0.9166693496012818,0.6211446587333797]}}
        ]
    },
    "9702_w20_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2020/w/9702_w20_qp_22.pdf",
        "source_sha256": "e92b3f4f78e2c3e43674906c75298081e0b40dec9ba54eb7b7b66611779690f3",
        "pages": [
            {"size":[596,842,3,1788],"margin":"1e510752548bf8b30f68f478f7b0beadd766f58e76e90fae0ae58c091a8a29d2","full":"3e098baa55188861e43c3bd051617f9472e48ba225b1d3fb88c537b3c9ea4909","objects":"bc323191a6c22d50a080f9d9fbd44a1a52d81fe8199b7ad3ee72c11937e4b7ce"},
            {"size":[596,842,3,1788],"margin":"471503ad8074cd5f6740a4548ee2d2b4f5a807d0565fd5c7f609eda76831165a","full":"1d05b49665e2b3c33a1c5c3c86015325d0e0ccdfa598fecc7ac2a10e5659246a","objects":"2301780ed18f4062de4cb0b60539725e3d26bda1697cf0c3a412269b136c5b8f"},
            {"size":[596,842,3,1788],"margin":"8c42994131559dc84d3bee3cea97b274f9264173abcf2dc8fc0b661fbbdc4aae","full":"aa16bd6a0a6a079e8c99875be4af855b8e0bbe160619f2b7e756ac46f9f922fa","objects":"f07101b6d12dbf05714942538d2e853aa319f6d1fcf11418599204d56db1cbbd"},
            {"size":[596,842,3,1788],"margin":"65693a3dd2a2e1c1eae29368e1c4931aeddeaa454dd3de0468039e2d7bf4d79e","objects":"915f8f00f2f37a569ef74ab12972a57974761866c50f2ab66f00af6228a40b61"},
            {"size":[596,842,3,1788],"margin":"dcfe34bd4f9d5230f0873e046442c69099f25f0b58564fd399acab0e83f5f864","tail":[511,"3f9c2fc5c5a874251bd97a6162a76bd18c70ebe370d5ac9088a258d1c2dcad46"],"objects":"c83e01ea56b6dd501f7384921d46a4233bb547fe9fd46911fcf327a23c075f99","total":{"marks":6,"literal":"[Total: 6]","box":[0.8468166006733107,0.5886672849277262,0.916662890051699,0.6065021735559131]}},
            {"size":[596,842,3,1788],"margin":"9d801fb964353836b7d244044dc6f6bdf6c8799a873e7bb299a2272c6bc4584d","objects":"ea0e72361321ec14df84bfca27636225e63818ff731e79fd255b3d26449e106a"},
            {"size":[596,842,3,1788],"margin":"42b501f588b91abc38d01b1147481d361518204131c5d9a78081fb5bfa437e25","objects":"543210a45dead583408748fd2c7128313b4fdf0676ac48e58d04f51bd2da4043"},
            {"size":[596,842,3,1788],"margin":"5a82394775cefba2c9a53318c3c6e8f562df7be979651ac9bd2ef08ed1f7ad05","tail":[311,"1b008c2ba23b44cfb2f07bea2152f81579d103c0c6325dba5ad7b8a382cc0a92"],"objects":"3709698bff6d751fd0c9cb5a121984e816f29b943de8a4789dfd4757428fa7f2","total":{"marks":12,"literal":"[Total: 12]","box":[0.8365485826825423,0.3509676206069427,0.9166691445362156,0.3688025092351296]}},
            {"size":[596,842,3,1788],"margin":"9a5cfa55e33d8ec165b83ffdaa065d5d154dd2f8985f72fcfe9bca6865e09917","full":"9f16a40444eb81e54187e5541c1ce3e871ed6890d213aae3278066dccfeb55bc","objects":"cb709d933b63c185fad44c16eb37b64cdcb9bf8777c105b5fc5e153a7be0a987"},
            {"size":[596,842,3,1788],"margin":"b75b240558abafb319552da16657a0812d2db0e6aaf904b69d0dbed737c5e0e4","objects":"8b262654420409d7c357c99ac6219d6e5a473b3950fa5134e2e9d2ca80d39143"},
            {"size":[596,842,3,1788],"margin":"0cac634707d97436d4ceabaa7136fa91cb15a217b0ecd32a91723df1ad7d729c","objects":"3840f33307c02aa921561f5e8b4a2e7d19ba8a34fc1f6be7678722ee028ef39e"},
            {"size":[596,842,3,1788],"margin":"796b6a79f6733df1110a1440748e000d0852272707a142acfa4a5a44a63de838","tail":[194,"9d6a8e88f5f66d8d03d7079531dff77f680ffe6681aee4632c33a9c80c970fa4"],"objects":"d21a2b13c97f16c3409c0f33883b0c3ee5dcc3eb8f83cc545ccc3ebf9e74d842","total":{"marks":13,"literal":"[Total: 13]","box":[0.8365485826825423,0.21197321120067486,0.9166691445362156,0.229808081704417]}},
            {"size":[596,842,3,1788],"margin":"dfe252591c16a78a50ff97d811753cc1e877248230a3f0203bd617bc829a7029","tail":[794,"c575bd3654621d600550149ab4bf9cee297ede21c9eb17bad130e06a1fb8a08f"],"objects":"2d57cb6d881bcfeb1f15499fb46d2f3e87b699d85715997bd7f3a6f4a2073c58","total":{"marks":4,"literal":"[Total: 4]","box":[0.846815472815447,0.9242809271537966,0.9166617621938353,0.9421158157819836]}},
            {"size":[596,842,3,1788],"margin":"c38d21ac05aeabf4d17d93d0639ecb6a06d9ad79adf7cf72ae8081110f7bf28a","objects":"1a62a55c6c894889a4ac6096482d18f6f2e81e5d89f1beee2f050f2e3ce9778a"},
            {"size":[596,842,3,1788],"margin":"ed726f8d04707e945b8dcc55cbeda72656944c83e54b025261a61326c8871634","tail":[441,"522eefb315319354653ce081151c6da0314912b970ccb51345c7ab189e726a02"],"objects":"d0afe792da1fab1a87009f0dc114c79b43ca63562640a7cd653536ca5d23963d","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468228038915607,0.5051187419373407,0.9166691445362156,0.5229536305655276]}},
            {"size":[596,842,3,1788],"margin":"4babe2e6109a9ede4652973d0e8e340642b035f2fe9bf6fcc00a7877ff956695","objects":"459920d61237ed067985f694fa7b39dff9fb53a21debfa03cf68b723d08bb444"},
            {"size":[596,842,3,1788],"margin":"2a104aaf05beed3e73fbc61ea8e3176b239bb01e53384213e46cdd48ffef2232","tail":[729,"c2c1f14216dafccb0ba1e594437e51a229b531c1afe663f1c0bfe55f42b59d76"],"objects":"08c43c8fc1143f360bbf8e2d8a9da0787514901bde5b29c3d2738bddfeb81fd2","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468238292168914,0.8475797268950666,0.9166701698615463,0.8654146155232535]}},
            {"size":[596,842,3,1788],"margin":"6ff36ae18144285bf1138dc17c42bc21c98976ade55129572ed212013a74d7c0","tail":[750,"3c009032f84d70cfddce655b5ef665fba43fb18be7fb33d89f8dc7516fd0b672"],"objects":"026f1f427c52cb083463805517b207f371f5a3dbe0cda8917f204168c96343be","total":{"marks":7,"literal":"[Total: 7]","box":[0.8468166006733107,0.8720541796202074,0.916662890051699,0.8898890682483942]}},
            {"size":[596,842,3,1788],"margin":"aa30abc9ebdb2289ff34601bba9d8957d270be4a4853dadd16661daacc2d8e83","full":"e69bf08de02e3825342774815c8ed4281038c1a138b621193304ea7d68eef308","objects":"d9f064ca2abd445c0a0e195bbd872755340110cde0ff4e2a874099d6a0227325"},
            {"size":[596,842,3,1788],"margin":"7c7b62e65e82961485e7cf1354aa69fd58f43fa9f947468e103f1f8c53c18698","full":"ed85b7b5d5f6643518cac045348d5ebda8bc84f6f3f2e2f32f165f10758bdcbe","objects":"7ed850e801099c21e35901bd5100b2f13567d92cce9d918f77f8ec3aa17755ed"}
        ]
    },
    "9702_w21_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2021/w/9702_w21_qp_22.pdf",
        "source_sha256": "649bb30eb335b1446b1a477fe8f94c858b01f6e8bbd3ab980c544aede58b425a",
        "pages": [
            {"size":[596,842,3,1788],"margin":"c2f3959f9ab61ebf7bdd6618d4e9891c0f95979e1a8308f6c962e90db840d023","full":"c74d9a6009481c91e1e5905a7c69f1987c7776ec425493acf9c61e090ee267c7","objects":"d5a357b4df84d344708a2724781e023525be406b84798436fa1bdb99b9504495"},
            {"size":[596,842,3,1788],"margin":"09310e32d619100cca1c121a6371efdb77b68b1aa3a2353d391676ffcc2b968d","full":"a85be8089fa6afec4e3de42f5d9bed51bf70528efa49312c8c5fc157eaafe042","objects":"7e9e652ba138d7cfded6ce4ea9ef182cfab7dcd1abd544a6e8fba448ee363aa5"},
            {"size":[596,842,3,1788],"margin":"982c0146ffb07e8fb133b3fc22cbd0a7e0b831286abb31bf2200b93835558920","full":"6191f32a5a881e78b0465c51129b6c7a6e72124ad222ecb36a3fb1b72d0e930c","objects":"a6610cbc030531240b10d402508e979d4ea4968d93f4e7a887a2a9f5bd7d34bb"},
            {"size":[596,842,3,1788],"margin":"7ac15e4269f9b3f62eb6bb2297725a2d26dd9cd82b6ba49eeb393cc0236dbeb5","objects":"cfcdede9d3b91b98cfafc44f12b7405af76452564a101fab1513f01308f3021b"},
            {"size":[596,842,3,1788],"margin":"5b0f9ba8d4c8f4c8ba33444d90de0de97df3f368d89ef4f15d12475aa17c5ea3","tail":[389,"3526ecf66063169b0a85fdf2bc092b50a8807c5273a1d638f0cfa21db71c18d7"],"objects":"ca38d43e1ad6012e690e1a653c62e1dd5e1ba78682eaa7a9ee069d8a6c535990","total":{"marks":6,"literal":"[Total: 6]","box":[0.846841977475243,0.44329948702021515,0.9166883181198978,0.461134375648402]}},
            {"size":[596,842,3,1788],"margin":"6ba603cd4aeb10a94670ecb5a59e3097085dddee75bba82fb6091efe53e924bd","objects":"1062038642782c0966d8efc5874abb50fcdf7b08d909f9e314b086d809a5cf29"},
            {"size":[596,842,3,1788],"margin":"e5ad915ba8163e467541e2f456b792046b402f6bc236084638a8f3c48e8140a8","tail":[781,"8fa13b45c0b3c35deded0f119fb02bf13b28eeac524b243623fe48cbf9970e29"],"objects":"f592070642e9decae074c4f9fc5c9dee84507436b768f6e74d3f6b487fb949f4","total":{"marks":14,"literal":"[Total: 14]","box":[0.8365412003401619,0.9087438556319827,0.9166617621938353,0.9265787442601696]}},
            {"size":[596,842,3,1788],"margin":"ed4aebfd3e86ba777cde12a181cd70ca6e849f4ee7c5189573c1dd97a38b1063","objects":"3a702575c4ac5cef138c9ac4a61a6a8da6aca43de01a38999c3258d31dce852e"},
            {"size":[596,842,3,1788],"margin":"eed3563be0aa38495a4ce099d1129e5364388b7e79336cd67589a7658d4a445c","tail":[597,"deb63e9b069218c8b4753d5a2ccba353f9a29ecbc897469ea1385d399237c180"],"objects":"ec824978312ec141e1c2a89696ed79581ea051fd995519eda34672fadd2948d4","total":{"marks":8,"literal":"[Total: 8]","box":[0.8468177797974409,0.690361478276113,0.9166641204420957,0.7081963669042999]}},
            {"size":[596,842,3,1788],"margin":"58ba3d1f6bcf974275c035826ee0b577f91f2070253bf27441d066ab234de7e5","objects":"192a05e00efe6f7fd70d093c058e5bf7fe54c46d6297ef448bcce818f7d755c7"},
            {"size":[596,842,3,1788],"margin":"a035456bba73c00cfa2c4986c943c649e7d2c66f0b8a42ca2d34f4fd600d532f","tail":[272,"03489b0185e660ce7f678b8e59c133533f3300fe34663290f8fb949a3a637e37"],"objects":"50841d4212dd58b97b0c00db008b9817b4c74fded115bb5b4c4c847e872a107b","total":{"marks":6,"literal":"[Total: 6]","box":[0.84680434803561,0.3043229120675888,0.9166506886802648,0.3221578006957757]}},
            {"size":[596,842,3,1788],"margin":"82555629498e64e1a587a47bb6b8e9f8dd16396fe9a46117de66be46117177ef","objects":"c8e2f5a069706e50aeb94248cc7e27545043cbc8588fcca8f94ec0557114ac53"},
            {"size":[596,842,3,1788],"margin":"fe66485b6731e70c57ab6002fa5d106aff8aa64cf07bb0c455cc6a771c554b35","tail":[220,"ea43eb7e4d2416101007eccaf37505c3d52aa001be9a3f91a6875a9c60ebe6d6"],"objects":"8d9401126fc8cfb0e34c24c68974fd64edcc15c341a162c1866a289e750fdeaa","total":{"marks":5,"literal":"[Total: 5]","box":[0.8468413110137781,0.2425606766536707,0.9166876003921665,0.2603955471574128]}},
            {"size":[596,842,3,1788],"margin":"e0dd60f17bc1609901bc45b0da2c36fc575f348c674ad0c7927197457dc43e07","objects":"3fce800cbe51b6b7672389ac83332593457b985bc4701bc682cb205926820f46"},
            {"size":[596,842,3,1788],"margin":"84e9a5dd58e6eca9537dc4957ae658f7be311a3464c80b621d8e320bfe02ca80","tail":[675,"5a2d6782c43bdeabc29f5a9a3dd0d6d2edb86fa3f08d5909bc16d82ef9a772e9"],"objects":"db6a5d799826d6a69af0e4ee08648b0664830f96622454aad38185e3280040c0","total":{"marks":11,"literal":"[Total: 11]","box":[0.8379170331350286,0.7830529336733769,0.9166683242759511,0.8008878223015637]}},
            {"size":[596,842,3,1788],"margin":"b1d951e4e8cd2a580181affa9755bc0930bdac011b65e9a6ceff06f0e0708bd0","objects":"85588aa9d349f20a1d393f60d9e15e7fef63126c202f400c5a687c7393ca6626"},
            {"size":[596,842,3,1788],"margin":"22b5879c952f10adf09999c455008acf2562232a72370c147569938e3f17fc3a","tail":[558,"a92a0497ba7f8920ad8db7eb1e67671827d7a44e8ddff5e045a476db02c7121a"],"objects":"477b48239229338832f921d1a2ab9e23494a578407be8b716224cc325a0c7594","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365370990388395,0.64431719634269,0.9166576608925129,0.662152084970877]}},
            {"size":[596,842,3,1788],"margin":"1dca22e9fc41c568d0aaf11ee6089827392d0711b07f3943324cb0e3e260aa0f","full":"9cddea69e6f102a9f51887cdf617104eec0709209d5828144beb395b7cc94c5e","objects":"eed89e65a745b04e2c6adeab42502df36d06371981655b532f6496061f164d61"},
            {"size":[596,842,3,1788],"margin":"e178d8eaf6b394992d6ff9d4b1ac527abfc394a2bc8d6c19c10a2c30fb7d7856","full":"564033d8e33a74bf954096189ad517539e5d54903f9e686ca2b89839a20b4b9a","objects":"4b21cafad8178b8b3ad37931eebf23470a2df0b0c766a21ce8ee87dcbedaf5ae"},
            {"size":[596,842,3,1788],"margin":"3fe7545948f8cc5da360544578c2ea306a74fc48cf9602894ab18ae9ea92efee","full":"6a38188bf09c1e79d35712fd6a2f0fdd7538e212d7208d69f5baecaa0276de94","objects":"3783a4f78195628de6c6de02cf86c4689cbd5e5eb12eee7ee5a9256e8956d2e9"}
        ]
    },
    "9702_s22_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2022/s/9702_s22_qp_22.pdf",
        "source_sha256": "17041e391fee955573e445dc9ffa67fd4dea8e71c771c1ef68a3dba0d6471565",
        "pages": [
            {"size":[596,842,3,1788],"margin":"45b8ec0642a429606476ace21b54a724f9bd66657a0b126ed16b5598a7a2adc3","full":"01fb513cd1739f582ac5b53f12856af9bf068d717cf9ea995305643f4c0e6662","objects":"23a9a32391001fd4225d4eb1a2928a0586d56a703e9834100d781919d5480eac"},
            {"size":[596,842,3,1788],"margin":"52d137f5d92adf0be2ecc66feaf89f07ba7f01c20b024d3f94a8fa46e3fff4dd","full":"b43100adeb85f56125aa488f0e6a221efea80c10e81bdd188a12d079994112a7","objects":"633743c6592aa62b1d79733192aa64059f8d6b92d5fb32945afeef34b48dadeb"},
            {"size":[596,842,3,1788],"margin":"a092e018c6fea1b46039f84709a07e6a72d2a90bd8214b32b1a310b23a13d282","full":"bd7dc74580d473abac67aabc80ae0f8dfe1e6a1c49ba84ef0714935ab213f045","objects":"16840635db4bfabb8154c49c83088d4f582325c84b1e6372ba5b255d1d3b9a1a"},
            {"size":[596,842,3,1788],"margin":"8ef249da887b8e20b68d95a4c7c14c24b16008e8ab94a021b91159b33ab19125","objects":"2856500fb731f550b7af29c98be32f1af21f8201e261f8fb3b5461dfbf64fe23"},
            {"size":[596,842,3,1788],"margin":"ffae124ddbcaf1331067f18631162a18f7293b7abd2671cb74a312fd11f209e6","tail":[285,"d5216c8676526caa0c77858e086c4ba26bd39f25a984945de32bea474eca2e0a"],"objects":"1fcf34d9029af6ef4e9a4be744da6851db2f50bd93d719f118731223142bb223","total":{"marks":5,"literal":"[Total: 5]","box":[0.8468167544721102,0.3197595741654454,0.916663095116765,0.3375944627936323]}},
            {"size":[596,842,3,1788],"margin":"b12e93504e8f776b09808d4fd7082d29eaae7328f1ce231c1c9f0db1f0553c61","objects":"19a7b5614505929a8c5d1b99fb86733b630fa2aff0fc0c6b410e77da0444a6c2"},
            {"size":[596,842,3,1788],"margin":"43385f80d92f6945b200124709fcc900d5d8f90d0a61271404929b5e43c8bb52","tail":[714,"d0f966188d78b2283bd0e27d57eaa2211cb0fcfb3708037fdc3bdd5242854f8f"],"objects":"7ba5069ee9c2adf029a2533690acd0c23216a82489caba0502b98024ab457e0c","total":{"marks":11,"literal":"[Total: 11]","box":[0.8379345149319153,0.8293736496382433,0.9166857548065713,0.8472085382664302]}},
            {"size":[596,842,3,1788],"margin":"bec5c8e2229aeb41da091ed29c10aa355741182f136c705fa0ecc34a56d33a35","objects":"5244a06374324674d1a292c34055f5f38047fa171523d054e6648d5fbef1c79f"},
            {"size":[596,842,3,1788],"margin":"6cf87028c5bc2edddc28377e5666fdb57f1ba3c8b856cd99d8b0358c7a2d2f3b","tail":[638,"b710696df412ff1ced8de8256f9cc0990127721ee4a3d878324125789c99cd11"],"objects":"db107c9815bc3dc870717a1579ed1ba3dac1bb17bdc651e8216df5adcdc6a46b","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365426357956248,0.7389210706530005,0.9166631976492982,0.7567559592811874]}},
            {"size":[596,842,3,1788],"margin":"8fc2e17819a591630a10148f851a4b61dca6d6119c93f0785314943a4aca6057","objects":"9f6345c56414e43541a146d149dc8ac7626e3ab1af5324111c24e3b2d8f701da"},
            {"size":[596,842,3,1788],"margin":"3d9840326f2477ee74ceb006ff2a65dc0ee7d454c3a3746e82b1e1a087c55606","tail":[311,"c7e1c849fb406ca4f72ef9e6bf8d5015a6fda45ca140c32de1f9583e2605ecff"],"objects":"471e03ca5724306b04533f12539bcca30b80a1d5f117764e41463bcbc6c0bdc3","total":{"marks":7,"literal":"[Total: 7]","box":[0.84680434803561,0.35065435770375175,0.9166506886802648,0.36848924633193864]}},
            {"size":[596,842,3,1788],"margin":"2894d536e993670ba86e9dca89203bc83c29fc0654ae889575eaea3d04242c2f","objects":"3cda97fcfb25b70af8e2a5183a97314801a84d1e7314e4a57bc99d5851b2de2e"},
            {"size":[596,842,3,1788],"margin":"7401ef1e10035e78cac8c15089a8beb3811e3dc2f5d9e336419a23f5e6685275","tail":[662,"f7c8776a1c510da76cf67244caf53572983349d5bbb02098587f5ff213034161"],"objects":"041a54d7818b00857d3fdb68c06a5db328c80e31c6aca84e206bd29be8dfd5d0","total":{"marks":11,"literal":"[Total: 11]","box":[0.8378975519537472,0.7676245363223297,0.9166488430946698,0.7854594249505167]}},
            {"size":[596,842,3,1788],"margin":"8b27891ce0c27398d89c3ff73a6ba07ce0e19a0b35f0096b63b6ce370359ba80","objects":"6c03402b1b3c0f185b25423098fec8cdb87c6e17e6feea2c1c984626df7a9994"},
            {"size":[596,842,3,1788],"margin":"13b85db8f962e0a517eba074ccdca3f130f60bf8c4cd7f6dc90db3e4498b2c01","tail":[680,"cc4c1e5a750212ddc8ed910a4ff49b0af0fc6279816ecb5cc0cd40fa91539d73"],"objects":"aa381292b9295ff617984819ef2f9a3263d9a73c320bf538a19b882cff8af712","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468192665191702,0.7886165582317386,0.9166655558975585,0.8064514468599254]}},
            {"size":[596,842,3,1788],"margin":"02d33c9e4f85c31fabf0399f8092bd4f45466239d49eb3f84a61aeb5997090f0","tail":[687,"bb71643320858ddaaa20e0bf4564251babaf09e6e2c25b6a147e7c45c80286aa"],"objects":"1c52fa5b70ab2d1f74d3d62637f03fd1527f3f1420d46aaccbb99cd64a058f40","total":{"marks":7,"literal":"[Total: 7]","box":[0.846824854542222,0.7979815313357875,0.9166711951868768,0.8158164199639744]}}
        ]
    },
    "9702_w23_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2023/w/9702_w23_qp_22.pdf",
        "source_sha256": "837fd4b472bb5b4274cb9b12549e4fa574c218452de70b534969f3397cc26a22",
        "pages": [
            {"size":[596,842,3,1788],"margin":"cdbbd4679f66c73e3236cc666afd4de2c059c3728fb75107166ae954d71eb0f4","full":"0ba48e6b0ae13d305b1aa0b4cf671c3a967d7937102167275865620843246057","objects":"418ed9b5db9fc278a786e5ae6979467653e7315182d28fda03ca8e68597833c0"},
            {"size":[596,842,3,1788],"margin":"e83ba31803ec36acaa6902d28ebf33f92fafb3de6cbf754354a6f34c5216a77b","full":"52e559d79c1bbb9cd305bec4e0569ad98b1d08fb4733326670d0dd1b9e537246","objects":"9cc7de0579b087ab02ceb856e73e447a29e3fe31c2c383168a833d0f4d46b094"},
            {"size":[596,842,3,1788],"margin":"8cbabd04ac7304c536ac516bb2f5d1ebbd6eb1299d73834acc6d7174b7804f81","full":"57a6ff8b5ae939fa5ee49604b57209c662281d310996d26f87a038b28ea62bd9","objects":"ebe7f08e9e69670a61df0827d1f836b488892fb989ab410d213d81b8e4113283"},
            {"size":[596,842,3,1788],"margin":"84e2fe4f5c260de2d4c42b49f7fe063aa5e3004e1cabe3bf35a09ac68fe3fb51","objects":"292d4913967a4b4ef8a61fc40dc18243575fcff580b9d0cd838a9bdeff20f40f"},
            {"size":[596,842,3,1788],"margin":"ee0bd3002f57c81f08504ea2414b34f8688806d602e35a9652fdbbb85b9d05ed","tail":[675,"cfbf0e1a10bb1d46256573895c6fd2fa703e5a5883979717c9a7ee8f9fda2afb"],"objects":"5b41a4757638c653e038911d8e7c549e289347a8e2476e67cf89d461dcc5f743","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468194715842363,0.7830172647660939,0.9166657609626246,0.8008521533942807]}},
            {"size":[596,842,3,1788],"margin":"07ca4c6f3eb7553779aa6ab4ff89431d816568ee571e29f65cbe3974566c411e","objects":"9675dfb1d60def3b1550fa5065e0859ec0690c441b2f698bf776936078d99425"},
            {"size":[596,842,3,1788],"margin":"0017e01a514d558a0dfbc370651dfe2b7ce5936bf3358e97663aed3ffef4d913","tail":[272,"b474ec732b9014795728f8309790b7ba59be6d7b385be582f628c98d78e6599d"],"objects":"bf793e7edf52c6b9bf797e6094ac997f10235e2b297bd7e19fd84572e8688e80","total":{"marks":8,"literal":"[Total: 8]","box":[0.8468318780207366,0.3043158072852438,0.9166781673991249,0.3221506959134307]}},
            {"size":[596,842,3,1788],"margin":"34b2143a91f2cc287807c5b7d67c05b78ff9fc24702f96657fa4a27ca76a3f44","objects":"2d4e6b9fb5c2d93a3b4464b63934bea23ed2306d40cb850ef3713395e01a0da0"},
            {"size":[596,842,3,1788],"margin":"3d949a7d99dbb7204ef77737d8800844c44e03758ab93e5c5e92bd9b4dfc621a","tail":[738,"0aa49c4ecb2ab205a2d5638550693b6783757b7e8bbda1a101341dcea0a05ed0"],"objects":"db29ea193e5d2d74f1c55c7880f2544efeab5fedae405a6302967f56029d2cc1","total":{"marks":10,"literal":"[Total: 10]","box":[0.8365423794642921,0.8580424613691959,0.916662992584232,0.8758773499973829]}},
            {"size":[596,842,3,1788],"margin":"3e557a639d19cca115ea9fc75293ab09dcd906c0ad1161b31302c47c02c8e724","objects":"421aceb9d31c8e2bc5265a620863e56e147e855d02f02f6a69a35221424beddc"},
            {"size":[596,842,3,1788],"margin":"847d32719a4162f899e08fc594939794d495e02b153a1b77a530cacbc1f28e4a","tail":[488,"73bbe68dfe3b8814e4e66f4a33183a0c9c4d572c13a4432d1391270b1cb71032"],"objects":"be6d5d601868e38fffcfbb552d8cdc81722582084f4e3f04654751002d27448a","total":{"marks":6,"literal":"[Total: 6]","box":[0.8468195228505029,0.5613978253276211,0.9166658634951577,0.579232713955808]}},
            {"size":[596,842,3,1788],"margin":"0bf71f67b0fda0f59f4455ceb5f2bed00aeb1bb87c785c73608864d86bbb5a41","objects":"f7581c1ad33fea16546bca7d2fdbf6ff75a83ad150da29c29a56bbffe9a85839"},
            {"size":[596,842,3,1788],"margin":"c2b6b2f9c59900ad2a72d3759efd908448f0f7792c083e2484647cdeeb2ca4c9","tail":[679,"3a82ce81d142f0e31fe26557e9410035ef17d13aa82c0f7301d1448916f64d0e"],"objects":"5cff12b4423882d9e8e2d3a13723a34a4d3ebfdb4e8dc317a7b626d3ebc2821a","total":{"marks":10,"literal":"[Total: 10]","box":[0.836541405405228,0.7882508794343085,0.9166619672589014,0.8060857680624954]}},
            {"size":[596,842,3,1788],"margin":"c5890780820dfce996bb4c76981203233164b02438b3f6e02312d9193fb45579","objects":"6fb578b3d9ac0b2be15005396c803093917370a3fb1b2d12601ec9b71514af5a"},
            {"size":[596,842,3,1788],"margin":"30c997cba9e8fbd2c08ecab1e4452b5ea7d2a17d4e6ddcb0f82f815f34ccc392","tail":[716,"2d0df6d02bf5702994cb40a60de7b23f98ed42e84733e0369c12bee0c212ecf0"],"objects":"8061ff1edce82e224408db3ba29f50f00654b2a4d13bda04b0ac48575c58eb27","total":{"marks":12,"literal":"[Total: 12]","box":[0.8365573492141188,0.8321674240509642,0.9166779623340587,0.850002312679151]}},
            {"size":[596,842,3,1788],"margin":"8b8b27841ebeb15bc495d6a7aad59c73fc30310263ecf4cba069f3db7f04d6c9","tail":[629,"7bf6b93930a373227c1e72b9c15e038ac4171346b500ee6f355c3c95450627a9"],"objects":"380eb8f89863403bd27fa2ec1790b37187f762cc6c99a59bedd4014631b97349","total":{"marks":5,"literal":"[Total: 5]","box":[0.8468172671347756,0.7289722004366396,0.9166636077794303,0.7468070890648265]}}
        ]
    },
    "9702_w25_22": {
        "source_reference": "Library/Courses/9702/Sources/PastPapers/9702/2025/w/9702_w25_qp_22.pdf",
        "source_sha256": "3e6384f2d529e7300023b8bb899f97ce50854005c4d5a52db1c9c40e2af3bd85",
        "pages": [
            {"size":[596,842,3,1788],"margin":"4bb6273c46b2555b8f012e682c6a44f827b2afcee9f557e2bb8a75dc5a02a1ab","full":"1ea2c9d8cb22345b4b2501bfad53d746d816789cc2b854fd2060aa8a3626a9de","objects":"3adff9350727217ecf872c1fe9b3a6d8e44d9bae7fccda6a40b31162e69de19f"},
            {"size":[596,842,3,1788],"margin":"4a3773678768b13de99d10c19c9483ac6bb66c637ef91ed35b3e58dc7f3ff2af","full":"3f489c411f7a182039415a1ee4da3637f39c8718bc412f19bb4d6074b2e900cd","objects":"76df9318a889ad9b104a11f14238c44213fc3cc5ed08e1e95ac8742cf9b55ab9"},
            {"size":[596,842,3,1788],"margin":"86dc2886c4290a6ad2cc4167e6057a8752a2f002b66643782bf2f17a863b15dc","full":"326ecbd522a11b4acabfbc1d5288cf7c2d05a7c43504d6ae8575969620e951df","objects":"def163c01d2fea5caa7a60d673c8a84b349e0969e0ddadd770da6644a1dcf793"},
            {"size":[596,842,3,1788],"margin":"12927fc07b2141c320293e1571029328d697c12f2aba0f8e0d15e0dd2029f484","objects":"d85543df729a0600fd8510eda00de7d8171006d8af4ea73db715c207c372c8eb"},
            {"size":[596,842,3,1788],"margin":"3354ecc4cc1d502234067128e71d943a836e59fc74323fd9737b676e650408a7","tail":[700,"8a5145e788540832c809da40acd2ad2b4fe48c617a3f0291e4bf5241bfc8150b"],"objects":"671a73b6e1133af4c8d13d15802ce35d64c0f3dac8c057400ca37e7ca7599fab","total":{"marks":11,"literal":"[Total: 11]","box":[0.8379737198675894,0.8172749497916486,0.9167249649979314,0.8303407933086271]}},
            {"size":[596,842,3,1788],"margin":"90b949488f7a076a5cb8bda64203fba6671425c5550a0f7407a7e844477545c8","objects":"a3dba29383cc59714007173118cc1a5f856dacd7e6d72966c0f5dc8d88339cf4"},
            {"size":[596,842,3,1788],"margin":"5dea6e2a39457fa896a17bf2125b547546e75e131495f20685ce5f0c47e224fe","objects":"d170dc49e77212525a9fe98eeb23c68434eeaec74333d3489e16e7f7566e9b0f"},
            {"size":[596,842,3,1788],"margin":"1a971317f8d6e3a8a18e4a0a3efbf90a31e665d2894e4f15d442510c02acf4c7","objects":"0e6da733a5154402e6b141d4615b86c3c5ce069808269a156ab77b17859f6966"},
            {"size":[596,842,3,1788],"margin":"0fbbf8dc9ea35e94f51c5bb8f9645b3536621f735760cb0b1fabdd2cca50335e","tail":[270,"3b5390bc6794e0d22c53ced62679cc66f3cbe994f5f4a5b15e84a3cdaa96c6b4"],"objects":"78df2f952605f87c66aa7d1146dfd225b20dc0aa6f5f55515bc26113d0534f50","total":{"marks":12,"literal":"[Total: 12]","box":[0.8366093697371936,0.3074361283506852,0.9167299890956573,0.32050197186766366]}},
            {"size":[596,842,3,1788],"margin":"14c5ccb341b9c2e7850e49c5ac32e842fdd886fd72a8cdc44466eb7ff8e952ff","objects":"5caab90b00b59fb7a60615aed174eb2d502d6ad4d8c8b7e49c352c6fddac127d"},
            {"size":[596,842,3,1788],"margin":"0ba97efa34e55b9a7a59352f9b2f9812b4ab05750652edbc0def4a0ba525e153","tail":[759,"196b8c1620b1b5bb2d3224576d16dc2037aa4ac1f8096c2166a415be99a48374"],"objects":"ed1197e5b45d45a1a58aaad7df08e6b08e46771cdd148ccc04ccd81730af810a","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468876996245769,0.8880288152656007,0.9167340903999233,0.9010946587825792]}},
            {"size":[596,842,3,1788],"margin":"8594e6cff0dcdb7729f78fdd370670c333fca46386fd91b93adc25cbf7b0a4b1","objects":"dfdcd364cb2f2519faa181a1bc959611bc375d89ed49e0a26c1c3d82f9dbd152"},
            {"size":[596,842,3,1788],"margin":"f250664e9a3a2623e220ffaa0d5a5530cd1cffee5452a6d563db7b78b8b7c9de","tail":[205,"013940cc292bd4927b2b318bcdac244358098b6ebabbbfb0a26582aac27fd9c6"],"objects":"8faab7d4db8ebe96a9c792a715ca884e60a20e25aee072096c70143badfc27af","total":{"marks":8,"literal":"[Total: 8]","box":[0.8468868280974203,0.2302479924996676,0.9167331676064634,0.24331383601664608]}},
            {"size":[596,842,3,1788],"margin":"1e3176b947b8f954ffbf800376149bb62895b470eb8d943d87094ddd577823a7","objects":"d8f4acb087d654116776395a122c0df2dc8d8097467a0897bea494629f1a3195"},
            {"size":[596,842,3,1788],"margin":"50d7dea1ce2346075227ffa7344a96070bdf34d52e030ab3bf1bf42a1a2503b1","tail":[777,"660849c68a4b55786f70e31b1dacf7018bc2deb322a6b3f85cf38d11c366c147"],"objects":"8fba0a794f6303017a3ff58195f2147daac5921edfa1218081fb43c9616d5f97","total":{"marks":11,"literal":"[Total: 11]","box":[0.8379831016010979,0.9096943478250152,0.9167343979977433,0.9227601913419937]}},
            {"size":[596,842,3,1788],"margin":"5b0acd7d2d334d9bffb74a2ac9332cc17dcbb83f494274b9d3d7ea5bba0fe090","tail":[757,"ab7834fa544fd96ab825bb4f6e2de96ec5fba544f7a72280b51663b7e4fa730e"],"objects":"a31c1ee8e86c5f74f2057591835e5c73d4a8bb3ffa37b4f8b812e9bad9cb8026","total":{"marks":9,"literal":"[Total: 9]","box":[0.8468672956358534,0.8856500174502204,0.9167136864111999,0.8987158609671989]}}
        ]
    }
}''')


def _plain(value):
    if isinstance(value,bytes):return value.hex()
    if isinstance(value,(list,tuple,pymupdf.Rect,pymupdf.Point,pymupdf.Quad)):
        return [_plain(v) for v in value]
    if isinstance(value,dict):return {k:_plain(v) for k,v in value.items()}
    return value


def _paint_fingerprint(page, regions):
    """Exact glyph/painting inventory complements finite-resolution pixels."""
    def inside(box):
        rect=pymupdf.Rect(box)*page.rotation_matrix
        rect=pymupdf.Rect(rect.x0/page.rect.width,rect.y0/page.rect.height,
                          rect.x1/page.rect.width,rect.y1/page.rect.height)
        # Strokes/points with zero-area geometry still belong to an exclusion.
        rect=rect+(-.001,-.001,.001,.001)
        return any(rect.intersects(pymupdf.Rect(region)) for region in regions)
    traces=[trace for trace in page.get_texttrace() if inside(trace['bbox'])]
    images=[info for info in page.get_image_info(hashes=True) if inside(info['bbox'])]
    drawings=[drawing for drawing in page.get_drawings() if inside(drawing['rect'])]
    annotations=[{'type':a.type,'rect':a.rect,'info':a.info,'colors':a.colors,'opacity':a.opacity}
                 for a in (page.annots() or [])]
    widgets=[{'rect':w.rect,'name':w.field_name,'type':w.field_type,'value':w.field_value}
             for w in (page.widgets() or [])]
    return _sha(canonical_bytes(_plain([traces,images,drawings,annotations,widgets])))


def _raster_witness(page, *, full=False, tail=None):
    pix=page.get_pixmap(dpi=72,alpha=False)
    raw=pix.samples;stride=pix.stride;width=pix.width;height=pix.height
    left=round(width*.06);right=round(width*.94);top=round(height*.06);bottom=round(height*.94)
    regions=[[0,0,1,top/height],[0,bottom/height,1,1],
             [0,top/height,left/width,bottom/height],[right/width,top/height,1,bottom/height]]
    edges=[raw[:top*stride],raw[bottom*stride:]]
    for y in range(top,bottom):
        edges.extend([raw[y*stride:y*stride+left*pix.n],raw[y*stride+right*pix.n:(y+1)*stride]])
    result={'size':[width,height,pix.n,stride],
            'margin':_sha(canonical_bytes([width,height,pix.n,stride])+b''.join(edges))}
    if full:
        result['full']=_sha(raw);regions=[[0,0,1,1]]
    elif tail is not None:
        result['tail']=[tail,_sha(raw[tail*stride:])];regions.append([0,tail/height,1,1])
    result['objects']=_paint_fingerprint(page,regions)
    return result


def _public_pixel_qualification(doc, exam, layout, source):
    key=f"{exam['course']}_{exam['series']}{exam['year']%100:02d}_22"
    authority=_PUBLIC_RASTER_BASELINES.get(key)
    if authority is None:
        return [],[{'source':'qp','reason':'unqualified_public_page_profile'}]
    proofs=[];issues=[]
    if len(authority['pages'])!=len(doc):
        return [],[{'source':'qp','reason':'unqualified_public_page_count'}]
    for entry,expected,page in zip(layout,authority['pages'],doc):
        observed=_raster_witness(page,full='full' in expected,
                                 tail=expected.get('tail',[None])[0])
        wanted={k:v for k,v in expected.items() if k!='total'}
        source_origin_match=source['sha256']==authority['source_sha256']
        qualified=source_origin_match and observed==wanted and ('total' not in expected or entry['totals']==[expected['total']])
        proofs.append({'page':entry['page'],'source_id':source['reference'],
            'source_sha256':source['sha256'],'registered_origin':authority['source_reference'],
            'registered_origin_sha256':authority['source_sha256'],'source_origin_match':source_origin_match,'dpi':72,
            'expected':wanted,'observed':observed,'qualified':qualified})
        if not qualified:issues.append({'source':'qp','page':entry['page'],'reason':'unqualified_public_page_content'})
    return proofs,issues


def _page_identity(doc, exam, role):
    issues=[]
    for number,page in enumerate(doc,1):
        text=' '.join(page.get_text().split())
        codes=set(re.findall(r'\b(970\d)\s*/\s*(\d{2})\b',text))
        expected={(exam['course'],exam['component'])}
        footer=set(re.findall(r'970\d/\d{2}/(M/J|O/N)/(\d{2})',text))
        sessions={(s,int(y)) for s,y in re.findall(r'(May/June|October/November)\s+(20\d{2})',text)}
        required=('May/June' if exam['series']=='s' else 'October/November',exam['year'])
        if (codes!=expected or footer and footer!={(('M/J' if exam['series']=='s' else 'O/N'),f"{exam['year']%100:02d}")}
                or sessions and sessions!={required}
                or number>1 and not (footer if role=='qp' else sessions)):
            issues.append({'source':role,'page':number,'reason':'source_page_identity_unproved'})
    return issues


def _public(doc):
    """Propose full-page roles; pinned pixel/paint proof must qualify exposure."""
    pages, anchors = [], []
    for number, page in enumerate(doc, 1):
        words = sorted(_words(page), key=_position)
        body = _body(words)
        starts = [w for w in body if re.fullmatch(r'[1-9]\d?', w['text']) and .075 < w['box'][0] < .095]
        # A whole-question numeral needs a real public part landmark on its page.
        starts = [w for w in starts if any(re.fullmatch(r'\([a-z]\)', p['text']) and .11 < p['box'][0] < .14 and p['box'][1] >= w['box'][1] - .005 for p in body)]
        totals = []
        for w in body:
            if w['text'] == '[Total:':
                suffix = [p for p in body if p['box'][0] >= w['box'][2] and abs(p['box'][1] - w['box'][1]) < .004 and re.fullmatch(r'\d+\]', p['text'])]
                if len(suffix) == 1:
                    totals.append({'marks': int(suffix[0]['text'][:-1]), 'literal': '[Total: ' + suffix[0]['text'], 'box': [w['box'][0],w['box'][1],suffix[0]['box'][2],suffix[0]['box'][3]]})
                else:
                    totals.append({'marks': None, 'literal': '[Total:', 'box': w['box']})
        text = ' '.join(page.get_text().split())
        if number == 1:
            role = 'cover'
        elif 'BLANK PAGE' in text:
            role = 'blank' if _blank_proved(page,words) else 'unexplained_public_page'
        elif (any(w['text'] in ('Data','Formulae') and .07<w['box'][0]<.12 and .06<w['box'][1]<.12 for w in body) or 'The Periodic Table of Elements' in text or 'Important values, constants and standards' in text):
            role = 'public_reference'
        else:
            role = 'question_or_continuation'
        entry = {'page': number, 'role': role, 'starts': [{'number': int(w['text']), 'box': w['box']} for w in starts], 'totals': totals, 'words': words}
        pages.append(entry)
        anchors.extend({'number': int(w['text']), 'page': number, 'box': w['box']} for w in starts)
    return pages, anchors


def _public_parts(pages):
    """Part markers and printed right-margin allocations, including unheaded pages."""
    parent = None; current = None; parts = []; reasons = []
    for page in pages:
        for word in sorted(_body(page['words']), key=_position):
            text = word['text']; x = word['box'][0]
            alpha = re.fullmatch(r'\(([a-z])\)', text) if .11 < x < .145 else None
            roman = re.fullmatch(r'\(([ivx]+)\)', text) if .145 <= x < .18 else None
            if alpha:
                parent = alpha[1]; current = parent
            elif roman:
                if parent is None:
                    reasons.append('public_orphan_subpart')
                current = (parent or '?') + '(' + roman[1] + ')'
            elif re.fullmatch(r'\[\d+\]', text) and .86 < x < .94:
                if current is None or any(p['part'] == current for p in parts):
                    reasons.append('public_missing_or_duplicate_part')
                parts.append({'part': current, 'marks': int(text[1:-1]), 'public_mark_witness': {'page': page['page'], **word}})
    return parts, reasons


def _part_label(literal):
    match = re.fullmatch(r'([1-9]\d?)(?:\(([a-z])\)|([a-z]))(?:\(([ivx]+)\))?', literal)
    if not match or match[3] and not match[4]:
        return None
    return int(match[1]), (match[2] or match[3]) + ('(' + match[4] + ')' if match[4] else '')


def _private(doc, course):
    """Displayed Question/Answer/Marks columns bind independent per-part maxima."""
    pages = []; rows = []
    for number, page in enumerate(doc, 1):
        words = sorted(_words(page), key=_position)
        headings = {label: [w for w in words if w['text'] == label and .07 < w['box'][1] < .135] for label in ('Question','Answer','Marks')}
        table = all(len(headings[label]) == 1 for label in headings)
        if table:
            qcol, acol, mcol = (headings[label][0] for label in ('Question','Answer','Marks'))
            table = (qcol['box'][2] < acol['box'][0] < mcol['box'][0] and qcol['box'][0] < .2 and mcol['box'][0] > .8)
        reasons=[]; page_rows=[]
        if table:
            labels=[]
            for w in words:
                if .13 <= w['box'][1] < .9 and qcol['box'][0] - .025 < w['box'][0] < qcol['box'][2] + .002:
                    label=_part_label(w['text'])
                    if label:labels.append((w,label))
                    else:reasons.append('unsupported_private_label')
            for index,(word,(q,part)) in enumerate(labels):
                bottom=labels[index+1][0]['box'][1]-.002 if index+1<len(labels) else .9
                witnesses=[{'page':number,**w} for w in words if mcol['box'][0] <= w['box'][0] and w['box'][2] <= mcol['box'][2]+.015 and word['box'][1]-.003 <= w['box'][1] < bottom]
                if course=='9701':
                    maximum=int(witnesses[0]['text']) if len(witnesses)==1 and re.fullmatch(r'[1-9]\d?',witnesses[0]['text']) else None
                else:
                    maximum=len(witnesses) if witnesses and all(re.fullmatch(r'[BCMA]1',w['text']) for w in witnesses) else None
                row={'number':q,'part':part,'marks':maximum,'label_witness':{'page':number,**word},'private_mark_witnesses':witnesses}
                page_rows.append(row);rows.append(row)
            role='mark_scheme'
            if not labels:reasons.append('missing_private_rows')
        else:
            text=' '.join(page.get_text().split())
            role='cover' if number==1 else 'private_guidance' if re.search(r'GENERIC MARKING PRINCIPLE|Generic Marking Principles|Science-Specific Marking Principles|Calculation|Abbreviations|Mark categories',text,re.I) else 'unexplained_private_page'
        pages.append({'page':number,'role':role,'rows':page_rows,'hold_reasons':sorted(set(reasons)), 'words':words})
    return pages,rows


def analyse(vault, qp_ref, ms_ref):
    """Read-only qualification; unsupported scopes are never silently complete."""
    library=AssetLibrary(Path(vault)); sources={}; docs={}; covers={}; exam=None
    try:
        for role,reference in [('qp',qp_ref),('ms',ms_ref)]:
            path=library.resolve(reference).relative_to(library.root).as_posix()
            identity=_identity(path,role)
            if exam is not None and exam!=identity:raise ValueError('source_pair: course/session/component mismatch')
            exam=identity
            raw=library.read(reference);docs[role]=pymupdf.open(stream=raw,filetype='pdf')
            identifier=next(key for key,value in library.records().items() if value['path']==path)
            sources[role]={'reference':path,'id':identifier,'asset_id':'asset:'+identifier,'sha256':_sha(raw),'pages':len(docs[role]),'role':role}
            covers[role]=_cover(docs[role],exam,role)
        public,anchors=_public(docs['qp']); private,rows=_private(docs['ms'],exam['course'])
        public_pixel_proofs,pixel_issues=_public_pixel_qualification(docs['qp'],exam,public,sources['qp'])
        exceptions=pixel_issues+_page_identity(docs['qp'],exam,'qp')+_page_identity(docs['ms'],exam,'ms')
        if [a['number'] for a in anchors]!=list(range(1,len(anchors)+1)) or not anchors:
            exceptions.append({'reason':'nonsequential_or_repeated_public_anchors'})
        first_table=min((p['page'] for p in private if p['role']=='mark_scheme'),default=999)
        for p in private:
            if p['role']=='private_guidance' and p['page']>=first_table:p['role']='unexplained_private_page'
            if p['role']=='unexplained_private_page':exceptions.append({'source':'ms','page':p['page'],'reason':p['role']})
        questions=[];owned=set()
        guidance=[p['page'] for p in private if p['role']=='private_guidance']
        if not guidance:exceptions.append({'reason':'private_guidance_unproved'})
        context=[p['page'] for p in public if p['role'] in ('cover','public_reference')]
        if re.search(r'\bData Booklet\b',covers['qp']['text'],re.I):
            exceptions.append({'source':'qp','page':1,'reason':'external_public_reference_unresolved'})
        for index,anchor in enumerate(anchors):
            n=anchor['number']; reasons=[]
            next_page=anchors[index+1]['page'] if index+1<len(anchors) else len(public)+1
            interval=[p for p in public if anchor['page']<=p['page']<next_page]
            totals=[(p,t) for p in interval for t in p['totals']]
            if len(totals)!=1 or totals[0][1]['marks'] is None:
                reasons.append('public_unique_total_unproved');end=next_page-1;maximum=None
            else:end=totals[0][0]['page'];maximum=totals[0][1]['marks']
            scope=[p for p in interval if p['page']<=end]
            if len(totals)==1:
                after=[w for w in _body(totals[0][0]['words']) if w['box'][1]>totals[0][1]['box'][3]+.005]
                if (after and _sha(' '.join(w['text'] for w in after).encode())!=_PUBLISHER_NOTICE_SHA256
                        or _graphics_intersect(docs['qp'][end-1],[.07,totals[0][1]['box'][3]+.005,.93,.94])):
                    reasons.append('public_content_after_total')
            if any(len(p['starts'])>1 for p in scope) or next_page==anchor['page']:
                reasons.append('shared_public_page_unproved')
            if any(p['role']!='question_or_continuation' for p in scope):reasons.append('public_scope_role_conflict')
            if any(docs['qp'][p['page']-1].rotation!=0 for p in scope):reasons.append('unsupported_public_rotation')
            owned.update(p['page'] for p in scope)
            parts,part_reasons=_public_parts(scope);reasons.extend(part_reasons)
            private_pages=[p for p in private if any(r['number']==n for r in p['rows'])]
            matches=[r for r in rows if r['number']==n]
            if not matches:reasons.append('private_question_missing')
            if any({r['number'] for r in p['rows']}!={n} for p in private_pages):reasons.append('shared_private_page_unproved')
            for p in private_pages:reasons.extend(p['hold_reasons'])
            if private_pages and [p['page'] for p in private_pages]!=list(range(private_pages[0]['page'],private_pages[-1]['page']+1)):
                reasons.append('nonconsecutive_private_scope')
            if len({r['part'] for r in matches})!=len(matches):reasons.append('repeated_private_part_unproved')
            if any(r['marks'] is None for r in matches):reasons.append('unsupported_private_scoring')
            required=[]
            if [(p['part'],p['marks']) for p in parts]!=[(r['part'],r['marks']) for r in matches]:reasons.append('public_private_parts_differ')
            else:
                required=[{**p,'label_witness':r['label_witness'],'private_mark_witnesses':r['private_mark_witnesses']} for p,r in zip(parts,matches)]
                for part in required:
                    for role,witnesses in [('qp',[part['public_mark_witness']]),('ms',[part['label_witness']]+part['private_mark_witnesses'])]:
                        for witness in witnesses:
                            witness.update(source_id=sources[role]['reference'],source_sha256=sources[role]['sha256'])
            if maximum is None or not matches or any(r['marks'] is None for r in matches) or sum(r['marks'] or 0 for r in matches)!=maximum:
                reasons.append('independent_maximum_mismatch')
            qid=f"{exam['course']}_{exam['series']}{exam['year']%100:02d}_22_q{n}"
            questions.append({'id':qid,'canonical_id':qid,'official_qid':qid,'number':n,'part':'','kind':'structured','assessment_mode':WHOLE_ASSESSMENT,
                'marks':maximum,'regions':[_region(sources['qp'],p['page']) for p in scope],
                'context_regions':[_region(sources['qp'],p) for p in context],
                'mark_scheme_regions':[_region(sources['ms'],p) for p in guidance+[p['page'] for p in private_pages]],
                'private_guidance_regions':[_region(sources['ms'],p) for p in guidance],
                'required_parts':required,'maximum_authority':{'qp':{**totals[0][1],'page':totals[0][0]['page'],'source_id':sources['qp']['reference'],'source_sha256':sources['qp']['sha256']} if len(totals)==1 else None,'ms_part_sum':sum(r['marks'] or 0 for r in matches)},'hold_reasons':sorted(set(reasons))})
        for p in public:
            if p['role']=='unexplained_public_page' or p['role']=='question_or_continuation' and p['page'] not in owned:exceptions.append({'source':'qp','page':p['page'],'reason':'unexplained_public_page'})
        if {r['number'] for r in rows}-{q['number'] for q in questions}:exceptions.append({'reason':'unknown_private_question'})
        # A physical assessment table cannot disappear merely because its part
        # labels are missing. Unknown ownership is global, never guessed from
        # adjacency or silently reclassified as private guidance.
        private_page_ownership=[]
        for p in private:
            if p['role']!='mark_scheme':continue
            declared={r['number'] for r in p['rows']}
            claims=[q for q in questions if any(r['page']==p['page'] and r['box']==[0,0,1,1]
                                               for r in q['mark_scheme_regions'])]
            owned=bool(declared) and declared=={q['number'] for q in claims}
            private_page_ownership.append({**_region(sources['ms'],p['page']),
                'question_numbers':sorted(declared),'owners':sorted({q['official_qid'] for q in claims}),'owned':owned})
            if not owned:
                exceptions.append({'source':'ms','page':p['page'],'reason':'unowned_private_assessment_page'})
                exceptions.extend({'source':'ms','page':p['page'],'reason':reason} for reason in p['hold_reasons'])
        if covers['qp']['maximum']==60:
            paper_maximum={'kind':'printed_qp_cover','maximum':60,'page':1}
        else:
            witnesses=[{'id':q['id'],**q['maximum_authority']['qp']} for q in questions if q['maximum_authority']['qp'] is not None]
            public_issues=[e for e in exceptions if e.get('source','qp')=='qp']
            public_issues += [{'reason':reason} for q in questions for reason in q['hold_reasons'] if reason in ('public_unique_total_unproved','shared_public_page_unproved','public_scope_role_conflict','unsupported_public_rotation','public_content_after_total')]
            totals_count=sum(len(p['totals']) for p in public)
            complete=(not public_issues and len(witnesses)==len(questions)==totals_count
                      and bool(witnesses) and all(type(w['marks']) is int and w['marks']>0 for w in witnesses)
                      and sum(w['marks'] for w in witnesses)==60)
            paper_maximum={'kind':'complete_qp_whole_totals','maximum':60 if complete else None,
                'question_totals':witnesses,'physical_pages':list(range(1,len(public)+1)),
                'source_id':sources['qp']['reference'],'source_sha256':sources['qp']['sha256']}
            if not complete:exceptions.append({'source':'qp','reason':'qp_paper_maximum_unproved'})
        # Global unexplained content/anchor failures cannot be bypassed by selecting Q1.
        for q in questions:q['hold_reasons']=sorted(set(q['hold_reasons']+[e['reason'] for e in exceptions]))
        ledger=[]
        for role,layout in [('qp',public),('ms',private)]:
            for p in layout:
                page=docs[role][p['page']-1]
                ledger.append({'source':sources[role]['reference'],'source_sha256':sources[role]['sha256'],'page':p['page'],'role':p['role'],
                    'rotation':page.rotation,'display_size':[page.rect.width,page.rect.height],'text_sha256':_sha(canonical_bytes(p['words'])),
                    'question_numbers':[a['number'] for a in p.get('starts',p.get('rows',[]))]})
        return {'schema_version':1,'profile':PROFILE,'exam':exam,'course':exam['course'],'title':f"{exam['course']}_{exam['series']}{exam['year']%100:02d}_22",
            'sources':sources,'covers':covers,'private_page_ownership':private_page_ownership,'public_pixel_proofs':public_pixel_proofs,'qp_paper_maximum_proof':paper_maximum,'questions':questions,'pages':ledger,'exceptions':exceptions,
            'paper_complete':not exceptions and all(not q['hold_reasons'] for q in questions),'source_verified':True,'teaching_approved':False,'mastery_certified':False}
    finally:
        for doc in docs.values():doc.close()


def _material(vault, qp_ref, ms_ref, dpi):
    if type(dpi) is not int or not 24<=dpi<=200:raise ValueError('dpi must be an integer in 24..200')
    bundle=analyse(vault,qp_ref,ms_ref);library=AssetLibrary(Path(vault));files={};media={};page_proofs=[];texts={}
    needed={}
    for q in bundle['questions']:
        for field,visibility in [('regions','public_question'),('context_regions','public_question'),('mark_scheme_regions','private_answer')]:
            names=[]
            for region in q[field]:
                name=('qp' if region['role']=='qp' else 'ms')+'/'+_sha(canonical_bytes(region))[:24]+'.png'
                needed[(region['role'],region['page'])]=(name,region,visibility);names.append(name)
            q[{'regions':'question_media','context_regions':'context_media','mark_scheme_regions':'mark_scheme_media'}[field]]=names
    for role,source in bundle['sources'].items():
        with pymupdf.open(stream=library.read(source['reference']),filetype='pdf') as doc:
            for number,page in enumerate(doc,1):
                pix=page.get_pixmap(dpi=dpi,alpha=False)
                page_proofs.append({'source':source['reference'],'source_sha256':source['sha256'],'page':number,'pixels_sha256':_sha(pix.samples),'width':pix.width,'height':pix.height})
                texts[(role,number)]=' '.join(w['text'] for w in sorted(_words(page),key=_position))
                if (role,number) in needed:
                    name,region,visibility=needed[(role,number)];png=pix.tobytes('png');files[name]=png
                    media[name]={'region':region,'visibility':visibility,'sha256':_sha(png),'bytes':len(png)}
    for q in bundle['questions']:
        q['question_text']='\n'.join(texts[(r['role'],r['page'])] for r in q['context_regions']+q['regions'])
        q['scheme_text']='\n'.join(texts[(r['role'],r['page'])] for r in q['mark_scheme_regions'])
    bundle.update(media=media,page_proofs=page_proofs,metrics={'dpi':dpi,'page_renders':len(page_proofs),'model_calls':0})
    return bundle,files


def prepare(vault, qp_ref, ms_ref, output, dpi=120):
    """Write a fresh authoring package outside the read-only source vault."""
    output=_physical(Path(output),exists=False);vault=Path(vault).resolve(strict=True)
    if output==vault or vault in output.parents or output.exists() or not output.parent.is_dir():
        raise ValueError('fresh external preparation folder required')
    descriptor,files=_material(vault,qp_ref,ms_ref,dpi)
    request={'profile':PROFILE,'qp_ref':descriptor['sources']['qp']['reference'],'ms_ref':descriptor['sources']['ms']['reference'],'dpi':dpi}
    files={'request.json':canonical_bytes(request),'caie-descriptor.json':canonical_bytes(descriptor),**files}
    output.mkdir()
    for name,raw in files.items():
        path=output/name;path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    (output/'COMPLETE').write_bytes(canonical_bytes({name:_sha(raw) for name,raw in files.items()}))
    return descriptor


def verify(vault, output, guard_holds=None):
    """Regenerate all source claims and pixels; resealing cannot change authority."""
    started=time.perf_counter();output=_physical(Path(output));request=_read_json(output/'request.json')
    if set(request)!={'profile','qp_ref','ms_ref','dpi'} or request['profile']!=PROFILE:raise ValueError('unsupported CAIE request')
    descriptor,pixels=_material(vault,request['qp_ref'],request['ms_ref'],request['dpi'])
    expected={'request.json':canonical_bytes(request),'caie-descriptor.json':canonical_bytes(descriptor),**pixels}
    actual=set()
    for path in output.rglob('*'):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):raise ValueError('unsafe preparation path')
        if path.is_file():actual.add(path.relative_to(output).as_posix())
    if actual!=set(expected)|{'COMPLETE'}:raise ValueError('preparation file inventory differs')
    for name,raw in expected.items():
        if (output/name).read_bytes()!=raw:raise ValueError('source replay differs from preparation: '+name)
    if _read_json(output/'COMPLETE')!={name:_sha(raw) for name,raw in expected.items()}:raise ValueError('preparation freeze differs')
    items=[];held=[];guard_holds=guard_holds or {}
    for q in descriptor['questions']:
        row=copy.deepcopy(q);reasons=row.pop('hold_reasons')+list(guard_holds.get(row['id'],[]))
        row.update(course=descriptor['course'],source=descriptor['title'],title=descriptor['title'],label=str(row['number']),kcs=[],source_verified=True,mastery_certified=False,teaching_approved=False)
        if reasons:held.append({'id':row['id'],'reasons':sorted(set(reasons))})
        else:items.append(row)
    return {**{k:v for k,v in descriptor.items() if k!='questions'},'items':items,'held':held,'_pixels':pixels,
        'preparation_sha256':_sha(expected['caie-descriptor.json']),
        'key_extractors':[], 'whole_source_proof':{'profile':PROFILE,'descriptor_sha256':_sha(expected['caie-descriptor.json']),
            'semantic_status':'not_checked','source_claims':copy.deepcopy(descriptor['sources'])},
        'metrics':{**descriptor['metrics'],'elapsed_seconds':time.perf_counter()-started}}
