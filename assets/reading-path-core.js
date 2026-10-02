/* Pure recommendation logic, shared by the page and Node tests. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.EpisReadingPath = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  var MODES = {
    quick: { label: "Quick answer", description: "A focused start on one question.", limit: 3 },
    guided: { label: "Guided learning", description: "Build the ideas, then put them to use.", limit: 7 },
    deep: { label: "Deep study", description: "Follow the arguments into the source-based study pages.", limit: 12 }
  };
  function normalize(data, input) {
    input = input && typeof input === "object" ? input : {};
    var topic = data.topics.find(function (t) { return t.id === input.topic; });
    var focus = topic && topic.focuses.find(function (f) { return f.id === input.focus; });
    return {
      goal: typeof input.goal === "string" ? input.goal.slice(0, 600) : "",
      mode: Object.prototype.hasOwnProperty.call(MODES, input.mode) ? input.mode : "guided",
      topic: topic ? topic.id : "", focus: focus ? focus.id : "",
      minutes: [15, 30, 60, 120, 240].includes(+input.minutes) ? +input.minutes : 30,
      known: Array.isArray(input.known) ? data.competencies.map(function (c) { return c.id; }).filter(function (id) { return input.known.includes(id); }) : [],
      done: Array.isArray(input.done) ? input.done.filter(function (id) { return typeof id === "string" && data.sections[id.replace(/:deep$/, "")]; }) : [],
      excluded: Array.isArray(input.excluded) ? input.excluded.filter(function (id) { return !!data.sections[id]; }) : []
    };
  }
  function suggest(data, goal) {
    var query = String(goal || "").toLowerCase();
    var ranked = data.topics.map(function (t) {
      return { id: t.id, score: t.keywords.reduce(function (sum, word) {
        var escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return sum + (new RegExp("\\b" + escaped + "\\b", "i").test(query) ? 1 : 0);
      }, 0) };
    }).filter(function (t) { return t.score > 0; }).sort(function (a, b) { return b.score - a.score; });
    return ranked.length ? ranked[0].id : "";
  }
  function validInterview(data, reply) {
    if (!reply || typeof reply !== "object" || !data.topics.some(function (t) { return t.id === reply.topic; })) return null;
    if (typeof reply.question !== "string" || reply.question.trim().length < 10 || reply.question.length > 300) return null;
    return { topic: reply.topic, question: reply.question.trim() };
  }
  function recommend(data, input) {
    var profile = normalize(data, input);
    var topic = data.topics.find(function (t) { return t.id === profile.topic; });
    var focus = topic && topic.focuses.find(function (f) { return f.id === profile.focus; });
    if (!focus) return { items: [], later: [], minutes: 0, profile: profile };
    var candidates = [], seen = new Set(), visiting = new Set();
    function add(sid, why, prerequisite) {
      if (seen.has(sid) || visiting.has(sid) || !data.sections[sid]) return;
      if (profile.excluded.includes(sid)) return;
      if (prerequisite && (profile.done.includes(sid) || profile.known.includes(data.foundations[sid]))) return;
      visiting.add(sid);
      (data.prerequisites[sid] || []).forEach(function (p) { add(p.id, p.why, true); });
      visiting.delete(sid);
      seen.add(sid);
      candidates.push(Object.assign({}, data.sections[sid], { why: why, prerequisite: !!prerequisite, kind: "section" }));
    }
    focus.steps.forEach(function (s) { add(s.id, s.why, false); });
    // Expand in pedagogical order. Foundations stay short; the primary topic gets depth.
    var expanded = [];
    candidates.forEach(function (s) {
      expanded.push(s);
      if (profile.mode === "deep" && s.deep && !s.prerequisite && !profile.excluded.includes(s.id)) {
        expanded.push(Object.assign({}, s, {
          id: s.id + ":deep", kind: "deep", url: s.deep.url, minutes: s.deep.minutes,
          why: "After the chapter section, examine its arguments, objections and source excerpts in the Deeper study page."
        }));
      }
    });
    var items = [], later = [], minutes = 0, available = new Set(profile.done);
    expanded.forEach(function (s) {
      if (profile.done.includes(s.id)) return;
      var base = s.id.replace(/:deep$/, "");
      var unmet = s.kind === "deep" ? !available.has(base) : (data.prerequisites[base] || []).some(function (p) {
        return !available.has(p.id) && !profile.known.includes(data.foundations[p.id]) && !profile.excluded.includes(p.id);
      });
      if (unmet || items.length >= MODES[profile.mode].limit || minutes + s.minutes > profile.minutes) {
        later.push(s); return;
      }
      items.push(s); available.add(s.id); minutes += s.minutes;
    });
    return { items: items, later: later, minutes: minutes, profile: profile, topic: topic, focus: focus };
  }
  return { modes: MODES, normalize: normalize, suggest: suggest, validInterview: validInterview, recommend: recommend };
});
