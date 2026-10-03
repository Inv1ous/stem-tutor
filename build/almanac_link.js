/* STEM Tutor sync. The tutor writes __FILE__ beside this page. This merges what it knows into the planner's own
   state: objectives it has seen you finish, a colour for every syllabus topic, paper scores, study days, mistake
   counts, the week's retrospective and the paper stage. What you tick, type or write yourself is kept. */
function tutorMerge(S, T) {
  if (!T || !T.stamp || (S.tutor && S.tutor.stamp === T.stamp)) return false;
  const mine = S.tutor = S.tutor || {};
  for (const key of ["done", "rag", "scores", "wall", "retro", "err"]) S[key] = S[key] || {};
  for (const id of Object.keys(T.done || {})) S.done[id] = 1;  /* ticks are added, never taken away */
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
  if (Number.isInteger(T.stage)) S.stage = T.stage;
  Object.assign(mine, { stamp: T.stamp, at: T.at, scores: T.scores || {}, err: T.err || {},
                        retro: Object.assign({}, mine.retro, T.retro) });
  return true;
}
if (typeof document !== "undefined") (function () {
  function pull() {
    const el = document.createElement("script");
    el.src = "__FILE__?" + Date.now();
    el.onload = () => {
      el.remove();
      const typing = document.activeElement && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
      if (!typing && tutorMerge(S, window.TUTOR_SYNC)) { save(); renderAll(); toast("Updated by STEM Tutor"); }
    };
    el.onerror = () => el.remove();
    document.head.appendChild(el);
  }
  pull();
  setInterval(pull, 30000);
})();
