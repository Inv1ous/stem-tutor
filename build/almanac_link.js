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
    };
    el.onerror = () => el.remove();
    document.head.appendChild(el);
  }
  const reset = document.getElementById && document.getElementById("resetBtn");
  if (reset) reset.addEventListener("click", () => {  /* runs after the page's own Reset */
    if (!S.tutor && kept) { S.tutor = kept; save(); }
  });
  pull();
  setInterval(pull, 30000);
})();
