import json, math
from pathlib import Path
SUB='9702-8.4'; K1=SUB+'.1'; K2=SUB+'.2'
root=Path(__file__).resolve().parents[3]
pack_path=root/'build/out/packs/9702/9702-8.4.json'
bank={q['id']:q for q in json.loads((root/'build/work/mcq/9702.tagged.json').read_text())}
num=lambda x,u='m': {'value':x,'unit':u,'sf_ok':[2,3]}
mis=[
 {'id':'m1','kc':K1,'statement':'The angle between symmetric maxima is the diffraction angle.','refutation':'The diffraction angle is measured from the central direction to one maximum, half the angle between symmetric maxima.','contrast':'one-sided angle versus full separation','source':'ER 9702 s23 P11 Q29'},
 {'id':'m2','kc':K1,'statement':'The highest order is the total number of spots.','refutation':'Count positive and negative orders and the central zero order: 2n_max+1.','contrast':'order versus total spots','source':'ER 9702 w23 P12 Q29'},
 {'id':'m3','kc':K1,'statement':'The grating spacing equals the screen distance.','refutation':'Spacing d is between adjacent lines; screen distance is used only to find the angle.','contrast':'microscopic spacing versus screen distance','source':'ER 9702 s23 P12 Q29'},
 {'id':'m4','kc':K1,'statement':'A screen displacement divided by screen distance is sin theta.','refutation':'The ratio is tan theta; use the right triangle before the grating equation.','contrast':'tan theta versus sin theta','source':'ER 9702 s23 P12 Q29'},
 {'id':'m5','kc':K2,'statement':'A larger line density means a larger grating spacing.','refutation':'d is the reciprocal of the number of lines per metre.','contrast':'spacing versus line density','source':'ER 9702 w20 P12 Q30'}]
worked=[
 {'id':'we1','kc':K1,'problem':'Calculate the wavelength for a second-order maximum at 40° using a grating of 500 lines per mm.', 'steps':[
  {'do':'Convert the line density to 500000 lines per metre, so $d=1/(500000)=2.0\\times10^{-6}\\,\\mathrm{m}$.','why':'The equation uses the separation between adjacent lines, in metres.'},
  {'do':'Use $d\\sin\\theta=n\\lambda$ with $n=2$ and $\\theta=40^\\circ$.','why':'The order and one-sided diffraction angle identify the maximum.'},
  {'do':f'$\\lambda=(2.0\\times10^{{-6}})\\sin40^\\circ/2={2e-6*math.sin(math.radians(40)):.3g}\\,\\mathrm{{m}}$.','why':'Rearrange for wavelength and give an SI unit.','check':{'kind':'numeric','answer':num(2e-6*math.sin(math.radians(40))/2)}}],
  'faded':{'id':'we1f','problem':'Calculate wavelength for a first-order maximum at 30° with 400 lines per mm.','answer':num((1/400000)*math.sin(math.radians(30))),'blank_from':1}},
 {'id':'we2','kc':K2,'problem':'Describe how to determine the wavelength of laser light using a grating with 300 lines per mm when first-order spots are 1.20 m either side of the centre on a screen 2.00 m away.', 'steps':[
  {'do':'Direct the laser normally at the grating and mark the central and symmetric first-order maxima.','why':'Normal incidence and the central direction set the angle reference.'},
  {'do':'Measure screen distance $L$ and each first-order displacement $y$; use $\\theta=\\tan^{-1}(y/L)$.','why':'The right triangle gives tan, not sin, of the angle.'},
  {'do':'Find $d=1/(300000)\\,\\mathrm{m}$ and calculate $\\lambda=d\\sin\\theta/n$ with $n=1$.','why':'Line density must be inverted to obtain spacing.'},
  {'do':f'$\\lambda=(1/300000)\\sin(\\tan^{{-1}}(1.20/2.00))={((1/300000)*1.2/math.hypot(1.2,2)):.3g}\\,\\mathrm{{m}}$.','why':'Use the measured angle and grating equation.','check':{'kind':'numeric','answer':num((1/300000)*1.2/math.hypot(1.2,2))}}],
  'faded':{'id':'we2f','problem':'With 500 lines per mm, screen distance 2.00 m and a first-order spot 0.80 m from centre, calculate wavelength.','answer':num((1/500000)*.8/math.hypot(.8,2)),'blank_from':2}}]
exps={
 '9702_w20_12_q30':'Increasing frequency decreases wavelength, so more integer orders may satisfy $n\\lambda\\le d$. D makes $d$ smaller and tends to reduce the available orders.',
 '9702_s21_12_q29':'The overlap is second order for 630 nm and third order for 420 nm; $d=2(630\\,\\mathrm{nm})/\\sin31^\\circ\\approx2.4\\,\\mathrm{\\mu m}$. A misses the order factor.',
 '9702_w21_12_q30':'Each second-order ray is 40° from the centre, so line density is $\\sin40^\\circ/(2\\times5.5\\times10^{-7})\\approx5.8\\times10^5\\,\\mathrm{m^{-1}}$. C uses the full 80°.',
 '9702_s22_11_q30':'The maximum order is $\\lfloor d/\\lambda\\rfloor=3$, giving three spots on each side plus the centre: 7. A counts only one side.',
 '9702_s22_13_q31':'$d=(300000)^{-1}\\,\\mathrm{m}$ gives maximum order 8; both sides and zero order give 17. A counts only one side.',
 '9702_w22_13_q29':'Known line spacing and measured diffraction angle yield wavelength from $d\\sin\\theta=n\\lambda$. Intensity depends on source and setup and is not determined by this angle equation.',
 '9702_s23_11_q29':'The diffraction angle is 55°, half the angle between second-order spots. Hence $\\lambda=d\\sin55^\\circ/2=4.1\\times10^{-7}\\,\\mathrm{m}$; B uses 110°.',
 '9702_s23_12_q29':'Use $\\tan\\theta=0.75/3.5$, then $d=3(550\\,\\mathrm{nm})/\\sin\\theta\\approx7.9\\times10^{-6}\\,\\mathrm{m}$. A treats third order as first.',
 '9702_s23_13_q29':'Here $\\sin\\theta=3(600\\,\\mathrm{nm})/(2.0\\times10^{-6}\\,\\mathrm{m})=0.90$. The full screen width is $2(1.50)\\tan\\theta\\approx6.2\\,\\mathrm{m}$; C forgets to double.',
 '9702_w23_11_q29':'At the same angle $2(720\\,\\mathrm{nm})=3\\lambda_X$, so $\\lambda_X=480\\,\\mathrm{nm}$. C reverses the order ratio.',
 '9702_w23_12_q29':'$d/\\lambda=1/(300000\\times690\\times10^{-9})\\approx4.83$, so orders 1–4 occur on each side plus zero: 9 spots. A counts just one side.',
 '9702_w23_13_q29':'Each first-order maximum is 30° from centre; $\\lambda=d\\sin30^\\circ=575\\,\\mathrm{nm}$. A halves the resulting wavelength.'}
ids=list(exps)
items=[]
for i,qid in enumerate(ids,1):
 q=bank[qid]
 items.append({'id':f'{SUB}-p{i:02d}','kcs':[K2] if qid=='9702_w22_13_q29' else [K1], 'kind':'mcq','difficulty':3 if qid=='9702_w22_13_q29' else 4,'command_word':'Determine','source':{'type':'past','ref':q['ref']},'stem':q['stem'],'options':q['options'],'answer':q['answer'],'image':q.get('image'),'marks':1,'explanation':exps[qid],'distractors':({'A':'m2','B':'m2','C':'m2'} if qid in ['9702_s22_11_q30','9702_s22_13_q31','9702_w23_12_q29'] else {})})
def short(i,k,word,stem,points,diff=2):
 items.append({'id':f'{SUB}-i{i:02d}','kcs':[k],'kind':'short','difficulty':diff,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':len(points),'rubric':[{'point':p,'keywords':keys} for p,keys in points], 'explanation':' '.join(p for p,_ in points),'hints':['Identify the quantity or observation involved.','Link it to the grating equation or the measurement geometry.','State the first relation or measurement needed.']})
short(1,K1,'State','State the diffraction grating equation and identify $d$, $n$, and $\\theta$.',[('$d\\sin\\theta=n\\lambda$, where $d$ is adjacent-line spacing, $n$ is order, and $\\theta$ is the angle from the central direction.',[['spacing','separation'],['order'],['angle']])])
short(2,K1,'Explain','Explain why the fourth-order maximum may be absent even when the third-order maximum is present.',[('A fourth-order maximum requires $4\\lambda/d\\le1$; if this exceeds one, no real diffraction angle exists.',[['fourth','4'],['sin','angle']])],4)
short(3,K2,'Describe','Describe how a diffraction grating can be used to determine the wavelength of monochromatic light.',[('Illuminate the grating normally and locate the central and an order-n maximum.',[['grating'],['central','zero']]),('Find line spacing from the stated line density and measure diffraction angle from the central direction.',[['spacing','density'],['angle']]),('Calculate wavelength using $\\lambda=d\\sin\\theta/n$.',[['wavelength'],['sin']])],4)
short(4,K2,'Explain','Explain why measuring corresponding maxima on both sides helps in a grating wavelength experiment.',[('The angle between them is twice the single diffraction angle, so halving it gives $\\theta$ and symmetric measurements reduce centring error.',[['half','halving','divide'],['angle']])],3)
short(5,K2,'Describe','Describe how to obtain the diffraction angle when a screen is used.',[('Measure screen distance $L$ and transverse displacement $y$ from the central maximum, then use $\\theta=\\tan^{-1}(y/L)$.',[['screen'],['displacement','distance'],['tan']])],3)
short(6,K2,'Explain','Explain how line density in lines per millimetre is converted to grating spacing in metres.',[('Multiply the line density by 1000 to get lines per metre, then take its reciprocal to find $d$ in metres.',[['1000','thousand'],['reciprocal','inverse']])],2)
short(7,K2,'Suggest','Suggest a way to improve the reliability of a measured wavelength using several diffraction orders.',[('Measure angles for corresponding maxima on both sides and several orders; calculate wavelength for each and average.',[['both','sides','symmetrical'],['average','mean']])],3)
# Parametric questions compute answers and distractors through expressions.
def template(i,k,stem,params,derived,answer,dist,unit='m'):
 items.append({'id':f'{SUB}-i{i:02d}','kcs':[k],'kind':'numeric','difficulty':4,'command_word':'Calculate','source':{'type':'generated'},'stem':stem,'marks':3,'answer':{'unit':unit,'sf_ok':[2,3]},'template':{'params':params,'derived':derived,'answer':answer,'distractors':dist,'constraints':[]},'explanation':'Convert line density to spacing; use the one-sided angle and $d\\sin\\theta=n\\lambda$.','hints':['Find the order and identify the grating spacing.','Convert the line density to lines per metre and take its reciprocal.','Substitute the one-sided angle into $d\\sin\\theta=n\\lambda$.']})
template(8,K1,'Calculate the wavelength in metres for order [[n]] at [[angle]]° with [[density]] lines per mm.',{'n':{'choices':[1,2,3]},'angle':{'choices':[20,30,40]},'density':{'choices':[200,300,400]}},{'d':'1/(density*1000)','rad':'angle*pi/180'},'d*sin(rad)/n',[{'expr':'d*sin(rad)*2','misconception':'m1'},{'expr':'d*sin(rad)/(n+1)','misconception':'m1'}])
template(9,K2,'Calculate the wavelength in metres from a first-order spot [[y:.2f]] m from the centre on a screen [[L:.2f]] m away. The grating has [[density]] lines per mm.',{'y':{'choices':[0.6,0.8,1.0]},'L':{'choices':[1.5,2.0,2.5]},'density':{'choices':[200,300,400]}},{'d':'1/(density*1000)','s':'y/sqrt(y*y+L*L)'},'d*s',[{'expr':'d*y/L','misconception':'m4'},{'expr':'d*s/2','misconception':'m1'}])
pack={'subtopic':SUB,'spec':'9702','version':1,'note':'Subjects/9702 Physics/08 Superposition/8.4 The diffraction grating.md','outline':'A diffraction grating has regular adjacent-line spacing $d$. Bright maxima at angle $\\theta$ from the central direction obey $d\\sin\\theta=n\\lambda$, where $n$ is an integer order. Use $d$ as the reciprocal of lines per metre. For wavelength measurement, illuminate normally, measure the angle to an identified order, and calculate $\\lambda=d\\sin\\theta/n$. A screen displacement gives $\\tan\\theta=y/L$.','misconceptions':mis,'worked':worked,'items':items,'flashcards':[{'id':'fc1','kc':K1,'front':'State the diffraction grating equation and define its symbols.','back':'$d\\sin\\theta=n\\lambda$: $d$ is spacing of adjacent lines, $\\theta$ is angle from the zero-order direction, $n$ is integer order and $\\lambda$ is wavelength.'}],'diagrams':[]}
pack_path.parent.mkdir(parents=True,exist_ok=True)
pack_path.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(items),len(worked))
