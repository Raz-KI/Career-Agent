"""Multi-language speaking test. ElevenLabs = examiner voice (TTS) + transcription (Scribe STT).
Run:  export ELEVENLABS_API_KEY=...   (scoring also runs on ElevenLabs, via an Agents examiner)
      pip install -r requirements.txt && python server.py   ->  http://localhost:8000
"""
import os, re, json, math, requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__, static_folder="static", static_url_path="")
XI_KEY = 'sk_3b035fa719e607ecb97bfa77146b1a6bc7f2326c4d269d38'
VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
TTS_MODEL = "eleven_multilingual_v2"
AGENT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".agent_id")
LIMITS = [30, 60, 90]  # seconds for parts 1-3

# name, [welcome, part1, part2, part3]
LANGS = {
 "en": ("English", ["Welcome to your speaking test. You will do three short tasks.",
  "Part one. Please introduce yourself: your name, where you are from, and what you do. You have thirty seconds.",
  "Part two. Describe a place you enjoy visiting and explain why. You have one minute.",
  "Part three. What is your opinion on technology and stress? Does technology make life more stressful? You have ninety seconds."]),
 "es": ("Spanish", ["Bienvenido a tu prueba oral. Harás tres tareas breves.",
  "Parte uno. Preséntate: tu nombre, de dónde eres y a qué te dedicas. Tienes treinta segundos.",
  "Parte dos. Describe un lugar que te guste visitar y explica por qué. Tienes un minuto.",
  "Parte tres. ¿Qué opinas de la tecnología y el estrés? ¿Hace la tecnología la vida más estresante? Tienes noventa segundos."]),
 "fr": ("French", ["Bienvenue à votre test oral. Vous allez faire trois courtes tâches.",
  "Partie un. Présentez-vous : votre nom, d'où vous venez et ce que vous faites. Vous avez trente secondes.",
  "Partie deux. Décrivez un lieu que vous aimez visiter et expliquez pourquoi. Vous avez une minute.",
  "Partie trois. Que pensez-vous de la technologie et du stress ? La technologie rend-elle la vie plus stressante ? Vous avez quatre-vingt-dix secondes."]),
 "de": ("German", ["Willkommen zu Ihrem Sprechtest. Sie bearbeiten drei kurze Aufgaben.",
  "Teil eins. Stellen Sie sich vor: Name, Herkunft und Beruf. Sie haben dreißig Sekunden.",
  "Teil zwei. Beschreiben Sie einen Ort, den Sie gern besuchen, und erklären Sie warum. Sie haben eine Minute.",
  "Teil drei. Was halten Sie von Technologie und Stress? Macht Technologie das Leben stressiger? Sie haben neunzig Sekunden."]),
 "it": ("Italian", ["Benvenuto al tuo test orale. Svolgerai tre brevi compiti.",
  "Parte uno. Presentati: nome, provenienza e lavoro. Hai trenta secondi.",
  "Parte due. Descrivi un luogo che ti piace visitare e spiega perché. Hai un minuto.",
  "Parte tre. Cosa pensi della tecnologia e dello stress? La tecnologia rende la vita più stressante? Hai novanta secondi."]),
 "pt": ("Portuguese", ["Bem-vindo ao seu teste oral. Você fará três tarefas curtas.",
  "Parte um. Apresente-se: seu nome, de onde você é e o que faz. Você tem trinta segundos.",
  "Parte dois. Descreva um lugar que você gosta de visitar e explique por quê. Você tem um minuto.",
  "Parte três. Qual é a sua opinião sobre tecnologia e estresse? A tecnologia torna a vida mais estressante? Você tem noventa segundos."]),
 "nl": ("Dutch", ["Welkom bij je spreektest. Je doet drie korte opdrachten.",
  "Deel één. Stel jezelf voor: je naam, waar je vandaan komt en wat je doet. Je hebt dertig seconden.",
  "Deel twee. Beschrijf een plek die je graag bezoekt en leg uit waarom. Je hebt een minuut.",
  "Deel drie. Wat vind je van technologie en stress? Maakt technologie het leven stressvoller? Je hebt negentig seconden."]),
 "pl": ("Polish", ["Witaj na teście mówienia. Wykonasz trzy krótkie zadania.",
  "Część pierwsza. Przedstaw się: imię, skąd pochodzisz i czym się zajmujesz. Masz trzydzieści sekund.",
  "Część druga. Opisz miejsce, które lubisz odwiedzać, i wyjaśnij dlaczego. Masz minutę.",
  "Część trzecia. Co sądzisz o technologii i stresie? Czy technologia sprawia, że życie jest bardziej stresujące? Masz dziewięćdziesiąt sekund."]),
 "sv": ("Swedish", ["Välkommen till ditt talprov. Du ska göra tre korta uppgifter.",
  "Del ett. Presentera dig: ditt namn, var du kommer ifrån och vad du gör. Du har trettio sekunder.",
  "Del två. Beskriv en plats du gillar att besöka och förklara varför. Du har en minut.",
  "Del tre. Vad tycker du om teknik och stress? Gör tekniken livet mer stressigt? Du har nittio sekunder."]),
 "ru": ("Russian", ["Добро пожаловать на устный тест. Вас ждут три коротких задания.",
  "Часть первая. Представьтесь: назовите имя, откуда вы и чем занимаетесь. У вас тридцать секунд.",
  "Часть вторая. Опишите место, которое вам нравится посещать, и объясните почему. У вас одна минута.",
  "Часть третья. Что вы думаете о технологиях и стрессе? Делают ли технологии жизнь более напряжённой? У вас девяносто секунд."]),
}
# Pronunciation counts for little: accents are expected from non-native speakers.
WEIGHTS = {"fluency": .20, "vocabulary": .25, "grammar": .25, "coherence": .25, "pronunciation": .05}
CRITERIA = list(WEIGHTS)
_tts_cache = {}

def clamp(x, lo=1.0, hi=5.0): return max(lo, min(hi, x))
def cefr(x):
    for lim, lvl in [(1.5, "A1"), (2.05, "A2"), (3.05, "B1"), (4.05, "B2"), (4.65, "C1")]:
        if x < lim: return lvl
    return "C2"

@app.get("/")
def home(): return app.send_static_file("index.html")

@app.get("/api/languages")
def languages():
    return jsonify([{"code": c, "name": v[0]} for c, v in LANGS.items()])

@app.get("/api/tasks")
def tasks():
    lang = request.args.get("lang", "en")
    if lang not in LANGS: return jsonify(error="Unsupported language"), 400
    t = LANGS[lang][1]  # [welcome, part1, part2, part3]
    return jsonify({"welcome": t[0],
                    "tasks": [{"part": i + 1, "text": t[i + 1], "limit": LIMITS[i]} for i in range(3)]})

@app.get("/api/tts")
def tts():
    if not XI_KEY: return jsonify(error="ELEVENLABS_API_KEY is not set on the server"), 500
    lang, idx = request.args.get("lang", "en"), int(request.args.get("i", 0))
    if lang not in LANGS or not 0 <= idx <= 3: return jsonify(error="Bad request"), 400
    key = (lang, idx)
    if key not in _tts_cache:
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
            headers={"xi-api-key": XI_KEY}, timeout=60,
            json={"text": LANGS[lang][1][idx], "model_id": TTS_MODEL})
        if r.status_code != 200: return jsonify(error="Text-to-speech failed", detail=r.text[:300]), 502
        _tts_cache[key] = r.content
    return Response(_tts_cache[key], mimetype="audio/mpeg")

def speech_metrics(words):
    w = [x for x in words if x.get("type") == "word"]
    if not w: return {"words": 0, "wpm": 0, "long_pauses": 0, "spoken": 0, "confidence": 0}
    conf = sum(math.exp(min(0, x.get("logprob", 0))) for x in w) / len(w)
    pauses = sum(1 for a, b in zip(w, w[1:]) if b["start"] - a["end"] > 0.8)
    spoken = max(w[-1]["end"] - w[0]["start"], 1)
    return {"words": len(w), "wpm": round(len(w) / spoken * 60), "long_pauses": pauses,
            "spoken": round(spoken, 1), "confidence": round(conf, 3)}

@app.post("/api/transcribe")
def transcribe():
    if not XI_KEY: return jsonify(error="ELEVENLABS_API_KEY is not set on the server"), 500
    f, lang = request.files.get("audio"), request.form.get("lang", "en")
    if not f or lang not in LANGS: return jsonify(error="Bad request"), 400
    r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": XI_KEY}, timeout=180,
        files={"file": (f.filename or "answer.webm", f.stream, f.mimetype or "audio/webm")},
        data={"model_id": "scribe_v1", "language_code": lang, "timestamps_granularity": "word", "tag_audio_events": "false"})
    if r.status_code != 200: return jsonify(error="Transcription failed", detail=r.text[:300]), 502
    j = r.json()
    return jsonify({"transcript": (j.get("text") or "").strip(), "metrics": speech_metrics(j.get("words", []))})

def pron_from_confidence(conf):
    """Intelligibility, not accent: if Scribe transcribed the words, pronunciation passes."""
    if conf >= .80: return 5.0
    if conf >= .65: return 4.0
    if conf >= .45: return 3.0
    return clamp(1 + conf * 4)

def heuristic_scores(parts):
    text = " ".join(p["transcript"] for p in parts)
    toks = re.findall(r"\w+", text.lower()); n = len(toks)
    ms = [p["metrics"] for p in parts]
    conf = sum(m["confidence"] * m["words"] for m in ms) / max(1, sum(m["words"] for m in ms))
    if n < 8:
        s = {c: 1.0 for c in CRITERIA}
        return s, {c: "Too little speech was captured to judge this." for c in CRITERIA}, \
               "Try again and speak for the full time, in complete sentences.", conf
    sents = max(1, len(re.findall(r"[.!?]+", text)))
    spoken = sum(m["spoken"] for m in ms); wpm = n / max(spoken, 1) * 60
    pauses_pm = sum(m["long_pauses"] for m in ms) / max(spoken / 60, .5)
    rttr = len(set(toks)) / math.sqrt(n)
    cover = min(1, spoken / (.6 * sum(LIMITS)))
    s = {"fluency": clamp(5 - abs(wpm - 130) / 25 - .5 * pauses_pm),
         "vocabulary": clamp(1 + (rttr - 3) * .8),
         "grammar": clamp(1 + (n / sents) / 6),
         "coherence": clamp(1 + 3.5 * cover + .5 * min(sents / 9, 1)),
         "pronunciation": pron_from_confidence(conf)}
    obs = {"fluency": f"About {round(wpm)} words per minute with {sum(m['long_pauses'] for m in ms)} long pauses.",
           "vocabulary": f"{len(set(toks))} different words across {n} spoken words.",
           "grammar": f"Average sentence length was {n / sents:.1f} words (estimated from the transcript).",
           "coherence": f"You spoke for about {round(cover * 100)}% of the time that was expected.",
           "pronunciation": "Your words were transcribed clearly, so this passes. Accent is not penalised." if conf >= .65
                            else "Some words were hard to transcribe. Slow down and say each word fully."}
    weakest = min(CRITERIA[:4], key=lambda c: s[c])
    return {k: round(v, 1) for k, v in s.items()}, obs, f"Focus next on {weakest}: practise answering aloud for the full time.", conf

RUBRIC = ("You are a language speaking examiner for non-native speakers. The conversation holds three speaking tasks (agent turns) "
  "and the candidate's transcribed answers (user turns), then examiner notes with speech metrics. "
  "Judge mainly the QUALITY OF THE ANSWERS as shown in the transcript: vocabulary, grammar, coherence and task fulfilment. "
  "Weight pronunciation LOW because accents are expected: if the words were transcribed correctly and are understandable, pronunciation is 4 or 5. "
  "Use pause counts, words per minute and transcription confidence only as supporting evidence for fluency.")
DESC = {
 "fluency": "Score 1-5 for fluency of the candidate's answers. 1 long pauses and broken speech; 3 some hesitation but keeps going; 5 smooth natural pace. Use the examiner notes. Explain in one concrete sentence.",
 "vocabulary": "Score 1-5 for vocabulary in the candidate's answers. 1 very basic; 3 adequate everyday range; 5 precise, varied, idiomatic. Explain in one concrete sentence.",
 "grammar": "Score 1-5 for grammar in the candidate's answers. 1 frequent errors that block meaning; 3 errors rarely block meaning; 5 accurate with complex structures. Explain in one concrete sentence.",
 "pronunciation": "Score 1-5 for intelligibility only, NOT accent. If the words were transcribed correctly and are understandable give 4 or 5. 1 hard to understand; 3 generally clear. Explain in one concrete sentence.",
 "coherence": "Score 1-5 for coherence. 1 ideas disconnected; 3 organised but basic; 5 well structured with linking and supported opinions. Explain in one concrete sentence."}

def _xi(method, path, **kw):
    r = requests.request(method, "https://api.elevenlabs.io" + path, headers={"xi-api-key": XI_KEY}, timeout=180, **kw)
    if r.status_code >= 400: raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()

def ensure_agent():
    """One examiner agent in your ElevenLabs account. Created on first use, id saved in .agent_id."""
    if os.environ.get("ELEVENLABS_AGENT_ID"): return os.environ["ELEVENLABS_AGENT_ID"]
    if os.path.exists(AGENT_FILE): return open(AGENT_FILE).read().strip()
    dc = {c: {"type": "number", "description": DESC[c]} for c in CRITERIA}
    dc["practice_tip"] = {"type": "string", "description": "One clear next step for practice, in English, one sentence."}
    j = _xi("POST", "/v1/convai/agents/create", json={"name": "PathWay speaking examiner",
        "conversation_config": {"agent": {"first_message": "Hello.", "prompt": {"prompt": RUBRIC}}},
        "platform_settings": {"data_collection": dc}})
    open(AGENT_FILE, "w").write(j["agent_id"])
    return j["agent_id"]

def eleven_scores(lang, parts):
    name = LANGS[lang][0]
    hist = [{"role": "agent", "message": f"Language being tested: {name}. The speaking test begins.", "time_in_call_secs": 0}]
    for i, p in enumerate(parts):
        hist.append({"role": "agent", "message": LANGS[lang][1][i + 1], "time_in_call_secs": 0})
        hist.append({"role": "user", "message": p["transcript"] or "(no speech)", "time_in_call_secs": 0})
    notes = "; ".join(f"Task {i+1}: {p['metrics']['wpm']} words/min, {p['metrics']['long_pauses']} long pauses, transcription confidence {p['metrics']['confidence']}"
                      for i, p in enumerate(parts))
    hist.append({"role": "agent", "message": "Examiner notes. " + notes, "time_in_call_secs": 0})
    j = _xi("POST", f"/v1/convai/agents/{ensure_agent()}/simulate-conversation", json={
        "simulation_specification": {"simulated_user_config": {"prompt": {"prompt": "Reply with one short thank-you."}},
                                     "partial_conversation_history": hist},
        "new_turns_limit": 1})
    res = j["analysis"]["data_collection_results"]
    scores = {c: clamp(float(res[c]["value"])) for c in CRITERIA}
    obs = {c: res[c].get("rationale") or "" for c in CRITERIA}
    return scores, obs, (res.get("practice_tip") or {}).get("value") or "Keep practising by answering aloud for the full time."

@app.post("/api/evaluate")
def evaluate():
    d = request.get_json(force=True); lang = d.get("lang", "en"); parts = d.get("parts", [])
    if lang not in LANGS or len(parts) != 3: return jsonify(error="Bad request"), 400
    scores, obs, tip, conf = heuristic_scores(parts)
    engine = "estimate"
    if XI_KEY:
        try:
            scores, obs, tip = eleven_scores(lang, parts)
            engine = "elevenlabs"
        except Exception as e:
            print("[scorer] ElevenLabs scoring failed, using estimate:", e)  # see your terminal
    if conf >= .65: scores["pronunciation"] = max(scores["pronunciation"], 4.0)  # clearly transcribable = pass
    overall = round(sum(scores[c] * WEIGHTS[c] for c in CRITERIA), 2)
    return jsonify({"scores": {k: round(v, 1) for k, v in scores.items()}, "observations": obs, "tip": tip,
                    "overall": overall, "cefr": cefr(overall), "engine": engine})

if __name__ == "__main__":
    app.run(port=8080, debug=False)
