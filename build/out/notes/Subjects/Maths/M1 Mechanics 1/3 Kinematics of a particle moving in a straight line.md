---
tags: [stem-tutor/lesson, edexcel-m1]
spec: "M1"
subtopic: "M1-3"
kcs: ["M1-3.1"]
---
# 3 Kinematics of a particle moving in a straight line
> [!abstract] In one breath
> A particle moving in a straight line has signed displacement, velocity and acceleration once you choose a positive direction. With **constant acceleration**, a small set of equations links these quantities; graph gradients and areas give the same motion information visually.

## Key ideas
Take one direction as positive throughout. Displacement $s$ is the signed change in position, whereas distance is the total length travelled. Velocity is the rate of change of displacement; speed is the nonnegative magnitude of velocity. Acceleration is the rate of change of velocity. A negative acceleration points in the negative chosen direction: whether the particle slows down depends on the sign of its velocity.

Use $u$ for initial velocity, $v$ for final velocity, $a$ for constant acceleration and $t$ for elapsed time. The constant-acceleration, or **suvat**, equations are

$$v=u+at,\qquad s=ut+\tfrac12at^2,\qquad s=\tfrac12(u+v)t,\qquad v^2=u^2+2as.$$

The third equation uses average velocity, $(u+v)/2$, which is valid here because velocity changes linearly. These equations apply within an interval of constant acceleration. For free fall near Earth, use $g=9.8\,\mathrm{m\,s^{-2}}$ and choose downward or upward as positive before assigning the sign of $a$.

A fifth equivalent form, $s=vt-\tfrac12at^2$, is often quicker when the final velocity rather than the initial one is known: putting $u=v-at$ into $s=\tfrac12(u+v)t$ gives $s=\tfrac12(2v-at)t=vt-\tfrac12at^2$. None of these equations is printed in the examination paper, so all five have to be recalled.

A **displacement–time** graph has velocity as its gradient. On a **velocity–time** graph, gradient is acceleration and signed area between the line and time axis is displacement. Area below that axis is negative. A **speed–time** graph has nonnegative height and its area is distance. On an **acceleration–time** graph, signed area gives change in velocity. Constant acceleration appears as a horizontal acceleration–time line, a straight velocity–time line, and a quadratic displacement–time curve. When velocity reaches zero, the displacement–time graph has a horizontal tangent; the particle may then reverse direction.

![[Assets/M1/M1-3-vt-turning.svg]]

Here the line crosses the time axis at $t=4\,\mathrm{s}$, where the particle is momentarily at rest and then reverses. The shaded region above the axis has area $+16\,\mathrm{m}$ and the region below has area $-9\,\mathrm{m}$, so the displacement is $16-9=7\,\mathrm{m}$ while the distance adds the magnitudes, $16+9=25\,\mathrm{m}$.

![[Assets/M1/M1-3-at-area.svg]]

The shaded rectangle under this acceleration–time graph has area $3\times5=15\,\mathrm{m\,s^{-1}}$, which is the **change** in velocity over the $5\,\mathrm{s}$ and not the velocity itself: add it to $u$ to get $v$. The same constant acceleration makes the velocity–time graph a straight line of gradient $3$ and the displacement–time graph a quadratic curve.

## Method
1. Sketch a direction arrow and record known values with signs and units: $u,v,a,s,t$.
2. Choose an equation containing the unknown and known quantities, leaving out the one quantity you do not have. If motion has stages, treat each constant-acceleration stage separately and carry the final velocity into the next stage.
3. Substitute signed values before simplifying. If an equation gives $v^2$, check both possible signs of $v$ against the motion.
4. For a graph, use a gradient for a rate of change and an area for an accumulated change. Split areas at every change of slope or crossing of the time axis.
5. Give a unit, sensible significant figures and a contextual check. A displacement can be negative; a distance cannot.

> [!example]- Worked example
> A particle starts at $3\,\mathrm{m\,s^{-1}}$ and accelerates at $2\,\mathrm{m\,s^{-2}}$ for $4\,\mathrm{s}$. Find its final velocity and displacement.
> Take the initial direction as positive. Here $u=3$, $a=2$ and $t=4$.
> $$v=u+at=3+2(4)=11\,\mathrm{m\,s^{-1}}.$$
> $$s=ut+\tfrac12at^2=3(4)+\tfrac12(2)(4)^2=28\,\mathrm{m}.$$
> The positive answers agree with motion continuing forwards and speeding up.

## Traps
- **Trap:** Treat a negative acceleration as proof that speed decreases. **Why it's wrong:** A particle moving in the negative direction speeds up if acceleration is also negative. **Instead:** Compare the signs of velocity and acceleration.
- **Trap:** Add every velocity–time area positively to obtain displacement. **Why it's wrong:** Area below the time axis represents negative displacement. **Instead:** Use signed areas for displacement and absolute areas for distance.
- **Trap:** Use a suvat equation across a change in acceleration. **Why it's wrong:** Its derivation assumes one constant value of $a$. **Instead:** Split the motion into constant-acceleration intervals.

## Exam technique
For **Find** or **Calculate**, show the equation, substitution and result with units. For **Sketch**, label axes, intercepts and the sign or shape of the gradient; a straight velocity–time line signals constant acceleration. For **Explain**, name the graph operation and the physical quantity it produces. If a particle turns, find the time when $v=0$ before calculating total distance. With $g=9.8\,\mathrm{m\,s^{-2}}$, quote a calculated result to 2 or 3 significant figures.

> [!tip] Turning an acceleration–time graph into a speed–time graph
> 1. Write down the initial velocity: the acceleration graph on its own cannot tell you it.
> 2. Take one interval at a time and add that interval's signed area to the velocity at its start.
> 3. Plot those velocities and join them: constant acceleration gives a straight segment, zero acceleration a horizontal one.
> 4. Mark every time at which the velocity changes sign, solving $v=0$ for it.
> 5. Reflect the parts below the axis upwards to turn velocity into speed, then read distance as the total area under the speed–time graph.

Pearson's guidance for this topic says graphical solutions to problems may be required, covering displacement–time, velocity–time, speed–time and acceleration–time graphs. WME01 papers do ask for speed–time graphs to be sketched on given axes, and their mark schemes credit either a gradient read from the sketch or $v=u+at$, so a labelled sketch earns marks even when an equation supplies the number.

## Self-test
> [!question]- Three checks
> 1. A particle has $u=-4\,\mathrm{m\,s^{-1}}$ and $a=-2\,\mathrm{m\,s^{-2}}$. Is it speeding up or slowing down? — **Speeding up**: velocity and acceleration have the same sign.
> 2. An acceleration–time graph is horizontal at $-2\,\mathrm{m\,s^{-2}}$ for $6\,\mathrm{s}$ and the particle starts at $9\,\mathrm{m\,s^{-1}}$. Find the velocity at $t=6\,\mathrm{s}$. — The signed area is $-12\,\mathrm{m\,s^{-1}}$, so $v=9-12=-3\,\mathrm{m\,s^{-1}}$.
> 3. For that motion, find the displacement and the distance over the $6\,\mathrm{s}$. — Velocity is zero at $t=4.5\,\mathrm{s}$; displacement $=\tfrac12(4.5)(9)+\tfrac12(1.5)(-3)=20.25-2.25=18\,\mathrm{m}$, distance $=20.25+2.25=22.5\,\mathrm{m}$.

## Links
Builds on [[2 Vectors in mechanics]] · Leads to [[4 Dynamics of a particle moving in a straight line]]
