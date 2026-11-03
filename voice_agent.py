"""
AI Sales & Business Calling Agent - local prototype (Phase 1)
Runs fully on your laptop:
  microphone -> faster-whisper (speech to text) -> Ollama (draft answer)
  -> pyttsx3 (text to speech) -> speaker

Usage:
  python voice_agent.py           voice mode (microphone + speaker)
  python voice_agent.py --text    typing mode (test without microphone)
"""

import csv
import datetime as dt
import json
import os
import re
import sys

import requests

# ---------- Settings ----------
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"
WHISPER_MODEL = "base"          # "tiny" = faster, "small" = more accurate
WHISPER_LANGUAGE = None         # None = auto-detect (Hindi/English); "en" = force English
SAMPLE_RATE = 16000
RECORD_SECONDS = 6
FAQ_FILE = "business_faq.json"
LOG_FILE = "call_logs.csv"
AUDIO_FILE = "last_input.wav"
STOP_WORDS = ["stop", "exit", "quit", "bye"]
LEAD_TRIGGERS = ["demo", "interested", "callback", "call back", "book",
                 "buy", "purchase", "appointment", "chahiye"]
FALLBACK = ("I'm sorry, I don't have that confirmed information. "
            "I can arrange a follow-up with our team so they can help you.")
LOG_FIELDS = ["timestamp", "customer_said", "agent_said", "lead_interest",
              "lead_requirement", "lead_followup", "lead_callback_consent"]
LEAD_QUESTIONS = [
    ("lead_interest", "Great! Which product or service are you interested in?"),
    ("lead_requirement", "What is your main requirement?"),
    ("lead_followup", "What day and time would suit you for a follow-up? Our team will confirm it."),
    ("lead_callback_consent", "May we call you back to share more details? Please say yes or no."),
]
SYSTEM_RULES = """You are a polite sales/business calling assistant for {company}.
You are an AI assistant. If asked, say so clearly.
Rules:
- Keep replies short (1 to 3 sentences), natural and easy to understand.
- Use ONLY the approved company information below for company facts.
- Never invent prices, discounts, guarantees, availability or confirmed bookings.
- If the answer is not in the information, say you do not have that detail and offer a human follow-up.
- Ask at most one question at a time.
- Reply in the same language the customer used (English, Hindi, or Hinglish).

Approved company information:
{info}
"""

_whisper = None


# ---------- Helpers ----------
def load_faq():
    with open(FAQ_FILE, encoding="utf-8") as f:
        return json.load(f)


def tokens(text):
    return set(re.findall(r"[a-z0-9]+|[\u0900-\u097F]+", text.lower()))


def find_faq_match(question, faq):
    """Simple keyword matching to find the most relevant approved FAQ."""
    q = tokens(question)
    best, best_score = None, 0
    for item in faq.get("faqs", []):
        keys = set()
        for k in item.get("keywords", []):
            keys |= tokens(k)
        score = len(q & keys)
        if score > best_score:
            best, best_score = item, score
    return best


def is_stop(text):
    t = text.lower()
    return any(re.search(rf"\b{w}\b", t) for w in STOP_WORDS) or "band karo" in t


def has_invented_facts(reply, faq):
    """Safety check: any number in the reply must exist in the approved FAQ file."""
    source = json.dumps(faq, ensure_ascii=False)
    return any(n not in source for n in re.findall(r"\d+", reply))


# ---------- Brain (Ollama) ----------
def ask_llm(question, faq, history, match):
    info = json.dumps(faq, ensure_ascii=False, indent=2)
    system = SYSTEM_RULES.format(company=faq.get("company_name", "our company"), info=info)
    if match:
        system += f"\nMost relevant approved answer: {match['answer']}\n"
    messages = [{"role": "system", "content": system}] + history[-6:]
    messages.append({"role": "user", "content": question})
    resp = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 120},
    }, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def answer(question, faq, history):
    match = find_faq_match(question, faq)
    fallback = match["answer"] if match else FALLBACK
    try:
        reply = ask_llm(question, faq, history, match)
    except Exception as e:
        print(f"[Ollama not reachable: {e}] Make sure the Ollama app is running.")
        return fallback
    if not reply or has_invented_facts(reply, faq):
        return fallback
    return reply


# ---------- Ears (microphone + speech to text) ----------
def record_audio():
    import sounddevice as sd
    from scipy.io import wavfile
    print(f"Recording {RECORD_SECONDS} seconds... speak now")
    audio = sd.rec(int(RECORD_SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="int16")
    sd.wait()
    wavfile.write(AUDIO_FILE, SAMPLE_RATE, audio)


def transcribe():
    global _whisper
    import numpy as np
    from scipy.io import wavfile
    from faster_whisper import WhisperModel
    if _whisper is None:
        print("Loading speech model (first run may download it)...")
        _whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    rate, audio = wavfile.read(AUDIO_FILE)
    audio = audio.flatten().astype(np.float32) / 32768.0
    segments, _ = _whisper.transcribe(audio, language=WHISPER_LANGUAGE,
                                      beam_size=1, vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()

def get_input(text_mode):
    if text_mode:
        return input("You: ").strip()
    cmd = input("\nPress Enter and speak (or type 'stop' to quit): ").strip()
    if is_stop(cmd):
        return cmd
    record_audio()
    said = transcribe()
    print(f"You (heard): {said or '[nothing heard]'}")
    return said


# ---------- Mouth (text to speech) ----------
def speak(text):
    print(f"Agent: {text}")
    try:
        import pyttsx3
        engine = pyttsx3.init()          # fresh engine each time avoids pyttsx3 hangs
        engine.setProperty("rate", 165)
        if re.search(r"[\u0900-\u097F]", text):   # Devanagari text: try a Hindi voice
            for v in engine.getProperty("voices"):
                if "hindi" in (v.name + str(v.languages)).lower():
                    engine.setProperty("voice", v.id)
                    break
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"[speech output unavailable: {e}] (the text reply is shown above)")


# ---------- Logging and lead flow ----------
def log_row(**fields):
    row = {f: "" for f in LOG_FIELDS}
    row["timestamp"] = dt.datetime.now().isoformat(timespec="seconds")
    row.update(fields)
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def run_lead_flow(text_mode):
    speak("Sure, I can help with that. I will ask you a few quick questions.")
    lead = {}
    for key, question in LEAD_QUESTIONS:
        speak(question)
        reply = get_input(text_mode)
        if is_stop(reply):
            return None
        if key == "lead_callback_consent":
            reply = "yes" if re.search(r"\b(yes|yeah|yep|haan|ha|ok|okay|sure)\b",
                                       reply.lower()) else "no"
        lead[key] = reply
    speak("Thank you. I have noted your details. I cannot confirm a booking myself, "
          "but our team will confirm the follow-up.")
    return lead


# ---------- Main loop ----------
def main():
    text_mode = "--text" in sys.argv
    faq = load_faq()
    history = []
    print(f"=== {faq.get('company_name')} AI assistant | mode: "
          f"{'TEXT' if text_mode else 'VOICE'} ===")
    speak(f"Hello, I am an AI assistant for {faq.get('company_name')}. How can I help you today?")

    while True:
        said = get_input(text_mode)
        if is_stop(said):
            speak("Thank you for your time. Goodbye!")
            break
        if not said:
            speak("Sorry, I did not catch that. Could you please repeat?")
            continue

        if any(t in said.lower() for t in LEAD_TRIGGERS):
            lead = run_lead_flow(text_mode)
            if lead is None:
                speak("Thank you for your time. Goodbye!")
                break
            if lead["lead_callback_consent"] == "yes":
                log_row(customer_said=said, agent_said="[lead captured]",
                        lead_interest=lead["lead_interest"],
                        lead_requirement=lead["lead_requirement"],
                        lead_followup=lead["lead_followup"],
                        lead_callback_consent="yes")
            else:
                log_row(customer_said=said,
                        agent_said="[lead not stored: no callback consent]",
                        lead_callback_consent="no")
            continue

        reply = answer(said, faq, history)
        speak(reply)
        history += [{"role": "user", "content": said},
                    {"role": "assistant", "content": reply}]
        log_row(customer_said=said, agent_said=reply)

    print(f"Session ended. Log saved to {LOG_FILE}")


if __name__ == "__main__":
    main()