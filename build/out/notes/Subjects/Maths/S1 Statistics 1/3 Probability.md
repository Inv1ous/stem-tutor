---
tags: [stem-tutor/lesson, S1]
spec: "S1"
subtopic: "S1-3"
kcs: ["S1-3.1", "S1-3.2", "S1-3.3", "S1-3.4"]
---
# 3 Probability
> [!abstract] In one breath
> Probability measures how likely an event is, from 0 (impossible) to 1 (certain). To combine events, distinguish overlap, conditioning, and independence before choosing a rule.

## Key ideas
The **sample space** is the set of all possible outcomes. An **event** is a subset of that space. When outcomes are equally likely, $P(A)=\text{number of outcomes in }A\div\text{number in the sample space}$. For example, a fair die has six equally likely outcomes, so $P(\text{even})=3/6=1/2$. The formula is not valid when outcomes have different chances. Every probability satisfies $0\le P(A)\le1$.

The **complementary event** $A'$ means that $A$ does not occur. The two possibilities exhaust the sample space, so $P(A')=1-P(A)$. **Mutually exclusive** events cannot happen together: $P(A\cap B)=0$. For any two events, the **sum law** is $P(A\cup B)=P(A)+P(B)-P(A\cap B)$. The subtraction removes the overlap counted twice. A Venn diagram makes this visible: the central region is $A\cap B$, while every region inside either circle is $A\cup B$.

**Conditional probability** $P(B\mid A)$ is the chance of $B$ given that $A$ occurred. The sample space is restricted to $A$, giving $P(B\mid A)=P(A\cap B)/P(A)$ when $P(A)>0$. Rearranging gives the **product law** $P(A\cap B)=P(A)P(B\mid A)$. The order can be reversed: $P(A\cap B)=P(B)P(A\mid B)$.

Events are **independent** when knowing one occurred does not change the probability of the other: $P(B\mid A)=P(B)$ or $P(A\mid B)=P(A)$, when the conditions have positive probability. Equivalently, $P(A\cap B)=P(A)P(B)$. Independence differs from mutual exclusivity. Two mutually exclusive events with positive probabilities have zero intersection, but their product is positive.

## Method
1. Define each event and list the sample space when it is short enough. Decide whether outcomes are equally likely.
2. For a Venn problem, put the intersection in first. Fill the exclusive regions next, then the outside region. Use the sum law for a union and subtract from one for a complement.
3. For a tree diagram, label branches with probabilities conditional on the preceding draws. Multiply along each path to get an intersection. Add separate paths for an event that can occur in several orders.
4. With replacement, the bag returns to its original composition after each draw. Without replacement, reduce the total and the count of the drawn type before labelling the next branch.
5. Test independence by comparing $P(A\cap B)$ with $P(A)P(B)$. Never assume it merely because the events sound unrelated.

> [!example]- Worked example
> A bag has four red and three blue counters. Two are drawn without replacement. Calculate the probability of one red and one blue.
> The orders are red then blue, or blue then red. Along each route, multiply the branch probabilities:
> $$P(RB)=\frac47\times\frac36=\frac27,\qquad P(BR)=\frac37\times\frac46=\frac27.$$
> The routes are mutually exclusive, so add them: $P(\text{one of each})=2/7+2/7=4/7$.

## Traps
- **Trap:** Add $P(A)+P(B)$ for every union. **Why it's wrong:** The overlap is counted twice. **Instead:** Subtract $P(A\cap B)$ once.
- **Trap:** Treat mutually exclusive events as independent. **Why it's wrong:** Occurrence of one rules out the other. **Instead:** Use the product test for independence.
- **Trap:** Keep the same fractions after a draw without replacement. **Why it's wrong:** Both the total and one colour count change. **Instead:** Update the second branch from what remains.

## Exam technique
For **Calculate** and **Find**, show the probability rule before substituting values; this earns method credit. For **Show that**, present every step until the supplied result follows. For **Explain**, use the distinction in context: say whether a first draw changes the next probability, or whether an overlap was counted twice. Leave exact fractions when a decimal would repeat, and check that the final probability lies between 0 and 1.

## Links
Builds on [[1 Modelling in probability and statistics]] · Leads to [[4 Discrete random variables]]
