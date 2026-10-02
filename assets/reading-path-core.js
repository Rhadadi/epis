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
  var EDUCATION = [
    { id: "unspecified", label: "Prefer not to say / skip" },
    { id: "secondary", label: "School / secondary education" },
    { id: "university", label: "College / undergraduate study" },
    { id: "graduate", label: "Postgraduate study" },
    { id: "self-directed", label: "Self-directed learning / another route" }
  ];
  var STUDIES = [
    { id: "none", label: "No related study / skip" },
    { id: "philosophy", label: "Philosophy, logic or critical thinking" },
    { id: "quantitative", label: "Mathematics, statistics or data analysis" },
    { id: "research", label: "Science, medicine or research methods" },
    { id: "social", label: "Social sciences, humanities or media studies" }
  ];
  function assess(data, answers) {
    var bank = data.diagnostics && data.diagnostics.questions || [];
    var sanitized = [], seen = new Set(), dimensions = {}, reviews = [];
    (Array.isArray(answers) ? answers : []).forEach(function (answer) {
      if (!answer || typeof answer !== "object" || seen.has(answer.question)) return;
      var q = bank.find(function (q) { return q.id === answer.question; });
      if (!q || !(answer.answer === "unsure" || q.choices.some(function (_, i) { return String(i) === answer.answer; }))) return;
      seen.add(q.id);
      var record = { question: q.id, answer: answer.answer, confidence: answer.answer !== "unsure" && answer.confidence === "sure" ? "sure" : "tentative", reason: typeof answer.reason === "string" ? answer.reason.slice(0,400) : "" };
      sanitized.push(record);
      var result = dimensions[q.dimension] || { correct: 0, attempts: 0, unsure: 0, confidentErrors: 0 };
      result.attempts++;
      if (record.answer === "unsure") result.unsure++;
      else if (+record.answer === q.correct) result.correct++;
      else if (record.confidence === "sure") result.confidentErrors++;
      dimensions[q.dimension] = result;
      if (record.answer === "unsure" || +record.answer !== q.correct) reviews.push({ question: q.id, title: q.title, id: q.review.id, why: record.answer === "unsure" ? data.unsureReason || "Start with an explanation of this idea, since you chose “not sure” in the example." : q.review.why, unsure: record.answer === "unsure" });
    });
    var familiar = Object.keys(dimensions).filter(function (dim) {
      var r = dimensions[dim]; return r.correct >= 2 && r.correct === r.attempts;
    });
    return { answers: sanitized, dimensions: dimensions, familiar: familiar, reviews: reviews };
  }
  function nextQuestion(data, input) {
    if (!data.diagnostics) return null;
    var report = assess(data, input && input.diagnosticAnswers);
    var limit = input && input.mode === "quick" ? 3 : input && input.mode === "deep" ? 6 : 5;
    if (report.answers.length >= limit) return null;
    var priorities = data.diagnostics.priorities[(input && input.topic) + "/" + (input && input.focus)] || ["vocabulary", "logic", "knowledge"];
    priorities = priorities.slice();
    var first = report.dimensions[priorities[0]];
    if (first && first.attempts >= 2 && first.correct === 0) {
      var repair = { logic: "vocabulary", probability: "vocabulary", knowledge: "vocabulary", evidence: "logic", testimony: "evidence", definitions: "logic", vocabulary: "evidence" }[priorities[0]];
      priorities = [priorities[0], repair].concat(priorities.slice(1).filter(function (d) { return d !== repair; }));
    }
    var dimension = priorities[Math.floor(report.answers.length / 2)] || priorities[0];
    var available = data.diagnostics.questions.filter(function (q) {
      return q.dimension === dimension && !report.answers.some(function (a) { return a.question === q.id; });
    });
    if (!available.length) return null;
    var current = report.dimensions[dimension];
    if (!current) {
      var entry = data.diagnostics.entryByStudy[(input && input.studies) + "/" + dimension];
      return available.find(function (q) { return q.id === entry; }) || available.sort(function (a,b) { return a.level - b.level; })[0];
    }
    return available.sort(function (a,b) { return current.correct ? b.level - a.level : a.level - b.level; })[0];
  }
  function normalize(data, input) {
    input = input && typeof input === "object" ? input : {};
    var topic = data.topics.find(function (t) { return t.id === input.topic; });
    var focus = topic && topic.focuses.find(function (f) { return f.id === input.focus; });
    var report = Array.isArray(input.diagnosticAnswers) ? assess(data, input.diagnosticAnswers) : null;
    return {
      goal: typeof input.goal === "string" ? input.goal.slice(0, 600) : "",
      mode: Object.prototype.hasOwnProperty.call(MODES, input.mode) ? input.mode : "guided",
      topic: topic ? topic.id : "", focus: focus ? focus.id : "",
      minutes: [15, 30, 60, 120, 240].includes(+input.minutes) ? +input.minutes : 30,
      education: EDUCATION.some(function (e) { return e.id === input.education; }) ? input.education : "unspecified",
      studies: STUDIES.some(function (s) { return s.id === input.studies; }) ? input.studies : "none",
      known: report ? report.familiar : Array.isArray(input.known) ? data.competencies.map(function (c) { return c.id; }).filter(function (id) { return input.known.includes(id); }) : [],
      done: Array.isArray(input.done) ? input.done.filter(function (id) { return typeof id === "string" && data.sections[id.replace(/:deep$/, "")]; }) : [],
      excluded: Array.isArray(input.excluded) ? input.excluded.filter(function (id) { return !!data.sections[id]; }) : [],
      ...(report ? { diagnosticAnswers: report.answers } : {})
    };
  }
  function suggest(data, goal) {
    function normalized(text) { return String(text).toLowerCase().replace(/ي/g, "ی").replace(/ك/g, "ک").replace(/\u200c/g, " "); }
    var query = normalized(goal || "");
    var ranked = data.topics.map(function (t) {
      return { id: t.id, score: t.keywords.reduce(function (sum, word) {
        var escaped = normalized(word).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return sum + (new RegExp("(?:^|[^\\p{L}\\p{N}])" + escaped + "(?=$|[^\\p{L}\\p{N}])", "iu").test(query) ? 1 : 0);
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
      if (profile.known.includes(data.foundations[sid]) || (prerequisite && profile.done.includes(sid))) return;
      visiting.add(sid);
      (data.prerequisites[sid] || []).forEach(function (p) { add(p.id, p.why, true); });
      visiting.delete(sid);
      seen.add(sid);
      candidates.push(Object.assign({}, data.sections[sid], { why: why, prerequisite: !!prerequisite, kind: "section" }));
    }
    var introduction = data.educationIntroductions && data.educationIntroductions[topic.id + "/" + focus.id];
    // Education supplies a starting suggestion, never proof of subject mastery.
    // Explicit competence, relevant study, completion and skips override a school-level introduction.
    if (introduction && profile.education === "secondary" && profile.studies === "none" && !profile.known.includes(data.foundations[introduction.id]) && !profile.known.includes("knowledge") && !profile.done.includes(introduction.id)) {
      add(introduction.id, introduction.why, true);
    }
    if (data.studyBridges && data.studyBridges[profile.studies + "/" + topic.id + "/" + focus.id]) {
      var bridge = data.studyBridges[profile.studies + "/" + topic.id + "/" + focus.id];
      if (!profile.known.includes(data.foundations[bridge.id]) && !profile.done.includes(bridge.id)) add(bridge.id, bridge.why, true);
    }
    var diagnosticReport = assess(data, profile.diagnosticAnswers);
    diagnosticReport.reviews.forEach(function (review) { add(review.id, review.why, true); });
    focus.steps.forEach(function (s) { add(s.id, s.why, false); });
    // Expand in pedagogical order. Foundations stay short; the primary topic gets depth.
    var expanded = [];
    candidates.forEach(function (s) {
      expanded.push(s);
      if (profile.mode === "deep" && s.deep && !s.prerequisite && !profile.excluded.includes(s.id)) {
        expanded.push(Object.assign({}, s, {
          id: s.id + ":deep", kind: "deep", url: s.deep.url, minutes: s.deep.minutes,
          language: s.deep.language || s.language || "en",
          why: data.deepReason || "After the chapter section, examine its arguments, objections and source excerpts in the Deeper study page."
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
    return { items: items, later: later, minutes: minutes, profile: profile, topic: topic, focus: focus, assessment: diagnosticReport };
  }
  return { modes: MODES, education: EDUCATION, studies: STUDIES, assess: assess, nextQuestion: nextQuestion, normalize: normalize, suggest: suggest, validInterview: validInterview, recommend: recommend };
});
