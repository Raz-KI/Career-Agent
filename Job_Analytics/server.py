"""PathWay job tracker + AI insights. Run: pip install -r requirements.txt && python server.py -> http://localhost:8001"""
import os, json, requests
from flask import Flask, request, jsonify

app = Flask(__name__, static_folder="static", static_url_path="")
# Hard-coded for now, as requested. Server-side only: it is never sent to the browser. Move to an env var before sharing this folder.
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY") or ""
AGENT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".coach_agent_id")

# Dummy CV until the upload step exists.
CV = {"name": "Alex Morgan", "title": "Frontend developer",
      "summary": "Software developer with experience building web applications. Looking for a new opportunity.",
      "skills": ["javascript", "react", "html", "css", "figma", "git", "python", "prototyping"],
      "bullets": ["Built and maintained customer dashboards", "Worked with designers on new features",
                  "Improved page load time by 35% across the main app", "Fixed bugs and supported releases"]}
CV_SKILLS = set(CV["skills"])
POS = ("interview", "offer")

def norm(l): return [str(x).strip().lower() for x in (l or []) if str(x).strip()]

def stats(jobs):
    c = lambda s: sum(1 for j in jobs if j.get("s") == s)
    return {"total": len(jobs), "interview": c("interview"), "offer": c("offer"), "rejected": c("rejected"), "waiting": c("applied")}

def groups(jobs, key):
    d = {}
    for j in jobs:
        g = d.setdefault(j.get(key) or "Other", [0, 0]); g[0] += 1; g[1] += j.get("s") in POS
    rows = [{"name": k, "n": v[0], "pos": v[1], "rate": round(100 * v[1] / v[0])} for k, v in d.items()]
    return sorted(rows, key=lambda r: (-r["rate"], -r["pos"], -r["n"]))

def missing_skills(jobs):
    need = {}
    for j in jobs:
        for s in norm(j.get("skills")):
            if s not in CV_SKILLS: need[s] = need.get(s, 0) + 1
    return [k for k, _ in sorted(need.items(), key=lambda kv: -kv[1])][:4]

def matches(jobs):
    out = []
    for j in jobs:
        sk = norm(j.get("skills"))
        if not sk: continue
        have = [s for s in sk if s in CV_SKILLS]
        out.append({"role": j.get("role"), "co": j.get("co"), "desc": j.get("desc", ""), "s": j.get("s"),
                    "match": round(100 * len(have) / len(sk)), "missing": [s for s in sk if s not in CV_SKILLS]})
    return sorted(out, key=lambda m: -m["match"])[:3]

def headline(st):
    t, iv, of, rj = st["total"], st["interview"], st["offer"], st["rejected"]
    if t == 0: return {"tone": "info", "title": "No applications yet", "text": "Add a few applications and I'll start spotting patterns."}
    if of: return {"tone": "good", "title": f"You have {of} offer{'s' if of > 1 else ''}", "text": "Great work. Compare the offers, and keep your other applications warm until you decide."}
    if t >= 5 and iv == 0:
        return {"tone": "warn", "title": f"You have applied to {t} jobs but have no interviews yet",
                "text": "That usually means the CV is not landing or the roles are a stretch. Let's review your CV first."}
    if iv >= 1 and (iv >= 2 or rj >= 2):
        return {"tone": "warn", "title": f"You are getting interviews ({iv}) but no offers yet",
                "text": "Your CV is working. The next gain is in the interview itself, so practise answering out loud."}
    if iv >= 1: return {"tone": "good", "title": "You have an interview", "text": "Good start. Prepare for it now while the role is fresh."}
    return {"tone": "info", "title": f"{t} application{'s' if t > 1 else ''} so far", "text": "It is early. Keep applying and check back after about five."}

def cv_feedback(jobs):
    tips, miss = [], missing_skills(jobs)
    if miss: tips.append("Roles you applied to often ask for " + ", ".join(miss) + ", which your CV does not mention. Add them if you have them, or plan to learn them.")
    if len(CV["summary"].split()) < 25 or "opportunity" in CV["summary"]:
        tips.append("Your summary is generic. Name your target role and two strengths, for example 'Frontend developer focused on accessible React apps'.")
    plain = [b for b in CV["bullets"] if not any(ch.isdigit() for ch in b)]
    if plain: tips.append(f"{len(plain)} of {len(CV['bullets'])} experience bullets have no result or number. Rewrite them like your page-load bullet, which shows a 35% gain.")
    tips.append("Tailor the top third of the CV to each job title, using the same keywords as the job description.")
    return tips

def build(jobs):
    st = stats(jobs); pos = st["interview"] + st["offer"]
    cat, typ = groups(jobs, "cat"), groups(jobs, "type")
    best = [r for r in cat + typ if r["pos"] > 0][:2]
    if pos == 0: ptxt = "No positive responses yet, so there is no pattern to report. Keep applying across a few different role types."
    else: ptxt = "Most positive responses so far: " + "; ".join(f"{r['name']} ({r['pos']} of {r['n']})" for r in best) + ". Lean into these."
    iv = st["interview"] >= 1 and st["offer"] == 0
    return {"stats": st, "headline": headline(st), "cv": cv_feedback(jobs),
            "patterns": {"text": ptxt, "category": cat, "type": typ}, "matches": matches(jobs),
            "interview": {"emphasis": iv, "text": "Practise answering common questions out loud, and prepare two or three stories with a clear result." if iv
                          else "Nothing urgent here yet. Interview practice will help once interviews start coming in."},
            "missing": missing_skills(jobs)}

# ---------- ElevenLabs: coach agent that writes the insight text ----------
ITEMS = {
 "headline": "Two plain, encouraging sentences summarising where the job search stands. Use only the figures in the data.",
 "cv_feedback": "Three short sentences of specific CV feedback, using the CV, the skills the jobs asked for, and the application results. Only use facts from the data.",
 "positive_patterns": "Two sentences on which kinds of jobs (category, work type) got the most positive responses (interviews or offers). Only use the data.",
 "strongest_matches": "Two sentences naming the strongest-matching job titles and why, based on skill overlap. Only use the data.",
 "interview_advice": "Two sentences of interview advice. If the person has interviews but no offers, tell them to practise interviews more. Otherwise say what to do before interviews start."}

def _xi(method, path, **kw):
    r = requests.request(method, "https://api.elevenlabs.io" + path, headers={"xi-api-key": ELEVENLABS_API_KEY}, timeout=180, **kw)
    if r.status_code >= 400: raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()

def coach_agent():
    if os.environ.get("ELEVENLABS_AGENT_ID"): return os.environ["ELEVENLABS_AGENT_ID"]
    if os.path.exists(AGENT_FILE): return open(AGENT_FILE).read().strip()
    j = _xi("POST", "/v1/convai/agents/create", json={"name": "PathWay job search coach",
        "conversation_config": {"agent": {"first_message": "Hello.", "prompt": {"prompt":
            "You are a supportive UK job search coach. The user message holds JSON about a job seeker's dashboard, CV and applications. Be specific, honest and kind. Never invent facts."}}},
        "platform_settings": {"data_collection": {k: {"type": "string", "description": v} for k, v in ITEMS.items()}}})
    open(AGENT_FILE, "w").write(j["agent_id"]); return j["agent_id"]

def ai_text(jobs, facts):
    ctx = {"cv": CV, "stats": facts["stats"], "jobs": [{k: j.get(k) for k in ("role", "co", "cat", "type", "s", "skills")} for j in jobs],
           "positive_rate_by_category": facts["patterns"]["category"], "positive_rate_by_type": facts["patterns"]["type"],
           "strongest_matches": facts["matches"], "skills_missing_from_cv": facts["missing"]}
    j = _xi("POST", f"/v1/convai/agents/{coach_agent()}/simulate-conversation", json={
        "simulation_specification": {"simulated_user_config": {"prompt": {"prompt": "Reply with one short thank-you."}},
            "partial_conversation_history": [{"role": "agent", "message": "Share your job search data.", "time_in_call_secs": 0},
                                             {"role": "user", "message": json.dumps(ctx), "time_in_call_secs": 0}]},
        "new_turns_limit": 1})
    res = j["analysis"]["data_collection_results"]
    return {k: (res.get(k) or {}).get("value") or "" for k in ITEMS}

@app.get("/")
def home(): return app.send_static_file("index.html")

@app.post("/api/insights")
def insights():
    jobs = (request.get_json(force=True) or {}).get("jobs", [])[:200]
    out = build(jobs); out["engine"] = "rules"
    if jobs:
        try:
            out["ai"] = ai_text(jobs, out); out["engine"] = "elevenlabs"
        except Exception as e:
            print("[insights] ElevenLabs failed, showing built-in analysis:", e)
    return jsonify(out)

if __name__ == "__main__":
    app.run(port=8001, debug=False)
