# PathWay — AI Career Agent

An honest, multilingual career navigator for people rebuilding work in the UK — including displaced people, Ukrainian refugees, carers returning to work, and anyone facing a language barrier or a career gap.

Built for CulturaLinks' "Career Access" brief (AI for Social Good): understand career options, match jobs, strengthen applications, prepare for interviews. Voice interview practice uses ElevenLabs (STT + TTS) from the backend only.

## The problem

A nurse with 12 years' experience in Kyiv is not "unskilled" in Manchester — but a UK application that quietly implies NMC registration, NHS experience, or local references can harm her. PathWay is built to stay truthful, name regulated routes without promising licences, and hand off to a human adviser.

## Architecture

```
  Browser (HTML/CSS/JS)          FastAPI (stateless + in-memory sessions)
  ----------------------         ---------------------------------------
  Text | Voice toggle            /api/profile   CV parse + extract
  6-step stepper                 /api/careers   UK paths + regulation notes
  MediaRecorder mic              /api/jobs      LLM role suggestions (+ Reed if keyed)
  <audio> playback               /api/application  CV, letter, truthfulness
                                 /api/interview    mock session dict
                                 /api/voice        ElevenLabs STT/TTS
                                 /api/handoff      adviser brief
                                         |
                         llm.py  -->  Gemini Studio (preferred)
                                 -->  Anthropic (fallback)
                         voice.py --> ElevenLabs REST
```

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # then add keys
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000/

### Keys

| Variable | Required for |
|---|---|
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Coaching, matching, CV, interview (preferred) |
| `ANTHROPIC_API_KEY` | Fallback if Gemini is unset |
| `LLM_MODEL` | e.g. `gemini-2.5-flash` |
| `ELEVENLABS_API_KEY` | Voice mode (STT Scribe + TTS) |
| `ELEVENLABS_VOICE_ID` | Default `JBFqnCBsd6RMkjVDRZzb` |
| `REED_API_KEY` | Optional live UK vacancies |

Without ElevenLabs keys, **text mode still works**. Interview questions and interviewer replies are spoken automatically when ElevenLabs is configured; voice mode additionally enables microphone answers. Generating role suggestions requires an LLM key; if generation fails, the app reports the error rather than displaying hardcoded jobs. Suggestions are illustrative role ideas, not live vacancies. Optional Reed results are live listings when a Reed key is configured.

## Demo script (~2 minutes)

1. Click **Load demo profile (Ukrainian nurse)**.
2. Glance at Olena's profile (B1 English, childcare gap, **not** NMC registered) → Save.
3. Choose **Healthcare Assistant (bridge role)** — note the regulated Nurse/NMC card is honest.
4. **Find matching jobs** → review AI-generated role suggestions based on the profile; these are not live vacancies.
5. **Strengthen application** → truthfulness badge, reject any red claim, download `.docx`.
6. Start the 5-question mock interview; questions and interviewer replies are spoken automatically. Turn on **Voice** to answer using the microphone.
7. Open **Share summary with a human adviser**, tick consent, copy/download. Nothing is emailed.

## Responsible AI

- **Truthfulness guard**: second LLM pass + heuristics (NMC PIN, QTS, DBS already held, right-to-work "confirmed"). Unsupported claims are red, "Remove", and excluded from downloads by default.
- **Safety**: keyword rules + classifier for visa/legal requests, exploitation (passport withheld), abuse, distress, fabrication. Signposts GOV.UK, ACAS, Citizens Advice, 999, Samaritans 116 123. No immigration advice.
- **Privacy**: no database; in-memory interview sessions; **Delete my data**; privacy notice before use.
- **Employment info** is grounded in `backend/data/uk_guidance.md`.

## Tests

```bash
pytest -q
python -m backend.tests.eval_demo
```

## Assumptions

- Demo city is Manchester; profile details can be reviewed and edited before career suggestions.
- Gemini is the default provider even though `.env.example` also lists `ANTHROPIC_API_KEY` (sponsor stack + easy swap in `llm.py`).
- "Simple English" slows TTS (~0.8×) and asks the model for short sentences.
- AI-generated role suggestions are matched against the profile; optional Reed listings are added when a key is present.
- Handoff is copy/download only — no email integration.

## Limitations

- Not a regulated immigration, legal, or clinical service.
- LLM matching can still miss nuance; always review the CV.
- STT quality depends on mic and B1 accented English; typing always works.
- Sessions vanish on server restart.

## Roadmap

- Live job APIs beyond Reed; adviser dashboard; more languages.
- Real-time ElevenLabs Agents for conversational interviews.
- Pilot with councils, colleges, and CulturaLinks advisers.

## Disclaimer

AI guidance, not legal or immigration advice. Verify with official sources. This tool supports human advisers; it doesn't replace them.
