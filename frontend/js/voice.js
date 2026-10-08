import { stt, tts } from "./api.js";

let mediaRecorder = null;
let chunks = [];
let stream = null;

export function setStatus(text) {
  const el = document.getElementById("voiceStatus");
  if (el) el.textContent = text;
}

export async function playText(text, { slow = false, statusElementId } = {}) {
  if (!text) return;
  const updatePlaybackStatus = (t) => {
    const element = statusElementId && document.getElementById(statusElementId);
    if (element) element.textContent = t;
  };
  if (!("speechSynthesis" in window)) {
    setStatus("Text-to-speech not supported in this browser.");
    updatePlaybackStatus("Text-to-speech not supported.");
    return;
  }
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = slow ? 0.8 : 1.0;
    utterance.lang = "en-GB";

    utterance.onstart = () => {
      setStatus("Speaking…");
      updatePlaybackStatus("Speaking now…");
    };
    utterance.onend = () => {
      setStatus("Voice ready");
      updatePlaybackStatus("Audio finished.");
    };
    utterance.onerror = () => {
      setStatus("Voice ready");
      updatePlaybackStatus("Audio playback finished or cancelled.");
    };

    window.speechSynthesis.speak(utterance);
  } catch (err) {
    const message = err.message || "Could not speak text.";
    setStatus(message);
    updatePlaybackStatus(`Audio unavailable: ${message}`);
  }
}

export async function startRecording() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    setStatus("Microphone permission denied. You can still type.");
    return false;
  }
  chunks = [];
  const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
  mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data);
  };
  mediaRecorder.start();
  document.getElementById("micBtn")?.classList.add("live");
  setStatus("Listening…");
  return true;
}

export function stopRecording() {
  return new Promise((resolve) => {
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      resolve(null);
      return;
    }
    mediaRecorder.onstop = () => {
      stream?.getTracks().forEach((t) => t.stop());
      document.getElementById("micBtn")?.classList.remove("live");
      const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
      resolve(blob);
    };
    mediaRecorder.stop();
  });
}

export async function captureAndTranscribe(language) {
  setStatus("Transcribing…");
  const blob = await stopRecording();
  if (!blob || blob.size < 800) {
    setStatus("I did not catch that. Try again or type.");
    return "";
  }
  try {
    const result = await stt(blob, language);
    setStatus("Voice ready");
    return result.text || "";
  } catch (err) {
    setStatus(err.message || "Could not transcribe. Please type.");
    return "";
  }
}

export function wireMic(onText, getLanguage) {
  const btn = document.getElementById("micBtn");
  if (!btn) return;
  const start = async () => {
    await startRecording();
  };
  const end = async () => {
    const text = await captureAndTranscribe(getLanguage());
    if (text) onText(text);
  };
  btn.addEventListener("mousedown", start);
  btn.addEventListener("mouseup", end);
  btn.addEventListener("mouseleave", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") end();
  });
  btn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    start();
  });
  btn.addEventListener("touchend", (e) => {
    e.preventDefault();
    end();
  });
}
