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

const SpeechRecognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

let recognitionInstance = null;
let lastTranscript = "";

export function wireMic(onText, getLanguage) {
  const btn = document.getElementById("micBtn");
  if (!btn) return;

  if (SpeechRecognition) {
    btn.addEventListener("mousedown", (e) => {
      e.preventDefault();
      try {
        lastTranscript = "";
        recognitionInstance = new SpeechRecognition();
        recognitionInstance.continuous = true;
        recognitionInstance.interimResults = true;
        const lang = getLanguage ? getLanguage() : "en";
        recognitionInstance.lang = lang === "uk" ? "uk-UA" : lang === "pl" ? "pl-PL" : lang === "es" ? "es-ES" : "en-GB";

        recognitionInstance.onstart = () => {
          btn.classList.add("live");
          setStatus("Listening… speak into your microphone");
        };

        recognitionInstance.onresult = (event) => {
          let current = "";
          for (let i = 0; i < event.results.length; i++) {
            current += event.results[i][0].transcript;
          }
          lastTranscript = current;
        };

        recognitionInstance.onerror = (evt) => {
          btn.classList.remove("live");
          if (evt.error === "not-allowed") {
            setStatus("Microphone permission denied. You can type instead.");
          } else {
            setStatus("Speech recognition error. Please try again or type.");
          }
        };

        recognitionInstance.onend = () => {
          btn.classList.remove("live");
          setStatus("Voice ready");
          const text = lastTranscript.trim();
          if (text) {
            onText(text);
          } else {
            setStatus("No speech detected. Hold button to speak or type.");
          }
        };

        recognitionInstance.start();
      } catch (err) {
        console.warn("Speech recognition start error:", err);
      }
    });

    const stopMic = (e) => {
      e.preventDefault();
      if (recognitionInstance) {
        try {
          recognitionInstance.stop();
        } catch (err) {}
      }
    };

    btn.addEventListener("mouseup", stopMic);
    btn.addEventListener("mouseleave", stopMic);
    btn.addEventListener("touchend", stopMic);
  } else {
    btn.addEventListener("click", () => {
      const text = prompt("Default voice-to-text is not supported in this browser. Please type your answer:");
      if (text) onText(text);
    });
  }
}
