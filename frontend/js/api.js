const LANG_HINT = { en: "en", uk: "uk", pl: "pl", ru: "ru", ar: "ar", es: "es", ro: "ro" };

async function api(path, { method = "GET", json, form } = {}) {
  const opts = { method, headers: {} };
  if (json !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(json);
  }
  if (form) opts.body = form;
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const data = await res.json();
    if (!res.ok) {
      const err = new Error(data.detail || data.error || res.statusText);
      err.payload = data;
      throw err;
    }
    return data;
  }
  if (!res.ok) throw new Error(await res.text());
  return res;
}

export const health = () => api("/api/health");
export const getDemo = () => api("/api/profile/demo");
export const profileFromText = (body) => api("/api/profile/from_text", { method: "POST", json: body });
export const uploadCv = (file, preferred_language, simple_english) => {
  const form = new FormData();
  form.append("file", file);
  form.append("preferred_language", preferred_language);
  form.append("simple_english", simple_english);
  return api("/api/profile/upload", { method: "POST", form });
};
export const careerOptions = (body) => api("/api/careers/options", { method: "POST", json: body });
export const matchJobs = (body) => api("/api/jobs/match", { method: "POST", json: body });
export const analyzeJd = (body) => api("/api/jobs/analyze_jd", { method: "POST", json: body });
export const gapPlan = (body) => api("/api/application/gap_plan", { method: "POST", json: body });
export const tailorCv = (body) => api("/api/application/tailor_cv", { method: "POST", json: body });
export const coverLetter = (body) => api("/api/application/cover_letter", { method: "POST", json: body });
export const interviewQuestions = (body) => api("/api/interview/questions", { method: "POST", json: body });
export const interviewStart = (body) => api("/api/interview/start", { method: "POST", json: body });
export const interviewAnswer = (body) => api("/api/interview/answer", { method: "POST", json: body });
export const interviewEvaluate = (session_id) =>
  api("/api/interview/evaluate", { method: "POST", json: { session_id } });
export const safetyCheck = (text, preferred_language) =>
  api("/api/safety/check", { method: "POST", json: { text, preferred_language } });
export const handoffSummary = (body) => api("/api/handoff/summary", { method: "POST", json: body });
export const deleteSession = (session_id) =>
  api("/api/session/delete", { method: "POST", json: { session_id } });
export const insights = (jobs, custom_cv) =>
  api("/api/insights", { method: "POST", json: { jobs, custom_cv } });
export const languageTest = (text, target_role) =>
  api("/api/profile/language_test", { method: "POST", json: { text, target_role } });

export async function exportDoc(body) {
  const res = await fetch("/api/application/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download =
    body.kind === "cv" ? "pathway-cv.docx" : body.kind === "cover_letter" ? "pathway-cover-letter.docx" : "pathway-brief.docx";
  a.click();
  URL.revokeObjectURL(url);
}

export async function stt(blob, language) {
  const form = new FormData();
  form.append("file", blob, "answer.webm");
  form.append("language_code", LANG_HINT[language] || language || "");
  return api("/api/voice/stt", { method: "POST", form });
}

export async function tts(text, speed) {
  const res = await fetch("/api/voice/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, speed }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Voice playback unavailable");
  }
  return res.blob();
}
