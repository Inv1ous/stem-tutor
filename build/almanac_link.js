/* STEM Tutor sync. The tutor writes __FILE__ beside this page. This merges what it knows into the planner's own
   state: objectives it has seen you finish, a colour for every syllabus topic, paper scores, study days, mistake
   counts, the week's retrospective and the paper stage. What you tick, type or write yourself is kept. */
function tutorMerge(S, T) {
  if (!T || !T.stamp || (S.tutor && S.tutor.stamp === T.stamp)) return false;
  const mine = S.tutor = S.tutor || {}, added = {};
  for (const key of ["done", "rag", "scores", "wall", "retro", "err"]) S[key] = S[key] || {};
  for (const id of Object.keys(T.done || {}))  /* a tick is added once: one you take away stays off */
    if (!S.done[id] && !(mine.done || {})[id]) S.done[id] = added[id] = 1;
    else if (mine.stamp && !mine.done && S.done[id]) added[id] = 1;  /* merged before the tutor kept count */
  Object.assign(S.rag, T.rag || {});  /* every colour is the tutor's: it goes by your answers */
  Object.assign(S.wall, T.wall || {});
  for (const [k, v] of Object.entries(T.scores || {})) {  /* a score you typed yourself is left alone */
    const cur = S.scores[k];
    if (cur === undefined || cur === "" || cur === (mine.scores || {})[k]) S.scores[k] = v;
  }
  for (const [f, n] of Object.entries(T.err || {}))  /* add only what is new since the last merge */
    S.err[f] = Math.max(0, (S.err[f] || 0) + n - ((mine.err || {})[f] || 0));
  for (const [w, r] of Object.entries(T.retro || {})) {  /* a retrospective you wrote or edited is left alone */
    const cur = S.retro[w], old = (mine.retro || {})[w];
    if (!cur || (old && cur.broke === old.broke && cur.fix === old.fix)) S.retro[w] = r;
  }
  /* a paper stage you set yourself is left alone */
  if (Number.isInteger(T.stage) && (mine.stage === undefined || S.stage === mine.stage)) S.stage = T.stage;
  Object.assign(mine, { stamp: T.stamp, at: T.at, scores: T.scores || {}, err: T.err || {},
                        retro: Object.assign({}, mine.retro, T.retro), done: Object.assign({}, mine.done, added),
                        stage: Number.isInteger(T.stage) ? T.stage : mine.stage });
  return true;
}

/* What the tutor shows beside the ticks. A tick stays all or nothing (it follows the ideas an objective names); the
   rest is shown as it happens: how far each objective is, what is on screen now and what today has added. */
const TUTOR_SUBJ = { math: "Maths", chem: "Chemistry", phys: "Physics" };
const TUTOR_MODE = { autopilot: "Today's plan", learn: "Learning", lesson: "Lesson", review: "Review", weak: "Weak spots",
                     test: "Test prep", long: "Long questions", blurt: "Blurt", diagnose: "Diagnostic" };
function tutorProgressText(p) {
  if (!p || !p.of) return "";
  const pct = Math.round(100 * p.secure / p.of), need = Math.round(100 * (p.need || 1));
  let t = p.done ? `Done: the tutor has ticked this (${p.secure} of ${p.of} ideas ${p.new ? "learned" : "secure"}).`
    : `${p.secure} of ${p.of} ideas ${p.new ? "learned" : "secure"} (${pct}%)`;
  if (!p.done && need < 100) t += ` · ${need}% needed in each subject`;
  const subs = Object.entries(p.bysub || {});
  if (subs.length > 1) t += " · " + subs.map(([k, v]) => `${TUTOR_SUBJ[k] || k} ${v[0]}/${v[1]}`).join(", ");
  if (!p.done && p.waiting && !p.new) t += ` · ${p.waiting} right once, waiting for a second day`;
  if (!p.done && p.tried < p.of) t += ` · ${p.of - p.tried} not tried yet`;
  if (!p.done && p.next && p.next.length) t += ` · next: ${p.next.join("; ")}`;
  return t;
}
function tutorLiveText(T, nowSec) {
  if (!T) return "";
  const s = T.session, d = T.today || {};
  const day = d.answers ? `Today: ${d.answers} answer${d.answers === 1 ? "" : "s"}, ${d.right} right, ${d.ideas} idea${d.ideas === 1 ? "" : "s"}` +
    (d.sessions > 1 ? ` over ${d.sessions} sessions` : "") + "." : "Nothing answered today yet.";
  if (!s) return `No session running. ${day}`;
  const fresh = nowSec - (s.updated || 0) < 300;
  let t = `${fresh ? "Live" : "Last seen"}: ${TUTOR_MODE[s.mode] || s.mode} · ${s.minutes} min · ${s.answered} answered` +
    (s.answered ? ` (${s.correct} right)` : "") + ".";
  if (fresh && s.now && s.now.length) t += ` On screen: ${s.now.join("; ")}.`;
  if (s.covered && s.covered.length) t += ` Covered: ${s.covered.join("; ")}.`;
  return `${t} ${day}`;
}
function tutorDecorate(T) {
  try { tutorDraw(T); } catch (e) { /* the progress is a courtesy: the page itself is never put at risk by it */ }
}
function tutorDraw(T) {
  if (!T || typeof document === "undefined" || !document.querySelectorAll) return;
  if (!document.getElementById("tutorLiveCss")) {
    const st = document.createElement("style");
    st.id = "tutorLiveCss";
    st.textContent = ".obj-prog{margin-top:6px;font-size:12px;line-height:1.4;opacity:.85}" +
      ".obj-prog i{display:block;height:4px;border-radius:2px;background:rgba(128,128,128,.25);margin-bottom:4px;overflow:hidden}" +
      ".obj-prog i b{display:block;height:100%;background:var(--tickc,#3a7)}" +
      "#tutorLive{margin:0 0 14px;padding:10px 14px;border-radius:8px;border:1px solid rgba(128,128,128,.35);font-size:13px;line-height:1.5}" +
      "#tutorLive[data-live=\"1\"]{border-color:#3a7}";
    document.head.appendChild(st);
  }
  document.querySelectorAll(".obj[data-id]").forEach(el => {
    const p = (T.progress || {})[el.dataset.id], text = tutorProgressText(p), body = el.querySelector(".obj-body");
    let box = el.querySelector(".obj-prog");
    if (!text || !body) { if (box) box.remove(); return; }
    const pct = Math.round(100 * p.secure / p.of);
    if (!box) { box = document.createElement("div"); box.className = "obj-prog"; box.innerHTML = "<i><b></b></i><span></span>"; body.appendChild(box); }
    const bar = box.querySelector("b"), label = box.querySelector("span");
    if (bar.style.width !== pct + "%") bar.style.width = pct + "%";
    if (label.textContent !== text) label.textContent = text;
  });
  const anchor = document.getElementById("nowObjectives");
  if (anchor) {
    let live = document.getElementById("tutorLive");
    if (!live) { live = document.createElement("div"); live.id = "tutorLive"; anchor.parentNode.insertBefore(live, anchor); }
    const text = "STEM Tutor · " + tutorLiveText(T, Date.now() / 1000), on = T.session && Date.now() / 1000 - T.session.updated < 300 ? "1" : "0";
    if (live.textContent !== text) live.textContent = text;
    if (live.dataset.live !== on) live.dataset.live = on;
  }
}
if (typeof document !== "undefined") (function () {
  let kept = S.tutor;  /* what the tutor last merged: "Reset everything" must not bring it straight back */
  function pull() {
    kept = S.tutor || kept;
    const el = document.createElement("script");
    el.src = "__FILE__?" + Date.now();
    el.onload = () => {
      el.remove();
      const typing = document.activeElement && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
      if (!typing && tutorMerge(S, window.TUTOR_SYNC)) { save(); renderAll(); toast("Updated by STEM Tutor"); }
      kept = S.tutor || kept;
      tutorDecorate(window.TUTOR_SYNC);
    };
    el.onerror = () => el.remove();
    document.head.appendChild(el);
  }
  const reset = document.getElementById && document.getElementById("resetBtn");
  if (reset) reset.addEventListener("click", () => {  /* runs after the page's own Reset */
    if (!S.tutor && kept) { S.tutor = kept; save(); }
  });
  let queued = false;  /* the page redraws its lists often: put the progress back after each redraw */
  if (typeof MutationObserver !== "undefined" && document.body)
    new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; tutorDecorate(window.TUTOR_SYNC); });
    }).observe(document.body, { childList: true, subtree: true });
  pull();
  setInterval(pull, 30000);  /* every pull redraws the progress too: "live" turns to "last seen" when pushes stop */
})();
