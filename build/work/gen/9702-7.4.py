import json
from pathlib import Path
S='9702-7.4'; K=lambda n:f'{S}.{n}'
root=Path(__file__).resolve().parents[3]
bank={q['id']:q for q in json.loads((root/'build/work/mcq/9702.tagged.json').read_text())}
mis=[
 {'id':'m1','kc':K(1),'statement':'Different electromagnetic regions travel at different speeds in free space.','refutation':'Every electromagnetic wave travels at the same speed c in free space.','contrast':'Wavelength and frequency differ, but their product is c.','source':'ER 9702 w20 P13 Q26'},
 {'id':'m2','kc':K(2),'statement':'Microwaves with centimetre wavelengths are radio waves.','refutation':'The approximate microwave range is 1 mm to 30 cm; radio wavelengths are roughly 30 cm to 100 km.','contrast':'2.1 cm is microwave.','source':'ER 9702 s23 P13 Q23'},
 {'id':'m3','kc':K(3),'statement':'A 500 nm wavelength is ultraviolet.','refutation':'Visible light spans approximately 400–700 nm in free space.','contrast':'500 nm is visible; 300 nm is ultraviolet.','source':'ER 9702 w22 P12 Q25'},
 {'id':'m4','kc':K(2),'statement':'Increasing wavelength also means increasing frequency.','refutation':'In free space c=fλ, so frequency falls as wavelength rises.','contrast':'Gamma rays have shortest wavelengths and highest frequencies.','source':'ER 9702 s21 P13 Q26'}]
p={'subtopic':S,'spec':'9702','version':1,'note':'Subjects/9702 Physics/07 Waves/7.4 Electromagnetic spectrum.md','outline':'All electromagnetic waves are transverse and travel at $c=3.00\\times10^8\\ \\mathrm{m\\,s^{-1}}$ in free space. Their wavelength increases in the order gamma rays, X-rays, ultraviolet, visible light, infrared, microwaves, radio waves. Visible wavelengths are about 400–700 nm. In free space $c=f\\lambda$ links wavelength and frequency: longer wavelength means lower frequency.','misconceptions':mis,'worked':[],'items':[],'flashcards':[],'diagrams':[]}
for n,front,back in [(1,'State the nature and free-space speed of all electromagnetic waves.','All electromagnetic waves are transverse waves and travel with the same speed $c=3.00\\times10^8\\ \\mathrm{m\\,s^{-1}}$ in free space.'),(2,'State the order of the principal electromagnetic regions from longest to shortest wavelength.','Radio waves, microwaves, infrared, visible light, ultraviolet, X-rays, gamma rays.'),(3,'State the wavelength range of visible light in free space.','Approximately 400–700 nm.')]:p['flashcards'].append({'id':f'fc{n}','kc':K(n),'front':front,'back':back})
ids=['9702_w23_12_q23','9702_w22_13_q24','9702_w22_12_q25','9702_w21_13_q26','9702_w21_12_q26','9702_w20_13_q26','9702_s23_13_q23','9702_s23_12_q23','9702_s21_13_q26','9702_s21_11_q25','9702_w24_13_q25','9702_s22_11_q25']
exps={
ids[0]:'$5.2\\times10^{-7}$ m is 520 nm, visible. For Y, $\\lambda=c/f=0.0319$ m, microwave. A wrongly classifies the wavelengths.',
ids[1]:'0.5 μm is 500 nm, within 400–700 nm. The 5.0 μm in B is infrared.',
ids[2]:'$5.0\\times10^{-7}$ m is 500 nm, visible; 0.05 m is microwave. A mistakes visible light for ultraviolet.',
ids[3]:'All bumps must be smaller than even the shortest visible wavelength, about 400 nm, so 350 nm is the largest listed possibility. The 720 nm in C is too large.',
ids[4]:'$\\lambda=c/f=3.00\\times10^8/(30\\times10^{12})=1.0\\times10^{-5}$ m, infrared. D would place this wavelength in visible light.',
ids[5]:'Microwaves and visible light travel at the same speed in the near-vacuum between satellites; the equal distance takes time T. A incorrectly compares wavelengths as if they set speeds.',
ids[6]:'2.1 cm lies in the approximate 1 mm to 30 cm microwave range. C wrongly treats a centimetre wave as radio.',
ids[7]:'$\\lambda=c/f=600$ nm, inside the visible interval. C has a frequency far below visible light.',
ids[8]:'Gamma rays have the shortest wavelength, then X-rays, visible light and microwaves. A reverses the wavelength order.',
ids[9]:'X-rays and microwaves share speed X in vacuum; X-rays have a wavelength about $10^{-8}$ times the microwave wavelength Y. C incorrectly assigns a different speed.',
ids[10]:'$10^{-8}$ m is ultraviolet. A puts $10^{-9}$ m in gamma rays, although it is normally X-ray.',
ids[11]:'$5.0\\times10^{-6}$ m is infrared and is invisible. B incorrectly claims different free-space speeds.'}
for j,qid in enumerate(ids,1):
 q=bank[qid]; d={}
 if qid==ids[3]:d={'C':'m3'}
 if qid==ids[5]:d={'A':'m1'}
 if qid==ids[6]:d={'C':'m2'}
 if qid==ids[8]:d={'A':'m4'}
 if qid==ids[2]:d={'A':'m3','C':'m3'}
 it={'id':f'{S}-p{j:02d}','kcs':q['kcs'],'kind':'mcq','difficulty':3,'command_word':None,'source':{'type':'past','ref':q['ref'],'qid':qid},'stem':q['stem'],'options':q['options'],'answer':q['answer'],'marks':1,'explanation':exps[qid],'hints':['Recall the relevant wavelength interval or wave property.','Convert all quantities to SI units where needed.','Compare with the visible range and the spectrum order.'],'distractors':d}
 if q.get('image'):it['image']=q['image']
 p['items'].append(it)
# Generated recall and transfer questions cover every KC; answers and options come from data.
gen=[
(1,'State the direction of oscillation in an electromagnetic wave relative to its direction of travel.','The oscillations are perpendicular to the direction of travel.'),
(1,'State the speed of radio waves in free space.','$3.00\\times10^8\\ \\mathrm{m\\,s^{-1}}$.'),
(1,'Explain why a microwave pulse and a visible-light pulse take equal times across the same distance in free space.','Both are electromagnetic waves and travel at the same speed $c$ in free space.'),
(1,'State whether electromagnetic waves can be polarised, and give the reason.','Yes. They are transverse waves, so they can be polarised.'),
(1,'Describe one property common to gamma rays and radio waves in free space.','Both are transverse electromagnetic waves travelling at the same speed $c$.'),
(1,'Explain why a lower-frequency electromagnetic wave in free space need not travel more slowly.','All electromagnetic waves have speed $c$ in free space. Its longer wavelength compensates for its lower frequency in $c=f\\lambda$.'),
(2,'State the electromagnetic regions in order of increasing wavelength.','Gamma rays, X-rays, ultraviolet, visible light, infrared, microwaves, radio waves.'),
(2,'Identify the principal region for a free-space wavelength of 10 μm.','Infrared.'),
(2,'Identify the principal region for a free-space wavelength of 1 nm.','X-rays.'),
(2,'Identify the principal region for a free-space wavelength of 2 cm.','Microwaves.'),
(2,'Compare the wavelengths and frequencies of ultraviolet and infrared in free space.','Ultraviolet has shorter wavelength and higher frequency than infrared.'),
(2,'Explain why gamma rays have higher frequency than radio waves in free space.','Gamma rays have much shorter wavelength; since $c=f\\lambda$ is constant, their frequency is higher.'),
(3,'State the approximate wavelength interval visible to the human eye in free space.','400–700 nm.'),
(3,'Identify whether 550 nm radiation is visible to the human eye.','Yes, 550 nm lies within 400–700 nm.'),
(3,'Identify whether 750 nm radiation is visible to the human eye.','No. 750 nm is beyond the red end of visible light, in infrared.'),
(3,'Give the visible wavelength range in micrometres.','0.4–0.7 μm.'),
(3,'Explain why 0.5 μm radiation is visible.','0.5 μm is 500 nm, within the visible range of 400–700 nm.'),
(3,'Determine whether a free-space wavelength of $3.0\\times10^{-7}$ m is visible.','No. It is 300 nm, shorter than the visible range and in ultraviolet.')]
for j,(n,stem,answer) in enumerate(gen,1):
 p['items'].append({'id':f'{S}-i{j:02d}','kcs':[K(n)],'kind':'short','difficulty':4 if 'Explain' in stem or 'Compare' in stem else 2,'command_word':stem.split()[0],'source':{'type':'generated'},'stem':stem,'marks':1,'rubric':[{'point':answer,'keywords':[[w] for w in (['transverse'] if n==1 else ['wavelength'] if n==2 and 'Compare' in stem else ['visible'] if n==3 and 'visible' in answer.lower() else [answer.strip('.$')])]}],'explanation':answer,'hints':['Recall the spectrum order or common wave property.','Use $c=f\\lambda$ or convert the wavelength unit if needed.','Recall the approximate wavelengths at the violet and red ends of the visible spectrum, and express the interval in nanometres.']})
# Computed numeric transfer item and its wrong-unit distractor.
c=3.00e8; f=5.0e14; lam=c/f; assert abs(lam-600e-9)<1e-20
p['items'].append({'id':f'{S}-i{len(gen)+1:02d}','kcs':[K(3)],'kind':'numeric','difficulty':4,'command_word':'Calculate','source':{'type':'generated'},'stem':'Calculate the wavelength in nm of electromagnetic radiation of frequency $5.0\\times10^{14}$ Hz in free space.','marks':2,'answer':{'value':lam*1e9,'unit':'nm','sf_ok':[2,3]},'distractors':[{'value':lam*1e6,'misconception':'m3'}],'explanation':'Using $\\lambda=c/f$ gives $6.0\\times10^{-7}$ m, or 600 nm, which is visible.','hints':['Recall the speed-frequency-wavelength relation.','Rearrange for wavelength and use the free-space value of $c$.','Convert the result in metres to nanometres.']})
out=root/'build/out/packs/9702/9702-7.4.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(p,ensure_ascii=False,indent=1))
