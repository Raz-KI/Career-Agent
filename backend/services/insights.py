"""Job search tracker & AI insights service."""

from __future__ import annotations

import json
import logging
import os

import httpx

from backend.config import get_settings

logger = logging.getLogger("pathway.insights")

# Default demo CV for insights calculation
DEFAULT_CV = {
    "name": "Alex Morgan",
    "title": "Frontend developer",
    "summary": "Software developer with experience building web applications. Looking for a new opportunity.",
    "skills": ["javascript", "react", "html", "css", "figma", "git", "python", "prototyping"],
    "bullets": [
        "Built and maintained customer dashboards",
        "Worked with designers on new features",
        "Improved page load time by 35% across the main app",
        "Fixed bugs and supported releases",
    ],
}

ITEMS = {
    "headline": "Two plain, encouraging sentences summarising where the job search stands. Use only the figures in the data.",
    "cv_feedback": "Three short sentences of specific CV feedback, using the CV, the skills the jobs asked for, and the application results. Only use facts from the data.",
    "positive_patterns": "Two sentences on which kinds of jobs (category, work type) got the most positive responses (interviews or offers). Only use the data.",
    "strongest_matches": "Two sentences naming the strongest-matching job titles and why, based on skill overlap. Only use the data.",
    "interview_advice": "Two sentences of interview advice. If the person has interviews but no offers, tell them to practise interviews more. Otherwise say what to do before interviews start.",
}

POS = ("interview", "offer")


def norm(lst: list | None) -> list[str]:
    return [str(x).strip().lower() for x in (lst or []) if str(x).strip()]


def stats(jobs: list[dict]) -> dict:
    c = lambda s: sum(1 for j in jobs if j.get("s") == s)
    return {
        "total": len(jobs),
        "interview": c("interview"),
        "offer": c("offer"),
        "rejected": c("rejected"),
        "waiting": c("applied"),
    }


def groups(jobs: list[dict], key: str) -> list[dict]:
    d: dict[str, list[int]] = {}
    for j in jobs:
        g = d.setdefault(j.get(key) or "Other", [0, 0])
        g[0] += 1
        g[1] += 1 if j.get("s") in POS else 0
    rows = [{"name": k, "n": v[0], "pos": v[1], "rate": round(100 * v[1] / v[0]) if v[0] else 0} for k, v in d.items()]
    return sorted(rows, key=lambda r: (-r["rate"], -r["pos"], -r["n"]))


def missing_skills(jobs: list[dict], cv_skills: set[str]) -> list[str]:
    need: dict[str, int] = {}
    for j in jobs:
        for s in norm(j.get("skills")):
            if s not in cv_skills:
                need[s] = need.get(s, 0) + 1
    return [k for k, _ in sorted(need.items(), key=lambda kv: -kv[1])][:4]


def matches(jobs: list[dict], cv_skills: set[str]) -> list[dict]:
    out = []
    for j in jobs:
        sk = norm(j.get("skills"))
        if not sk:
            continue
        have = [s for s in sk if s in cv_skills]
        out.append(
            {
                "role": j.get("role"),
                "co": j.get("co"),
                "desc": j.get("desc", ""),
                "s": j.get("s"),
                "match": round(100 * len(have) / len(sk)),
                "missing": [s for s in sk if s not in cv_skills],
            }
        )
    return sorted(out, key=lambda m: -m["match"])[:3]


def headline(st: dict) -> dict:
    t, iv, of, rj = st["total"], st["interview"], st["offer"], st["rejected"]
    if t == 0:
        return {"tone": "info", "title": "No applications yet", "text": "Add a few applications and I'll start spotting patterns."}
    if of:
        return {"tone": "good", "title": f"You have {of} offer{'s' if of > 1 else ''}", "text": "Great work. Compare the offers, and keep your other applications warm until you decide."}
    if t >= 5 and iv == 0:
        return {
            "tone": "warn",
            "title": f"You have applied to {t} jobs but have no interviews yet",
            "text": "That usually means the CV is not landing or the roles are a stretch. Let's review your CV first.",
        }
    if iv >= 1 and (iv >= 2 or rj >= 2):
        return {
            "tone": "warn",
            "title": f"You are getting interviews ({iv}) but no offers yet",
            "text": "Your CV is working. The next gain is in the interview itself, so practise answering out loud.",
        }
    if iv >= 1:
        return {"tone": "good", "title": "You have an interview", "text": "Good start. Prepare for it now while the role is fresh."}
    return {"tone": "info", "title": f"{t} application{'s' if t > 1 else ''} so far", "text": "It is early. Keep applying and check back after about five."}


def cv_feedback(jobs: list[dict], cv_data: dict, cv_skills: set[str]) -> list[str]:
    tips = []
    miss = missing_skills(jobs, cv_skills)
    if miss:
        tips.append(
            "Roles you applied to often ask for "
            + ", ".join(miss)
            + ", which your CV does not mention. Add them if you have them, or plan to learn them."
        )
    summary = cv_data.get("summary", "")
    if len(summary.split()) < 25 or "opportunity" in summary:
        tips.append(
            "Your summary is generic. Name your target role and two strengths, for example 'Frontend developer focused on accessible React apps'."
        )
    bullets = cv_data.get("bullets") or []
    plain = [b for b in bullets if not any(ch.isdigit() for ch in b)]
    if plain:
        tips.append(
            f"{len(plain)} of {len(bullets)} experience bullets have no result or number. Rewrite them like your page-load bullet, which shows a 35% gain."
        )
    tips.append("Tailor the top third of the CV to each job title, using the same keywords as the job description.")
    return tips


def build_insights(jobs: list[dict], custom_cv: dict | None = None) -> dict:
    cv_data = custom_cv or DEFAULT_CV
    cv_skills = set(norm(cv_data.get("skills", [])))
    st = stats(jobs)
    pos = st["interview"] + st["offer"]
    cat, typ = groups(jobs, "cat"), groups(jobs, "type")
    best = [r for r in cat + typ if r["pos"] > 0][:2]
    if pos == 0:
        ptxt = "No positive responses yet, so there is no pattern to report. Keep applying across a few different role types."
    else:
        ptxt = "Most positive responses so far: " + "; ".join(f"{r['name']} ({r['pos']} of {r['n']})" for r in best) + ". Lean into these."
    iv = st["interview"] >= 1 and st["offer"] == 0
    miss = missing_skills(jobs, cv_skills)
    mat = matches(jobs, cv_skills)
    return {
        "stats": st,
        "headline": headline(st),
        "cv": cv_feedback(jobs, cv_data, cv_skills),
        "patterns": {"text": ptxt, "category": cat, "type": typ},
        "matches": mat,
        "interview": {
            "emphasis": iv,
            "text": "Practise answering common questions out loud, and prepare two or three stories with a clear result."
            if iv
            else "Nothing urgent here yet. Interview practice will help once interviews start coming in.",
        },
        "missing": miss,
        "engine": "rules",
    }
