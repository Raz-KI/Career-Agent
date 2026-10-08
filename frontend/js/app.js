import * as api from "./api.js";
import * as voice from "./voice.js";
import * as ui from "./ui.js";

const state = {
  sessionId: crypto.randomUUID(),
  privacy: false,
  voiceMode: false,
  language: "en",
  simpleEnglish: false,
  profile: null,
  paths: [],
  chosenPath: null,
  jdText: "",
  matches: [],
  selectedMatch: null,
  gapPlan: [],
  tailored: null,
  cover: null,
  excludedClaims: new Set(),
  questions: [],
  interview: null,
  chat: [],
  evaluation: null,
  lastQuestion: "",
  safetyFlags: [],
  handoff: null,
  step: 0,
};

function ctx() {
  return {
    profile: state.profile,
    preferred_language: state.language,
    simple_english: state.simpleEnglish,
    target_role: state.chosenPath?.title,
    job: state.selectedMatch?.job,
    job_description: state.jdText || state.selectedMatch?.job?.description,
  };
}

function show(id) {
  document.querySelectorAll("main > section").forEach((s) => s.classList.add("hidden"));
  document.getElementById(id)?.classList.remove("hidden");
}

function setStep(n) {
  state.step = n;
  const nav = document.getElementById("progressNav");
  if (n >= 1) nav.hidden = false;
  nav.querySelectorAll("li").forEach((li) => {
    const s = Number(li.dataset.step);
    li.classList.toggle("active", s === n);
    li.classList.toggle("done", s < n);
  });
  if (n === 1) show("view-profile");
  if (n === 2) show("view-step1");
  if (n === 3) show("view-step2");
  if (n === 4) show("view-step3");
  if (n === 5) show("view-step4");
  if (n === 6) show("view-step5");
}

function maybeSafety(payload) {
  const flag = payload?.safety;
  if (flag?.triggered) {
    state.safetyFlags.push(flag.category);
    ui.safetyDialog(flag);
    return true;
  }
  return false;
}

async function withBusy(label, fn) {
  ui.showBusy(label);
  document.querySelectorAll("button").forEach((b) => {
    b.dataset.prev = b.disabled ? "1" : "0";
    b.disabled = true;
  });
  try {
    return await fn();
  } catch (err) {
    alert(err.message || "Something went wrong. Try again or switch to text.");
    throw err;
  } finally {
    ui.hideBusy();
    document.querySelectorAll("button").forEach((b) => {
      if (b.dataset.prev === "0") b.disabled = false;
    });
  }
}

function fillProfileForm(profile) {
  const container = document.getElementById("profileForm");
  container.innerHTML = ui.renderProfileForm(profile);

  container.querySelector("#add-exp-btn")?.addEventListener("click", () => {
    const expContainer = document.getElementById("pf-experience-container");
    const count = expContainer.children.length;
    const div = document.createElement("div");
    div.className = "profile-card-item exp-item";
    div.dataset.index = count;
    div.innerHTML = `
      <div class="row">
        <label class="grow">Job Title<input type="text" class="pf-exp-title" placeholder="e.g. Software Engineer / Nurse" /></label>
        <label class="grow">Employer / Company<input type="text" class="pf-exp-employer" placeholder="e.g. TechCorp / NHS Trust" /></label>
      </div>
      <div class="row">
        <label class="grow">Country / City<input type="text" class="pf-exp-country" placeholder="e.g. UK / Kyiv" /></label>
        <label class="grow">Years / Dates<input type="text" class="pf-exp-years" placeholder="e.g. 2019 - 2023" /></label>
      </div>
      <label>Key Achievements / Responsibilities <span class="muted">(separate with semicolons ;)</span>
        <input type="text" class="pf-exp-achievements" placeholder="e.g. Built REST APIs; Managed team of 5" />
      </label>
      <button type="button" class="ghost btn-remove-item remove-exp" title="Remove experience">✕ Remove role</button>
    `;
    expContainer.appendChild(div);
  });

  container.querySelector("#add-edu-btn")?.addEventListener("click", () => {
    const eduContainer = document.getElementById("pf-education-container");
    const count = eduContainer.children.length;
    const div = document.createElement("div");
    div.className = "profile-card-item edu-item";
    div.dataset.index = count;
    div.innerHTML = `
      <div class="row">
        <label class="grow">Qualification / Degree<input type="text" class="pf-edu-qual" placeholder="e.g. BSc Computer Science" /></label>
        <label class="grow">Institution / University<input type="text" class="pf-edu-inst" placeholder="e.g. Kyiv National University" /></label>
      </div>
      <div class="row">
        <label class="grow">Country<input type="text" class="pf-edu-country" placeholder="e.g. Ukraine / UK" /></label>
        <label class="grow">Year Completed<input type="text" class="pf-edu-year" placeholder="e.g. 2018" /></label>
      </div>
      <button type="button" class="ghost btn-remove-item remove-edu" title="Remove qualification">✕ Remove qualification</button>
    `;
    eduContainer.appendChild(div);
  });

  container.querySelector("#add-lang-btn")?.addEventListener("click", () => {
    const langContainer = document.getElementById("pf-languages-container");
    const count = langContainer.children.length;
    const div = document.createElement("div");
    div.className = "profile-card-item lang-item";
    div.dataset.index = count;
    div.innerHTML = `
      <div class="row">
        <label class="grow">Language<input type="text" class="pf-lang-name" placeholder="e.g. English, Ukrainian, Polish" /></label>
        <label class="grow">Proficiency Level<input type="text" class="pf-lang-level" placeholder="e.g. Fluent, Native, B2" /></label>
      </div>
      <button type="button" class="ghost btn-remove-item remove-lang" title="Remove language">✕ Remove language</button>
    `;
    langContainer.appendChild(div);
  });

  container.addEventListener("click", (e) => {
    if (e.target && e.target.classList.contains("btn-remove-item")) {
      const card = e.target.closest(".profile-card-item");
      if (card) {
        card.remove();
      }
    }
  });
}

async function loadDemo() {
  const profile = await withBusy("Loading demo…", () => api.getDemo());
  state.profile = profile;
  state.language = profile.preferred_language || "uk";
  state.simpleEnglish = true;
  document.getElementById("language").value = state.language;
  document.getElementById("simpleEnglish").checked = true;
  document.getElementById("privacyOk").checked = true;
  document.getElementById("acceptPrivacy").disabled = false;
  state.privacy = true;
  setStep(1);
  fillProfileForm(profile);
}

function readProfile() {
  state.profile = {
    ...ui.readProfileForm(state.profile || {}),
    preferred_language: state.language,
    simple_english: state.simpleEnglish,
  };
}

async function goCareers() {
  readProfile();
  const data = await withBusy("Finding realistic UK paths…", () =>
    api.careerOptions({
      profile: state.profile,
      preferred_language: state.language,
      simple_english: state.simpleEnglish,
    })
  );
  state.paths = data.paths || [];
  setStep(2);
  document.getElementById("view-step1").innerHTML = `<div class="card">
    <h1>Career options</h1>
    <p>Bridge jobs first where a profession is regulated. We never promise a licence.</p>
    ${ui.pathCards(state.paths)}
    <div class="actions"><button type="button" id="backProfile" class="ghost">Back to profile</button></div>
  </div>`;
  document.querySelectorAll("[data-choose]").forEach((btn) => {
    btn.onclick = () => {
      state.chosenPath = state.paths[Number(btn.dataset.choose)];
      renderStep2();
    };
  });
  document.getElementById("backProfile").onclick = () => setStep(1);
}

function renderStep2() {
  setStep(3);
  document.getElementById("view-step2").innerHTML = `<div class="card">
    <h1>Choose a path</h1>
    <p>Target role: <strong>${ui.escapeHtml(state.chosenPath?.title || "")}</strong></p>
    <div class="actions">
      <button type="button" class="primary" id="findJobs">Find matching jobs</button>
      <button type="button" id="useJd">Enter a job description (JD)</button>
    </div>
    <div id="jdBox" class="hidden">
      <label>Paste a UK job advert
        <textarea id="jdText" rows="8"></textarea>
      </label>
      <button type="button" id="analyzeJd">Analyse this advert</button>
    </div>
    <div class="actions"><button type="button" class="ghost" id="back1">Back</button></div>
  </div>`;
  document.getElementById("findJobs").onclick = findJobs;
  document.getElementById("useJd").onclick = () => document.getElementById("jdBox").classList.remove("hidden");
  document.getElementById("analyzeJd").onclick = runJd;
  document.getElementById("back1").onclick = () => setStep(2);
}

async function findJobs() {
  const data = await withBusy("Matching jobs…", () =>
    api.matchJobs({
      profile: state.profile,
      target_role: state.chosenPath?.title,
      preferred_language: state.language,
      simple_english: state.simpleEnglish,
    })
  );
  state.matches = data.matches || [];
  renderStep3List();
}

async function runJd() {
  state.jdText = document.getElementById("jdText").value;
  const match = await withBusy("Reading the advert…", () =>
    api.analyzeJd({
      profile: state.profile,
      job_description: state.jdText,
      preferred_language: state.language,
      simple_english: state.simpleEnglish,
    })
  );
  state.matches = [match];
  state.selectedMatch = match;
  renderMatch();
}

function renderStep3List() {
  setStep(4);
  document.getElementById("view-step3").innerHTML = `<div class="card">
    <h1>Matching jobs</h1>
    <p class="muted">AI-generated suggestions are examples, not live vacancies. Verify employers, pay, and availability independently.</p>
    <div class="cards">${ui.jobCards(state.matches)}</div>
    <div class="actions"><button type="button" class="ghost" id="back2">Back</button></div>
  </div>`;
  document.querySelectorAll("[data-job]").forEach((btn) => {
    btn.onclick = () => {
      state.selectedMatch = state.matches[Number(btn.dataset.job)];
      renderMatch();
    };
  });
  document.getElementById("back2").onclick = renderStep2;
}

function renderMatch() {
  setStep(4);
  document.getElementById("view-step3").innerHTML = ui.matchDetail(state.selectedMatch);
  document.getElementById("toApply").onclick = goApply;
  document.getElementById("readMatch").onclick = () =>
    voice.playText(
      `${state.selectedMatch.verdict}. Score ${state.selectedMatch.relevancy_score}. ${state.selectedMatch.reasoning}`,
      { slow: state.simpleEnglish }
    );
}

async function goApply() {
  const gaps = state.selectedMatch?.gaps || [];
  const [plan, tailored, cover, questions] = await withBusy("Strengthening your application…", () =>
    Promise.all([
      api.gapPlan({
        profile: state.profile,
        gaps,
        target_role: state.chosenPath?.title,
        preferred_language: state.language,
        simple_english: state.simpleEnglish,
      }),
      api.tailorCv({ ...ctx(), job: state.selectedMatch.job, job_description: state.jdText }),
      api.coverLetter({ ...ctx(), job: state.selectedMatch.job, job_description: state.jdText }),
      api.interviewQuestions({ ...ctx(), job: state.selectedMatch.job, job_description: state.jdText }),
    ])
  );
  state.gapPlan = plan.items || [];
  state.tailored = tailored;
  state.cover = cover;
  state.questions = questions.questions || [];
  state.excludedClaims = new Set(
    [...(tailored.truthfulness?.unsupported || []), ...(cover.truthfulness?.unsupported || [])].map((c) => c.claim)
  );
  renderApply();
}

function truthBadge(rep) {
  if (!rep) return "";
  return `<p><strong>Truthfulness check: ${rep.verified_count} of ${rep.total_count} claims verified</strong></p>`;
}

function renderApply() {
  setStep(5);
  const t = state.tailored || {};
  const cv = t.cv || {};
  const matchGaps = state.selectedMatch?.gaps || [];
  const unsupported = [...(t.truthfulness?.unsupported || []), ...(state.cover?.truthfulness?.unsupported || [])];

  const gapColumnHtml = (matchGaps.length ? matchGaps : (state.gapPlan || []))
    .map((g) => {
      const skillName = typeof g === "object" ? (g.skill || g.gap) : String(g);
      const label = typeof g === "object" && g.label ? g.label : "missing";
      const note = typeof g === "object" && g.note ? g.note : "";
      return `<div class="profile-card-item">
        <div class="row" style="justify-content: space-between; align-items: center;">
          <strong>${ui.escapeHtml(skillName)}</strong>
          <span class="badge ${label === 'missing' ? 'not_relevant' : 'partially_relevant'}">${ui.escapeHtml(label.replaceAll('_', ' '))}</span>
        </div>
        ${note ? `<p class="muted" style="margin: 0.2rem 0 0;">${ui.escapeHtml(note)}</p>` : ""}
      </div>`;
    })
    .join("");

  document.getElementById("view-step4").innerHTML = `<div class="card">
    <h1>Step 5: Strengthen Application & Tailor UK Resume</h1>
    ${truthBadge(t.truthfulness)}

    <div class="columns" style="align-items: start; margin-top: 1rem;">
      <div style="background: var(--bg); padding: 1rem; border-radius: 12px; border: 1px solid var(--line);">
        <h2>⚠️ Identified Skill & Background Gaps</h2>
        <p class="muted">Key gaps identified for target vacancy: <strong>${ui.escapeHtml(state.selectedMatch?.job?.title || state.chosenPath?.title || "Target Role")}</strong></p>
        <div class="stack" style="margin-bottom: 1rem;">
          ${gapColumnHtml || "<p>No critical gaps detected!</p>"}
        </div>
        
        <fieldset class="profile-section" style="margin-top: 1rem; background: var(--bg-card);">
          <legend>💡 Did you miss adding any skills or experience earlier?</legend>
          <p style="font-size: 0.9rem; margin-bottom: 0.5rem; color: var(--ink);">If you have relevant background, software, or qualifications that were not in your profile, add them here now to close these gaps and update your UK resume:</p>
          <textarea id="missedSkillsInput" rows="3" placeholder="e.g. I also have 2 years of Agile team leadership, Docker, and SQL experience..."></textarea>
          <div class="actions">
            <button type="button" class="accent" id="btnUpdateSkillsAndTailor">⚡ Add to Profile & Re-Tailor UK Resume</button>
          </div>
        </fieldset>

        <h3 style="margin-top: 1rem;">Recommended Action Plan</h3>
        <button type="button" id="readGaps">🔊 Read gap plan aloud</button>
        ${(state.gapPlan || [])
          .map(
            (g) => `<article class="path-card" style="margin-top: 0.5rem;"><h3>${ui.escapeHtml(g.gap)}</h3>
          <p>${ui.escapeHtml(g.how_to_address)}</p>
          <p><strong>This week:</strong> ${ui.escapeHtml(g.quick_win_this_week)}</p>
          <p class="muted">${ui.escapeHtml(g.free_resource_suggestion)}</p></article>`
          )
          .join("")}
      </div>

      <div>
        <h2>🇬🇧 UK-Styled Curriculum Vitae</h2>
        <div style="background: #ffffff; color: #111; padding: 1.25rem; border-radius: 8px; border: 1px solid #ccc; font-family: 'Calibri', 'Segoe UI', sans-serif;">
          <h2 style="margin: 0; color: #0f4c5c; border-bottom: 2px solid #0f4c5c; padding-bottom: 0.3rem;">${ui.escapeHtml(state.profile.name || "CURRICULUM VITAE")}</h2>
          <p style="margin: 0.2rem 0 0.8rem; font-size: 0.9rem; color: #555;">${ui.escapeHtml(state.profile.location || "United Kingdom")}</p>

          <h3 style="color: #0f4c5c; border-bottom: 1px solid #ddd; margin: 0.8rem 0 0.3rem; font-size: 1.05rem;">PROFESSIONAL STATEMENT</h3>
          <p style="margin: 0 0 0.8rem; line-height: 1.4;">${ui.escapeHtml(cv.summary || state.profile.summary)}</p>

          <h3 style="color: #0f4c5c; border-bottom: 1px solid #ddd; margin: 0.8rem 0 0.3rem; font-size: 1.05rem;">KEY COMPETENCIES & SKILLS</h3>
          <p style="margin: 0 0 0.8rem; font-weight: 500;">${ui.escapeHtml((cv.skills || []).join(" • "))}</p>

          <h3 style="color: #0f4c5c; border-bottom: 1px solid #ddd; margin: 0.8rem 0 0.3rem; font-size: 1.05rem;">PROFESSIONAL EXPERIENCE</h3>
          ${(cv.experience || [])
            .map((exp) => `<div style="margin-bottom: 0.8rem;">
              <strong>${ui.escapeHtml(exp.title)}</strong> — <em>${ui.escapeHtml(exp.employer)} (${ui.escapeHtml(exp.country)})</em> <span style="float:right;">${ui.escapeHtml(exp.years)}</span>
              <ul style="margin: 0.3rem 0 0 1.2rem; padding: 0;">${(exp.achievements || []).map(a => `<li>${ui.escapeHtml(a)}</li>`).join("")}</ul>
            </div>`)
            .join("")}

          <h3 style="color: #0f4c5c; border-bottom: 1px solid #ddd; margin: 0.8rem 0 0.3rem; font-size: 1.05rem;">EDUCATION & QUALIFICATIONS</h3>
          ${(cv.education || [])
            .map((ed) => `<p style="margin: 0 0 0.3rem;"><strong>${ui.escapeHtml(ed.qualification)}</strong>, ${ui.escapeHtml(ed.institution)} (${ui.escapeHtml(ed.country)}, ${ui.escapeHtml(ed.year)})</p>`)
            .join("")}
        </div>
      </div>
    </div>

    <h3 style="margin-top: 1.5rem;">UK ATS Alignment Enhancements & Changes</h3>
    ${(t.changes || [])
      .map(
        (c, i) => `<label class="change"><input type="checkbox" data-ch="${i}" checked />
      <span>${ui.escapeHtml(c.reason)}</span>
      <small class="muted">${ui.escapeHtml(c.original)} → ${ui.escapeHtml(c.revised)}</small></label>`
      )
      .join("")}

    ${unsupported.length ? `<h3>Unsupported claims (excluded from download unless kept)</h3>${unsupported.map((c) => `<div class="claim bad">${ui.escapeHtml(c.claim)} — ${ui.escapeHtml(c.evidence_or_reason)} <button type="button" data-rm="${ui.escapeHtml(c.claim)}">Remove</button></div>`).join("")}` : ""}

    <h2 style="margin-top: 1.5rem;">UK-Styled Cover Letter</h2>
    <pre style="white-space:pre-wrap; background: var(--bg); padding: 1rem; border-radius: 8px;">${ui.escapeHtml(state.cover?.letter || "")}</pre>

    <h2>Interview Preparation</h2>
    <ol>${state.questions
      .map(
        (q) =>
          `<li><strong>${ui.escapeHtml(q.question)}</strong><br/><span class="muted">${ui.escapeHtml(q.type)} — ${ui.escapeHtml(q.why_they_ask)}</span></li>`
      )
      .join("")}</ol>

    <div class="actions">
      <button type="button" id="dlCv" class="primary">📥 Download UK CV (.docx)</button>
      <button type="button" id="dlLetter">📥 Download Cover Letter (.docx)</button>
      <button type="button" class="accent" id="toInterview">🎙️ Practise Interview</button>
      <button type="button" class="ghost" id="back3">Back</button>
    </div>
  </div>`;

  document.getElementById("btnUpdateSkillsAndTailor")?.addEventListener("click", async () => {
    const extra = document.getElementById("missedSkillsInput")?.value.trim();
    if (extra) {
      state.profile.summary = (state.profile.summary + " " + extra).trim();
      const newSkills = extra.split(",").map((s) => s.trim()).filter(Boolean);
      state.profile.skills = Array.from(new Set([...(state.profile.skills || []), ...newSkills]));
    }
    await goApply();
  });

  document.querySelectorAll("[data-rm]").forEach((btn) => {
    btn.onclick = () => {
      state.excludedClaims.add(btn.dataset.rm);
      btn.parentElement.remove();
    };
  });
  document.getElementById("readGaps").onclick = () =>
    voice.playText(state.gapPlan.map((g) => `${g.gap}. ${g.how_to_address}`).join(" "), {
      slow: state.simpleEnglish,
    });
  document.getElementById("dlCv").onclick = () =>
    api.exportDoc({
      kind: "cv",
      cv: state.tailored.cv,
      name: state.profile.name,
      excluded_claims: [...state.excludedClaims],
    });
  document.getElementById("dlLetter").onclick = () =>
    api.exportDoc({ kind: "cover_letter", letter: state.cover.letter, name: state.profile.name });
  document.getElementById("toInterview").onclick = renderInterviewSetup;
  document.getElementById("back3").onclick = renderMatch;
}

function renderInterviewSetup() {
  setStep(6);
  document.getElementById("view-step5").innerHTML = `<div class="card">
    <h1>Interview prep</h1>
    <p>This is practice only. The interviewer will say it is an AI. Interview questions and replies will be spoken automatically using ElevenLabs.</p>
    <label>Difficulty
      <select id="diff"><option>friendly</option><option selected>realistic</option><option>tough</option></select>
    </label>
    <label>English
      <select id="eng"><option value="simple">simple</option><option value="standard" ${state.simpleEnglish ? "" : "selected"}>standard</option></select>
    </label>
    <div class="actions">
      <button type="button" class="primary" id="startIv">Start 5-question mock interview</button>
      <button type="button" class="ghost" id="back4">Back</button>
    </div>
    <div id="ivChat"></div>
  </div>`;
  document.getElementById("startIv").onclick = startInterview;
  document.getElementById("back4").onclick = renderApply;
}

async function startInterview() {
  const body = {
    ...ctx(),
    difficulty: document.getElementById("diff").value,
    english_level: document.getElementById("eng").value,
    num_questions: 5,
    language_for_feedback: state.language,
  };
  const turn = await withBusy("Starting interview…", () => api.interviewStart(body));
  state.interview = turn;
  state.sessionId = turn.session_id;
  state.chat = [{ role: "bot", text: turn.interviewer }];
  state.lastQuestion = turn.interviewer;
  paintChat();
  speakInterviewTurn(turn.interviewer);
}

function speakInterviewTurn(text) {
  voice.playText(text, {
    slow: state.simpleEnglish,
    statusElementId: "interviewAudioStatus",
  });
}

function paintChat() {
  const iv = state.interview || { question_index: 1, total_questions: 5 };
  const root = document.getElementById("view-step5");
  root.innerHTML = `<div class="card">
    <h1>Mock interview</h1>
    <p>Question ${iv.question_index} of ${iv.total_questions}</p>
    <div class="chat" id="chat">
      ${state.chat
        .map((m) => `<div class="bubble ${m.role === "bot" ? "bot" : "me"}">${ui.escapeHtml(m.text)}</div>`)
        .join("")}
    </div>
    <p id="interviewAudioStatus" class="muted" aria-live="polite">Interview audio will play automatically.</p>
    <label>Your answer
      <textarea id="answerBox" rows="4"></textarea>
    </label>
    <div class="actions">
      <button type="button" class="primary" id="sendAns">Send</button>
      <button type="button" id="replay">Replay question</button>
      <button type="button" id="skip">Skip</button>
      <button type="button" id="slower">Slower</button>
      <button type="button" id="evalNow">Get evaluation</button>
    </div>
    <div id="evalDash"></div>
  </div>`;
  document.getElementById("sendAns").onclick = sendAnswer;
  document.getElementById("replay").onclick = () =>
    voice.playText(state.lastQuestion, { slow: state.simpleEnglish });
  document.getElementById("slower").onclick = () => voice.playText(state.lastQuestion, { slow: true });
  document.getElementById("skip").onclick = () => {
    document.getElementById("answerBox").value = "I would like to skip this question and practise another.";
    sendAnswer();
  };
  document.getElementById("evalNow").onclick = runEval;
}

async function sendAnswer() {
  const text = document.getElementById("answerBox").value.trim();
  if (!text) return;
  state.chat.push({ role: "me", text });
  const turn = await withBusy("Thinking…", () =>
    api.interviewAnswer({ session_id: state.sessionId, answer: text })
  );
  if (maybeSafety(turn)) return;
  state.interview = turn;
  state.chat.push({ role: "bot", text: turn.interviewer });
  state.lastQuestion = turn.interviewer;
  paintChat();
  if (!turn.done) speakInterviewTurn(turn.interviewer);
  if (turn.done) runEval();
}

async function runEval() {
  const ev = await withBusy("Marking your answers…", () => api.interviewEvaluate(state.sessionId));
  state.evaluation = ev;
  const dash = document.getElementById("evalDash");
  if (!dash) return;
  const o = ev.overall || {};
  dash.innerHTML = `<h2>Interview Evaluation</h2>
    ${ui.scoreRow("Overall Performance Score", o.score || 0)}
    <p>Filler words detected: <strong>${o.filler_words_count}</strong> · Average answer length: <strong>${o.avg_answer_length_words} words</strong></p>
    <p><strong>Top Strengths:</strong> ${(o.top_3_strengths || []).join("; ")}</p>
    <p><strong>Key Areas for Growth:</strong> ${(o.top_3_improvements || []).join("; ")}</p>
    <p style="background: var(--accent-soft); padding: 0.65rem 0.9rem; border-radius: 8px;"><strong>Focus for Next Practice:</strong> ${ui.escapeHtml(o.next_practice_focus || "")}</p>
    
    <h3 style="margin-top: 1.5rem;">Detailed Question Evaluation & Exemplar Answers</h3>
    ${(ev.per_answer || [])
      .map(
        (a, i) => {
          let exemplarText = a.perfect_candidate_answer || a.improved_sample_answer || "";
          exemplarText = exemplarText.replace(/^For [^:]+:\s*/i, "").trim();
          return `<article class="card" style="margin-bottom: 1rem; border: 1px solid var(--line);">
            <h3>Question ${i + 1}: ${ui.escapeHtml(a.question)}</h3>
            <p><strong>Your Response:</strong> <em>"${ui.escapeHtml(a.answer || "No response provided")}"</em></p>
            ${ui.scoreRow("Relevance", a.scores?.relevance || 0)}
            ${ui.scoreRow("STAR Structure", a.scores?.structure_STAR || 0)}
            ${ui.scoreRow("Clarity & Confidence", a.scores?.clarity || 0)}
            
            <div style="background: var(--bg); padding: 0.85rem; border-radius: 8px; margin-top: 0.75rem;">
              <p><strong>Situation:</strong> ${ui.escapeHtml(a.star_breakdown?.situation || "N/A")}</p>
              <p><strong>Task:</strong> ${ui.escapeHtml(a.star_breakdown?.task || "N/A")}</p>
              <p><strong>Action:</strong> ${ui.escapeHtml(a.star_breakdown?.action || "N/A")}</p>
              <p><strong>Result:</strong> ${ui.escapeHtml(a.star_breakdown?.result || "N/A")}</p>
              ${(a.star_breakdown?.missing_parts || []).length ? `<p class="muted">Missing STAR elements: ${(a.star_breakdown.missing_parts).join(", ")}</p>` : ""}
            </div>

            <div style="background: #eef9f5; border: 1px solid var(--ok); padding: 0.85rem; border-radius: 8px; margin-top: 0.75rem;">
              <h4 style="margin: 0 0 0.4rem; color: #14532d;">🌟 Perfect Candidate Exemplar Answer</h4>
              <p style="margin: 0 0 0.5rem; line-height: 1.4; color: #14242b;">${ui.escapeHtml(exemplarText)}</p>

              <p id="exemplarAudioStatus-${i}" class="muted" aria-live="polite"></p>
              <div class="actions" style="margin-top: 0.75rem;">
                <button type="button" class="accent btn-listen-exemplar" data-text="${ui.escapeHtml(exemplarText)}">🔊 Listen to Exemplar Answer (Tom — ElevenLabs)</button>
              </div>
            </div>
          </article>`;
        }
      )
      .join("")}
    <div class="actions"><button type="button" class="primary" id="toHandoff">Share summary with a human adviser</button></div>`;

  document.querySelectorAll(".btn-listen-exemplar").forEach((btn) => {
    btn.onclick = () => {
      const text = btn.dataset.text;
      const index = Array.from(document.querySelectorAll(".btn-listen-exemplar")).indexOf(btn);
      voice.playText(text, {
        slow: state.simpleEnglish,
        statusElementId: `exemplarAudioStatus-${index}`,
      });
    };
  });
  document.getElementById("toHandoff").onclick = openHandoff;
}

function openHandoff() {
  show("view-handoff");
  document.getElementById("view-handoff").innerHTML = `<div class="card">
    <h1>Share with a human adviser</h1>
    <p>Nothing is emailed. You copy or download after consent.</p>
    <label class="consent"><input type="checkbox" id="handoffConsent" /> I agree to share this summary with an adviser</label>
    <button type="button" class="primary" id="makeHandoff" disabled>Generate summary</button>
    <pre id="handoffOut" style="white-space:pre-wrap"></pre>
    <div class="actions">
      <button type="button" id="copyHandoff">Copy</button>
      <button type="button" id="dlHandoff">Download .docx</button>
    </div>
  </div>`;
  const box = document.getElementById("handoffConsent");
  const btn = document.getElementById("makeHandoff");
  box.onchange = () => {
    btn.disabled = !box.checked;
  };
  btn.onclick = async () => {
    const data = await withBusy("Writing adviser brief…", () =>
      api.handoffSummary({
        profile: state.profile,
        chosen_path: state.chosenPath,
        matches: state.matches.slice(0, 3),
        gaps: state.selectedMatch?.gaps || [],
        interview_eval: state.evaluation,
        safety_flags: state.safetyFlags,
        preferences: state.profile?.constraints || [],
        consent: true,
        preferred_language: state.language,
        simple_english: state.simpleEnglish,
      })
    );
    state.handoff = data.summary;
    document.getElementById("handoffOut").textContent = data.summary;
  };
  document.getElementById("copyHandoff").onclick = async () => {
    await navigator.clipboard.writeText(state.handoff || "");
  };
  document.getElementById("dlHandoff").onclick = () =>
    api.exportDoc({ kind: "handoff", handoff_text: state.handoff || "", name: state.profile?.name });
}

function resetAll() {
  api.deleteSession(state.sessionId).catch(() => {});
  Object.assign(state, {
    sessionId: crypto.randomUUID(),
    privacy: false,
    profile: null,
    paths: [],
    chosenPath: null,
    matches: [],
    selectedMatch: null,
    tailored: null,
    cover: null,
    interview: null,
    chat: [],
    evaluation: null,
    handoff: null,
    safetyFlags: [],
    step: 0,
  });
  document.getElementById("progressNav").hidden = true;
  show("view-privacy");
}

function bind() {
  document.getElementById("privacyOk").onchange = (e) => {
    document.getElementById("acceptPrivacy").disabled = !e.target.checked;
  };
  document.getElementById("acceptPrivacy").onclick = () => {
    state.privacy = true;
    fillProfileForm(state.profile || {});
    setStep(1);
  };
  const loadDemoBtn = document.getElementById("loadDemo");
  if (loadDemoBtn) loadDemoBtn.onclick = loadDemo;
  document.getElementById("language").onchange = (e) => {
    state.language = e.target.value;
    if (state.profile) state.profile.preferred_language = state.language;
  };
  document.getElementById("simpleEnglish").onchange = (e) => {
    state.simpleEnglish = e.target.checked;
    if (state.profile) state.profile.simple_english = state.simpleEnglish;
  };
  document.querySelectorAll("input[name=mode]").forEach((r) => {
    r.onchange = () => {
      state.voiceMode = r.value === "voice";
      document.getElementById("voiceBar").classList.toggle("hidden", !state.voiceMode);
    };
  });
  document.getElementById("deleteData").onclick = resetAll;
  document.getElementById("openHandoff").onclick = openHandoff;
  document.getElementById("safetyClose").onclick = () =>
    document.getElementById("safetyModal").classList.add("hidden");
  document.getElementById("safetyHandoff").onclick = () => {
    document.getElementById("safetyModal").classList.add("hidden");
    openHandoff();
  };
  document.getElementById("fromText").onclick = async () => {
    const text = document.getElementById("profileText").value;
    if (!text.trim()) return;
    const data = await withBusy("Extracting structured profile from your text…", () =>
      api.profileFromText({
        text,
        preferred_language: state.language,
        simple_english: state.simpleEnglish,
      })
    );
    if (maybeSafety(data)) return;
    state.profile = data.profile;
    fillProfileForm(state.profile);
    const notice = document.getElementById("extractNotice");
    if (notice) {
      notice.innerHTML = `<div style="background: var(--accent-soft); border: 1px solid var(--accent); padding: 0.65rem 0.9rem; border-radius: 8px; font-weight: 600; color: var(--ink); margin: 0.6rem 0;">✓ Profile extracted! All fields have been populated below. Review and edit any field before proceeding.</div>`;
    }
    document.getElementById("profileForm")?.scrollIntoView({ behavior: "smooth" });
  };
  document.getElementById("uploadCv").onclick = async () => {
    const file = document.getElementById("cvFile").files[0];
    if (!file) return;
    const data = await withBusy("Extracting structured profile from CV file…", () =>
      api.uploadCv(file, state.language, state.simpleEnglish)
    );
    state.profile = data.profile;
    fillProfileForm(state.profile);
    const notice = document.getElementById("extractNotice");
    if (notice) {
      notice.innerHTML = `<div style="background: var(--accent-soft); border: 1px solid var(--accent); padding: 0.65rem 0.9rem; border-radius: 8px; font-weight: 600; color: var(--ink); margin: 0.6rem 0;">✓ Profile extracted from file! All fields have been populated below. Review and edit any field before proceeding.</div>`;
    }
    document.getElementById("profileForm")?.scrollIntoView({ behavior: "smooth" });
  };
  document.getElementById("saveProfile").onclick = goCareers;
  document.getElementById("speakProfile").onclick = async () => {
    document.getElementById("voiceBar").classList.remove("hidden");
    voice.setStatus("Press and hold the mic, then tell your story.");
  };
  document.querySelectorAll("#progressNav button").forEach((btn) => {
    btn.onclick = () => {
      const n = Number(btn.parentElement.dataset.step);
      if (n === 1) setStep(1);
      if (n === 2 && state.paths.length) setStep(2);
      if (n === 3 && state.chosenPath) renderStep2();
      if (n === 4 && state.matches.length) renderStep3List();
      if (n === 5 && state.tailored) renderApply();
      if (n === 6 && state.chosenPath) renderInterviewSetup();
    };
  });
  voice.wireMic((text) => {
    if (state.step === 6) {
      const box = document.getElementById("answerBox");
      if (box) {
        box.value = text;
        sendAnswer();
      }
    } else {
      const ta = document.getElementById("profileText");
      if (ta) {
        ta.value = (ta.value + " " + text).trim();
      }
    }
  }, () => state.language);
  api.health().then((h) => {
    console.log("Health check:", h)
    if (!h.elevenlabs) voice.setStatus("Voice keys missing — type instead. Text mode still works.");
  });
}

bind();
