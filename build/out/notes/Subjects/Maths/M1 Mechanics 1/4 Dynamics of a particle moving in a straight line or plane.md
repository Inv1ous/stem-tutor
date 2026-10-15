---
tags: [stem-tutor/lesson, edexcel-m1]
spec: "M1"
subtopic: "M1-4"
kcs: ["M1-4.1", "M1-4.2", "M1-4.3", "M1-4.4"]
---
# 4 Dynamics of a particle moving in a straight line or plane
> [!abstract] In one breath
> A resultant force changes a particle's velocity according to Newton's laws. Force diagrams, signed directions and separate motion phases turn connected particles, inclines, friction and collisions into equations.

## Key ideas
A **force** is a push or pull on a body, measured in newtons. Newton's **first law** says a body remains at rest or moves with constant velocity when its resultant force is zero. The **second law**, for constant mass, is $\sum\mathbf F=m\mathbf a$: acceleration follows the resultant force. In a plane, apply this separately to the $\mathbf i$ and $\mathbf j$ components. Newton's **third law** says interacting bodies exert equal and opposite forces on each other. The pair acts on different bodies, so it does not cancel in one body's force equation.

For **connected particles** joined by a light inextensible string over a smooth fixed **pulley** or peg, the taut string has one **tension** and the particles share an acceleration magnitude. Draw a separate force diagram for each; tension cancels when the equations are added. If a particle hits the ground, find its velocity at contact, then set up a new force equation for any later motion. The string may become slack.

On an **inclined plane** at angle $\theta$, weight has component $mg\sin\theta$ down the plane and $mg\cos\theta$ into it. Without other perpendicular forces, the **normal reaction** is $R=mg\cos\theta$. A smooth plane has no friction. On a **rough surface**, a moving particle experiences friction of magnitude $F=\mu R$, opposing its motion. This coefficient of friction rule applies while the particle slides; do not assume friction points downhill.

The diagram shows a particle **sliding up** the plane (towards the upper right): friction $F$ therefore points down the plane. Weight $mg$ is vertical and $R$ is perpendicular to the surface. Resolve weight as $mg\sin\theta$ down the plane and $mg\cos\theta$ into it when writing equations; these are components of weight, not two extra forces.

![[Assets/M1/M1-4-incline-forces.svg]]

**Momentum** is $p=mv$ and has the sign of velocity along a chosen line. **Impulse** is $J=\Delta p=m(v-u)$, the impulse–momentum principle. For a **direct collision** between two particles with negligible external impulse, total signed momentum before equals total signed momentum after. Kinetic energy need not be conserved, and no restitution law is needed here. Use $g=9.8\,\mathrm{m\,s^{-2}}$ throughout.

For a constant resultant force acting for time $t$, $J=Ft=m(v-u)$. Impulse has units $\mathrm{N\,s}=\mathrm{kg\,m\,s^{-1}}$; keep the sign of force and velocity along the chosen axis.

*Source: learner's library, Save My Exams, `sources/library/SaveMyExams/XMA01 mechanics-1/XMA01 c3.4.pdf`, p.3 (paraphrased).* 

## Method
1. Choose positive axes, draw forces on each particle, and resolve any sloping weight into parallel and perpendicular components.
2. Write $\sum F=ma$ separately for each body. For a taut string, use the same acceleration magnitude and one tension.
3. Solve simultaneously. If forces change at impact, carry the contact velocity into a second phase and solve again.
4. For an impulse or collision, write signed initial and final momenta before substituting values. State the final direction.

For example, taking right as positive, a $0.50\,\mathrm{kg}$ particle changing from $+4$ to $-2\,\mathrm{m\,s^{-1}}$ receives $J=0.50(-2-4)=-3.0\,\mathrm{N\,s}$. If a constant resultant acts for $0.20\,\mathrm{s}$, $F=J/t=-15\,\mathrm{N}$: the force acts leftward.

> [!example]- Worked example
> A $2\,\mathrm{kg}$ mass and a $3\,\mathrm{kg}$ mass hang over a smooth pulley. Find their acceleration and tension.
> Take the $3\,\mathrm{kg}$ mass downward as positive and the $2\,\mathrm{kg}$ mass upward as positive. Both have acceleration magnitude $a$.
> $$3g-T=3a,\qquad T-2g=2a.$$
> Add the equations: $g=5a$, so $a=1.96\,\mathrm{m\,s^{-2}}$. Substitute into $T-2g=2a$: $T=23.52\,\mathrm{N}$, or $23.5\,\mathrm{N}$ to three significant figures.

> [!example]- Worked example: after ground contact
> In the preceding system, release the particles from rest with the heavier mass $2.5\,\mathrm{m}$ above the ground. It stays on the ground after contact; the lighter mass remains clear of the pulley.
> Before contact, $a=1.96\,\mathrm{m\,s^{-2}}$, so $v^2=2(1.96)(2.5)=9.8$ and the contact speed is $3.13\,\mathrm{m\,s^{-1}}$.
> The lighter mass continues upward, shortening the distance from itself to the pulley while the heavier mass stays still. The string slackens, so $T=0$; only weight acts on the lighter mass. Its new acceleration is $-9.8\,\mathrm{m\,s^{-2}}$, taking upward as positive.
> Its further rise follows from $0=v^2-2gh$: $h=9.8/(2\times9.8)=0.50\,\mathrm{m}$. The old tension equation no longer applies because a slack string cannot pull; carry the lighter mass's velocity across the transition, not its acceleration.

*Scope checked against [Pearson Edexcel IAL Mathematics specification, Unit M1, section 4](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/international-a-level-maths-spec.pdf): forces may change after ground contact. Moving-friction wording also checked against the learner's `sources/library/SaveMyExams/XMA01 mechanics-1/XMA01 c3.3.pdf`, p.8.*

## Traps
- **Trap:** A body must have a forward resultant to keep moving. **Why it's wrong:** Zero resultant means constant velocity. **Instead:** Ask whether velocity is changing.
- **Trap:** Use $R=mg$ on every slope. **Why it's wrong:** The perpendicular weight component is $mg\cos\theta$. **Instead:** Resolve perpendicular to the plane first.
- **Trap:** Treat action and reaction as cancelling on one particle. **Why it's wrong:** They act on different bodies. **Instead:** Draw one force diagram per particle.
- **Trap:** Assume kinetic energy is conserved in every collision. **Why it's wrong:** Energy may change form. **Instead:** Use conservation of signed momentum when external impulse is negligible.

## Exam technique
For **Calculate** and **Find**, show the force or momentum equation before substitution, keep signs consistent and give units. For **Explain**, name the relevant law and the bodies or direction involved. Give numerical answers to two or three significant figures after using $g=9.8\,\mathrm{m\,s^{-2}}$.

## Links
Builds on [[3 Kinematics of a particle moving in a straight line]] and [[2 Vectors in mechanics]].

Leads to [[5 Statics of a particle]].
