"""Generate S1-3; all numerical results are computed here."""
import json
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/S1/S1-3.json'
K = [f'S1-3.{i}' for i in range(1, 5)]


def num(x):
    return {'value': float(x), 'unit': '', 'sf_ok': [2, 3], 'exact': True}


def item(k, stem, kind, difficulty, answer, explanation, hints, **more):
    n = len(items) + 1
    d = {'id': f'S1-3-i{n:02}', 'kcs': [k], 'kind': kind, 'difficulty': difficulty,
         'command_word': 'Calculate' if kind == 'numeric' else 'Explain' if kind == 'short' else 'Find',
         'source': {'type': 'generated'}, 'stem': stem, 'marks': 2 if kind == 'numeric' else 1,
         'explanation': explanation, 'hints': hints}
    if kind == 'numeric': d['answer'] = num(answer)
    elif kind == 'mcq': d['options'], d['answer'], d['shuffle'] = more.pop('options'), answer, True
    else: d['rubric'] = answer
    d.update(more)
    items.append(d)


mis = [
    {'id':'m1','kc':K[0],'statement':'Probability can exceed 1.','refutation':'Every probability lies between 0 and 1 inclusive.','contrast':'A probability of 1 is certain; 0 is impossible.','source':'research'},
    {'id':'m2','kc':K[1],'statement':'Adding event probabilities always gives their union.','refutation':'The overlap is counted twice and must be subtracted.','contrast':'Use $P(A\cup B)=P(A)+P(B)-P(A\cap B)$.','source':'research'},
    {'id':'m3','kc':K[2],'statement':'Mutually exclusive events with positive probabilities are independent.','refutation':'If one occurs, the other cannot: $P(B\mid A)=0$, unlike $P(B)>0$.','contrast':'Independence allows overlap and requires $P(A\cap B)=P(A)P(B)$.','source':'research'},
    {'id':'m4','kc':K[3],'statement':'Draws without replacement have identical second-draw probabilities.','refutation':'The first draw changes both the total and the composition.','contrast':'After removing a red item, use one fewer red and one fewer item overall.','source':'research'},
]

worked = []
def work(i, problem, steps, faded_problem, faded_answer):
    worked.append({'id':f'we{i}','kc':K[i], 'problem':problem,
                   'steps':[{'do':a,'why':b} for a,b in steps],
                   'faded':{'id':f'we{i}f','problem':faded_problem,'answer':num(faded_answer),'blank_from':1}})

work(1, 'Given $P(A)=3/5$, $P(B)=1/2$ and $P(A\cap B)=1/4$, calculate $P(A\cup B)$.',
     [('State $P(A\cup B)=P(A)+P(B)-P(A\cap B)$.','The intersection would otherwise be counted twice.'),
      (f'Substitute: $3/5+1/2-1/4={F(3,5)+F(1,2)-F(1,4)}$.','Use a common denominator before simplifying.')],
     'Given $P(A)=2/3$, $P(B)=1/2$, $P(A\cap B)=1/3$, calculate $P(A\cup B)$.', F(2,3)+F(1,2)-F(1,3))
work(2, 'Given $P(A)=2/5$, $P(B)=3/10$, $P(A\cap B)=3/25$, determine whether $A$ and $B$ are independent.',
     [('Calculate $P(A)P(B)=(2/5)(3/10)=3/25$.','The product criterion tests independence.'),
      ('Since $P(A\cap B)=3/25=P(A)P(B)$, the events are independent.','Equality proves the condition.')],
     'Given $P(A)=1/2$, $P(B)=1/3$ and $P(A\cap B)=1/6$, calculate $P(A)P(B)$.', F(1,6))
work(3, 'A bag contains 4 red and 3 blue counters. Two are drawn without replacement. Calculate the probability that both are red.',
     [('First red has probability $4/7$.','There are four red counters among seven.'),
      (f'After a red is removed, multiply: $(4/7)(3/6)={F(4,7)*F(3,6)}$.','The second branch is conditional on the first draw.')],
     'A bag has 5 red and 3 blue counters. Two are drawn without replacement. Calculate the probability both are red.', F(5,8)*F(4,7))

items=[]
item(K[0], 'A fair die is rolled. Calculate the probability of obtaining an even number.', 'numeric', 2, F(3,6), 'Three of the six equally likely outcomes are even, so the probability is $3/6$.', ['List the possible faces.','Count the favourable faces.','Divide that count by six.'])
item(K[0], 'A fair die is rolled. Calculate the probability of obtaining a number greater than 4.', 'numeric', 2, F(2,6), 'Only 5 and 6 qualify, so use two favourable outcomes out of six.', ['Identify the qualifying faces.','Count them.','Divide by the total number of faces.'])
item(K[0], 'State the probability of an impossible event.', 'mcq', 1, 'A', 'An impossible event has probability 0; 1 means certain.', ['Use the probability scale.','Think about the left endpoint.','Recall what zero means.'], options={'A':'0','B':'1','C':'$-1$','D':'$1/2$'}, distractors={'B':'m1','C':'m1'})
item(K[0], 'Explain why $7/6$ cannot be the probability of an event.', 'short', 2, [{'point':'A probability must be at most 1.','keywords':[['at most','less than or equal','between 0 and 1','exceeds 1']]}], 'The probability scale runs from 0 to 1, and $7/6>1$.', ['Recall the endpoints of the probability scale.','Compare the fraction with one.','Convert sixths of a whole to six sixths.'])
item(K[0], 'A fair spinner has 8 equal sectors, 3 green. Calculate the probability of green.', 'numeric', 3, F(3,8), 'Equal sectors are equally likely, so divide three green sectors by eight sectors.', ['The sectors are equally likely.','Use favourable over total.','Count the green sectors.'])
item(K[0], 'A fair coin is tossed three times. Calculate the probability that all tosses are heads.', 'numeric', 4, F(1,8), 'There are eight equally likely ordered sequences and only HHH qualifies.', ['List ordered sequences or multiply branches.','Each toss has two outcomes.','Count the sequence HHH.'])

item(K[1], 'Given $P(A)=0.68$, calculate $P(A\prime)$.', 'numeric', 2, 1-F(68,100), 'Complementary probabilities sum to 1.', ['Use the complement law.','Subtract from one.','Write $P(A\prime)=1-P(A)$.'], distractors=[{'value':float(F(68,100)),'misconception':'m2'}])
item(K[1], 'Given $P(A)=0.6$, $P(B)=0.5$ and $P(A\cap B)=0.2$, calculate $P(A\cup B)$.', 'numeric', 3, F(6,10)+F(5,10)-F(2,10), 'Subtract the overlap once from the sum.', ['Identify the overlap.','Use the addition law.','Start with $P(A)+P(B)-P(A\cap B)$.'], distractors=[{'value':float(F(6,10)+F(5,10)),'misconception':'m2'}])
item(K[1], 'Given $P(A\cap B)=0.18$ and $P(A)=0.6$, calculate $P(B\mid A)$.', 'numeric', 3, F(18,100)/F(6,10), 'Conditional probability divides the intersection by the probability of the condition.', ['Which event is the condition?','Use intersection over condition.','Divide $P(A\cap B)$ by $P(A)$.'])
item(K[1], 'Events $A$ and $B$ are mutually exclusive, with $P(A)=0.35$ and $P(B)=0.40$. Calculate $P(A\cup B)$.', 'numeric', 3, F(35,100)+F(40,100), 'Exclusive events have zero intersection, so their probabilities add.', ['What is the intersection?','Use the addition law.','Add the two probabilities.'])
item(K[1], 'Explain why $P(A\cup B)$ is not generally $P(A)+P(B)$.', 'short', 4, [{'point':'The intersection is counted twice.','keywords':[['intersection','overlap'],['twice','double']]},{'point':'Subtract the intersection once.','keywords':[['subtract','minus'],['intersection','overlap']]}], 'The overlap occurs in both event probabilities; subtract it once.', ['Imagine a Venn diagram.','Identify the region belonging to both circles.','Count how often that region appears in the sum.'])
item(K[1], 'Given $P(A)=0.7$, $P(B\mid A)=0.4$, calculate $P(A\cap B)$.', 'numeric', 4, F(7,10)*F(4,10), 'Use the product rule $P(A\cap B)=P(A)P(B\mid A)$.', ['Use the conditional product law.','Multiply a first event by a conditional probability.','Start with $P(A)P(B\mid A)$.'])

item(K[2], 'Independent events have $P(A)=0.4$ and $P(B)=0.3$. Calculate $P(A\cap B)$.', 'numeric', 2, F(4,10)*F(3,10), 'Independence makes the intersection the product of the marginal probabilities.', ['Recall the independence criterion.','Multiply the probabilities.','Use $P(A\cap B)=P(A)P(B)$.'])
item(K[2], 'Independent events have $P(B)=0.65$. Calculate $P(B\mid A)$.', 'numeric', 2, F(65,100), 'For independent events, knowing $A$ has occurred leaves $P(B)$ unchanged.', ['What does independence say about conditioning?','Compare $P(B\mid A)$ with $P(B)$.','Use their equality.'])
item(K[2], 'Given $P(A)=0.5$, $P(B)=0.4$ and $P(A\cap B)=0.2$, explain whether the events are independent.', 'short', 3, [{'point':'The intersection equals the product of the probabilities.','keywords':[['intersection','P(A∩B)'],['product','multiply','0.2']]},{'point':'The events are independent.','keywords':[['independent']]}], 'Because $0.5\\times0.4=0.2=P(A\cap B)$, the events are independent.', ['Use the product test.','Compare the given intersection with a product.','Multiply 0.5 by 0.4.'])
item(K[2], 'Two events with positive probabilities are mutually exclusive. Explain why they cannot be independent.', 'short', 4, [{'point':'Exclusivity gives zero intersection.','keywords':[['intersection','overlap'],['zero','0']]},{'point':'Independence requires a positive product.','keywords':[['product','multiply'],['positive','greater than zero']]}], 'Their intersection is zero, whereas the product of two positive probabilities is positive.', ['Compare the two definitions.','What is the intersection for exclusive events?','Can the product of two positive probabilities be zero?'])
item(K[2], 'Given $P(A)=0.2$, $P(B)=0.5$, and $P(A\cap B)=0.1$, calculate $P(B\mid A)$.', 'numeric', 3, F(1,10)/F(2,10), 'Divide the intersection by $P(A)$; equality to $P(B)$ confirms independence.', ['Use conditional probability.','Divide the intersection by the condition.','The condition here is $A$.'])
item(K[2], 'Independent events have $P(A)=0.3$ and $P(B)=0.6$. Calculate $P(A\cup B)$.', 'numeric', 4, F(3,10)+F(6,10)-F(3,10)*F(6,10), 'Find the intersection by multiplying, then subtract it in the sum law.', ['Find the overlap first.','Independence gives the overlap.','Use the addition law after multiplying.'])

item(K[3], 'A bag contains 3 red and 2 blue counters. Two are drawn without replacement. Calculate the probability of two reds.', 'numeric', 3, F(3,5)*F(2,4), 'The second draw has two red among four after a red was removed.', ['Draw two branches.','Update the composition after the first draw.','Multiply $3/5$ by the conditional second branch.'], distractors=[{'value':float(F(3,5)**2),'misconception':'m4'}])
item(K[3], 'The same bag contains 3 red and 2 blue counters. Two are drawn with replacement. Calculate the probability of two reds.', 'numeric', 3, F(3,5)**2, 'Replacement restores the original composition for the second draw.', ['Does the bag change?','Use the product law.','Each red branch has probability $3/5$.'])
item(K[3], 'A bag has 4 red and 3 blue counters. Two are drawn without replacement. Calculate the probability of red then blue.', 'numeric', 3, F(4,7)*F(3,6), 'After red is removed, three blue remain among six counters.', ['Follow one path of the tree.','Update the second-draw denominator.','Multiply $4/7$ by $3/6$.'])
item(K[3], 'A bag has 4 red and 3 blue counters. Two are drawn without replacement. Calculate the probability of one red and one blue in either order.', 'numeric', 4, F(4,7)*F(3,6)+F(3,7)*F(4,6), 'Add the probabilities of the disjoint paths red–blue and blue–red.', ['There are two orders.','Multiply along each branch, then add paths.','Write the red–blue and blue–red products.'])
item(K[3], 'Explain why a second draw without replacement depends on the first draw.', 'short', 2, [{'point':'The first draw changes the composition and total.','keywords':[['changes','alters','removes'],['composition','number of red','number of blue','total']]}], 'The first counter is removed, changing the numerator and denominator for the next branch.', ['Think about what remains in the bag.','Compare the counts before and after the first draw.','A removed counter reduces the total by one.'])
item(K[3], 'A Venn diagram has 12 outcomes in $A$ only, 5 in both $A$ and $B$, and 8 in $B$ only. There are 40 equally likely outcomes overall. Calculate $P(A\cup B)$.', 'numeric', 4, F(12+5+8,40), 'The union is all regions inside either circle, counted once.', ['Shade both circles.','Add their disjoint regions.','Count 12, 5 and 8 outcomes.'])

pack={'subtopic':'S1-3','spec':'S1','version':1,'note':'Subjects/Maths/S1 Statistics 1/3 Probability.md',
      'outline':'Elementary probability assigns values from $0$ to $1$ to events. For equally likely outcomes, count favourable outcomes over all outcomes. The sample space lists every possible outcome. Complements satisfy $P(A\prime)=1-P(A)$; a union satisfies $P(A\cup B)=P(A)+P(B)-P(A\cap B)$. Conditional probability gives $P(A\cap B)=P(A)P(B\mid A)$. Independent events satisfy $P(B\mid A)=P(B)$ and $P(A\cap B)=P(A)P(B)$. In a tree, multiply along branches and add disjoint routes. With replacement, probabilities remain the same; without replacement, update the second branch. Venn diagrams make intersections and unions visible.',
      'misconceptions':mis,'worked':worked,'items':items,
      'flashcards':[{'id':'fc1','kc':K[0],'front':'What is the probability of an event for equally likely outcomes?','back':'Number of favourable outcomes divided by the total number of equally likely outcomes.'},
                    {'id':'fc2','kc':K[0],'front':'What is the probability scale?','back':'An impossible event has probability 0, a certain event has probability 1, and every probability lies between 0 and 1 inclusive.'}],
      'diagrams':[]}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=1)+'\n')
print(f'{OUT}: {len(items)} items, {len(worked)} worked')
