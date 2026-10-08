export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function showBusy(text) {
  const b = document.getElementById("busy");
  document.getElementById("busyText").textContent = text || "Thinking…";
  b.classList.remove("hidden");
}

export function hideBusy() {
  document.getElementById("busy").classList.add("hidden");
}

export function renderProfileForm(profile) {
  const listText = (items, sep = ", ") => (items || []).join(sep);

  const expItems = profile.experience && profile.experience.length
    ? profile.experience
    : [{ title: "", employer: "", country: "", years: "", achievements: [] }];

  const expList = expItems
    .map((exp, i) => `
      <div class="profile-card-item exp-item" data-index="${i}">
        <div class="row">
          <label class="grow">Job Title<input type="text" class="pf-exp-title" value="${escapeHtml(exp.title)}" placeholder="e.g. Software Engineer / Nurse" /></label>
          <label class="grow">Employer / Company<input type="text" class="pf-exp-employer" value="${escapeHtml(exp.employer)}" placeholder="e.g. TechCorp / NHS Trust" /></label>
        </div>
        <div class="row">
          <label class="grow">Country / City<input type="text" class="pf-exp-country" value="${escapeHtml(exp.country)}" placeholder="e.g. UK / Kyiv" /></label>
          <label class="grow">Years / Dates<input type="text" class="pf-exp-years" value="${escapeHtml(exp.years)}" placeholder="e.g. 2019 - 2023" /></label>
        </div>
        <label>Key Achievements / Responsibilities <span class="muted">(separate with semicolons ;)</span>
          <input type="text" class="pf-exp-achievements" value="${escapeHtml((exp.achievements || []).join("; "))}" placeholder="e.g. Built REST APIs; Managed team of 5" />
        </label>
        <button type="button" class="ghost btn-remove-item remove-exp" title="Remove experience">✕ Remove role</button>
      </div>
    `).join("");

  const eduItems = profile.education && profile.education.length
    ? profile.education
    : [{ qualification: "", institution: "", country: "", year: "" }];

  const eduList = eduItems
    .map((edu, i) => `
      <div class="profile-card-item edu-item" data-index="${i}">
        <div class="row">
          <label class="grow">Qualification / Degree<input type="text" class="pf-edu-qual" value="${escapeHtml(edu.qualification)}" placeholder="e.g. BSc Computer Science" /></label>
          <label class="grow">Institution / University<input type="text" class="pf-edu-inst" value="${escapeHtml(edu.institution)}" placeholder="e.g. Kyiv National University" /></label>
        </div>
        <div class="row">
          <label class="grow">Country<input type="text" class="pf-edu-country" value="${escapeHtml(edu.country)}" placeholder="e.g. Ukraine / UK" /></label>
          <label class="grow">Year Completed<input type="text" class="pf-edu-year" value="${escapeHtml(edu.year)}" placeholder="e.g. 2018" /></label>
        </div>
        <button type="button" class="ghost btn-remove-item remove-edu" title="Remove qualification">✕ Remove qualification</button>
      </div>
    `).join("");

  const langItems = profile.languages && profile.languages.length
    ? profile.languages
    : [{ language: "English", level: "Fluent" }];

  const langList = langItems
    .map((lang, i) => `
      <div class="profile-card-item lang-item" data-index="${i}">
        <div class="row">
          <label class="grow">Language<input type="text" class="pf-lang-name" value="${escapeHtml(lang.language)}" placeholder="e.g. English, Ukrainian, Polish" /></label>
          <label class="grow">Proficiency Level<input type="text" class="pf-lang-level" value="${escapeHtml(lang.level)}" placeholder="e.g. Fluent, Native, B2" /></label>
        </div>
        <button type="button" class="ghost btn-remove-item remove-lang" title="Remove language">✕ Remove language</button>
      </div>
    `).join("");

  return `
    <fieldset class="profile-section">
      <legend>👤 Personal & Location Details</legend>
      <div class="row">
        <label class="grow">Full Name<input id="pf-name" type="text" value="${escapeHtml(profile.name)}" placeholder="e.g. Olena Shevchenko" /></label>
        <label class="grow">Current Location / Preferred Area<input id="pf-location" type="text" value="${escapeHtml(profile.location)}" placeholder="e.g. Manchester, UK" /></label>
      </div>
      <label>Professional Summary
        <textarea id="pf-summary" rows="3" placeholder="Brief summary of your professional background, strengths, and career goals...">${escapeHtml(profile.summary)}</textarea>
      </label>
    </fieldset>

    <fieldset class="profile-section">
      <legend>💡 Key Skills & Technologies</legend>
      <label>Skills <span class="muted">(separate with commas)</span>
        <textarea id="pf-skills" rows="2" placeholder="e.g. Python, SQL, React, Project Management, Customer Support">${escapeHtml(listText(profile.skills))}</textarea>
      </label>
    </fieldset>

    <fieldset class="profile-section">
      <legend>💼 Work Experience</legend>
      <div id="pf-experience-container" class="stack">
        ${expList}
      </div>
      <button type="button" id="add-exp-btn" class="accent">+ Add Work Experience</button>
    </fieldset>

    <fieldset class="profile-section">
      <legend>🎓 Education & Qualifications</legend>
      <div id="pf-education-container" class="stack">
        ${eduList}
      </div>
      <button type="button" id="add-edu-btn" class="accent">+ Add Qualification</button>
    </fieldset>

    <fieldset class="profile-section">
      <legend>🗣️ Languages Spoken</legend>
      <div id="pf-languages-container" class="stack">
        ${langList}
      </div>
      <button type="button" id="add-lang-btn" class="accent">+ Add Language</button>
    </fieldset>

    <fieldset class="profile-section">
      <legend>📜 Certifications, Gaps & Preferences</legend>
      <label>Certifications & Licences <span class="muted">(separate with commas)</span>
        <input id="pf-certifications" type="text" value="${escapeHtml(listText(profile.certifications))}" placeholder="e.g. AWS Certified, NMC Registered Nurse, ACCA" />
      </label>
      <label>Career Gaps / Breaks <span class="muted">(separate with commas)</span>
        <input id="pf-gaps_or_breaks" type="text" value="${escapeHtml(listText(profile.gaps_or_breaks))}" placeholder="e.g. Relocation gap 2022-2023, Parental leave" />
      </label>
      <label>Work Preferences & Constraints <span class="muted">(separate with commas)</span>
        <input id="pf-constraints" type="text" value="${escapeHtml(listText(profile.constraints))}" placeholder="e.g. Remote / Hybrid, Full-time, Visa support" />
      </label>
    </fieldset>
  `;
}

export function readProfileForm(base) {
  const split = (v, sep = ",") =>
    v
      ? v
          .split(sep)
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

  const experience = [];
  document.querySelectorAll(".exp-item").forEach((el) => {
    const title = el.querySelector(".pf-exp-title")?.value.trim() || "";
    const employer = el.querySelector(".pf-exp-employer")?.value.trim() || "";
    const country = el.querySelector(".pf-exp-country")?.value.trim() || "";
    const years = el.querySelector(".pf-exp-years")?.value.trim() || "";
    const achievementsStr = el.querySelector(".pf-exp-achievements")?.value || "";
    const achievements = achievementsStr
      .split(";")
      .map((a) => a.trim())
      .filter(Boolean);
    if (title || employer) {
      experience.push({ title, employer, country, years, achievements });
    }
  });

  const education = [];
  document.querySelectorAll(".edu-item").forEach((el) => {
    const qualification = el.querySelector(".pf-edu-qual")?.value.trim() || "";
    const institution = el.querySelector(".pf-edu-inst")?.value.trim() || "";
    const country = el.querySelector(".pf-edu-country")?.value.trim() || "";
    const year = el.querySelector(".pf-edu-year")?.value.trim() || "";
    if (qualification || institution) {
      education.push({ qualification, institution, country, year });
    }
  });

  const languages = [];
  document.querySelectorAll(".lang-item").forEach((el) => {
    const language = el.querySelector(".pf-lang-name")?.value.trim() || "";
    const level = el.querySelector(".pf-lang-level")?.value.trim() || "";
    if (language) {
      languages.push({ language, level });
    }
  });

  return {
    ...base,
    name: document.getElementById("pf-name")?.value.trim() || "",
    location: document.getElementById("pf-location")?.value.trim() || "",
    summary: document.getElementById("pf-summary")?.value.trim() || "",
    skills: split(document.getElementById("pf-skills")?.value),
    certifications: split(document.getElementById("pf-certifications")?.value),
    experience,
    education,
    languages,
    gaps_or_breaks: split(document.getElementById("pf-gaps_or_breaks")?.value),
    constraints: split(document.getElementById("pf-constraints")?.value),
  };
}

export function pathCards(paths) {
  return `<div class="cards">${paths
    .map(
      (p, i) => `<article class="path-card">
      <h3>${escapeHtml(p.title)}</h3>
      ${p.regulated_profession ? `<span class="badge reg">Regulated — verify with official body</span>` : ""}
      <p>${escapeHtml(p.why_it_fits)}</p>
      <p class="muted">${escapeHtml(p.typical_salary_range_gbp)} · ${escapeHtml(p.time_to_ready)} · ${escapeHtml(p.difficulty)}</p>
      <p>${escapeHtml(p.regulation_note)}</p>
      <ol>${(p.first_three_steps || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>
      <button type="button" data-choose="${i}">Choose this path</button>
    </article>`
    )
    .join("")}</div>`;
}

export function jobCards(matches) {
  return matches
    .map((m, i) => {
      const job = m.job || {};
      return `<article class="job-card">
        <h3>${escapeHtml(job.title)}</h3>
        ${job.sector === "ai-generated"
          ? `<p class="badge">AI-generated suggestion · not a live vacancy</p><p>${escapeHtml(job.location)} · ${escapeHtml(job.salary)}</p>`
          : `<p>${escapeHtml(job.employer)} · ${escapeHtml(job.location)} · ${escapeHtml(job.salary)}</p>`}
        <span class="badge ${escapeHtml(m.verdict)}">${escapeHtml((m.verdict || "").replaceAll("_", " "))}</span>
        <p>Relevancy ${m.relevancy_score}/100</p>
        <div class="gauge" aria-label="Relevancy ${m.relevancy_score}"><span style="width:${m.relevancy_score}%"></span></div>
        <button type="button" data-job="${i}">Open match analysis</button>
      </article>`;
    })
    .join("");
}

export function matchDetail(m) {
  const job = m.job || {};
  return `<div class="card">
    <h2>${escapeHtml(job.title)}</h2>
    ${job.sector === "ai-generated"
      ? `<p class="badge">AI-generated suggestion · not a live vacancy</p>`
      : `<p>${escapeHtml(job.employer)}</p>`}
    <p>${escapeHtml(job.description || "")}</p>
    <span class="badge ${escapeHtml(m.verdict)}">${escapeHtml((m.verdict || "").replaceAll("_", " "))}</span>
    <p><strong>${m.relevancy_score}/100</strong></p>
    <div class="gauge"><span style="width:${m.relevancy_score}%"></span></div>
    <p>${escapeHtml(m.reasoning)}</p>
    <button type="button" id="readMatch">🔊 Read this aloud</button>
    <div class="columns">
      <div><h3>Matched (with evidence)</h3><ul>${(m.matched_skills || [])
        .map((s) => `<li><strong>${escapeHtml(s.skill)}</strong> — ${escapeHtml(s.evidence)}</li>`)
        .join("")}</ul></div>
      <div><h3>Gaps</h3><ul>${(m.gaps || [])
        .map((g) => `<li>${escapeHtml(g.skill)} <em>(${escapeHtml(g.label)})</em> ${escapeHtml(g.note || "")}</li>`)
        .join("")}</ul></div>
    </div>
    <div class="actions"><button type="button" class="primary" id="toApply">Strengthen this application</button></div>
  </div>`;
}

export function safetyDialog(flag) {
  document.getElementById("safetyMsg").textContent = flag.message || "";
  document.getElementById("safetyResources").innerHTML = (flag.resources || [])
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");
  document.getElementById("safetyModal").classList.remove("hidden");
}

export function scoreRow(label, n) {
  return `<p>${escapeHtml(label)} ${n}/100</p><div class="score-bar"><i style="width:${n}%"></i></div>`;
}
