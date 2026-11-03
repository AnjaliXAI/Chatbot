import csv
import datetime as dt
import json
import os

import requests
import streamlit as st
import streamlit.components.v1 as components

from voice_agent import load_faq, answer, log_row, find_faq_match

# ---------------- Page setup ----------------
st.set_page_config(page_title="AI Assistant", page_icon="✨", layout="wide",
                   initial_sidebar_state="expanded")

LEADS_FILE = "leads.csv"
LEAD_FIELDS = ["timestamp", "name", "email", "phone", "company",
               "requirement", "preferred_contact"]
CONTACT_WORDS = ["contact", "callback", "call back", "demo", "book", "connect",
                 "team", "human", "speak to", "talk to"]
GREETINGS = ["hi", "hello", "hey", "good morning", "good evening"]
STOP_SPEECH = "__STOP__"

# (icon, title, description, card gradient, accent colour, question sent to assistant)
OPTIONS = [
    ("🧭", "Explore Services", "Discover what we currently offer and who it is for.",
     "linear-gradient(135deg,#E0F7F4,#B2F5EA)", "#0D9488", "Tell me about your services"),
    ("💲", "Pricing Information", "Understand our pricing policy and how to get a quote.",
     "linear-gradient(135deg,#F3E8FF,#DDD6FE)", "#7C3AED", "What is the price?"),
    ("🎯", "Find a Solution", "Tell us your goal and we will suggest the right fit.",
     "linear-gradient(135deg,#FCE7F3,#FBCFE8)", "#DB2777", "Which solution is right for my business?"),
    ("🤝", "Connect with Our Team", "Send an enquiry and get a follow-up from our team.",
     "linear-gradient(135deg,#DBEAFE,#BFDBFE)", "#2563EB", None),
]

CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}
html, body, .stApp, p, label, input, textarea, button {
  font-family: 'Segoe UI', 'Inter', system-ui, sans-serif;}
.stApp {background: radial-gradient(circle at top left,#E6FFFA 0%,#F5F3FF 45%,#EEF4FF 100%);}
.block-container {max-width: 1100px; padding-top: 3.2rem !important; padding-bottom: 6rem;}

/* Sidebar */
[data-testid="stSidebar"] {background: linear-gradient(180deg,#0F172A 0%,#1E1B4B 100%);}
[data-testid="stSidebar"] * {color: #E2E8F0;}
[data-testid="stSidebar"] .stButton > button {
  background: transparent; border: none; text-align: left; justify-content: flex-start;
  color: #CBD5E1; font-size: 0.86rem; padding: 0.45rem 0.7rem; border-radius: 10px;
  width: 100%; box-shadow: none;}
[data-testid="stSidebar"] .stButton > button:hover {background: rgba(255,255,255,0.09); color: #fff;}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#2DD4BF,#7C3AED); color: #fff; font-weight: 600;
  justify-content: center; box-shadow: 0 8px 20px rgba(124,58,237,0.35);}
.brand {display:flex; align-items:center; gap:10px; padding: 4px 4px 14px 4px;}
.brand-logo {width:38px; height:38px; border-radius:12px;
  background: linear-gradient(135deg,#2DD4BF,#7C3AED); display:flex; align-items:center;
  justify-content:center; font-size:1.15rem; box-shadow:0 6px 16px rgba(45,212,191,0.35);}
.brand-name {font-weight:700; font-size:0.98rem; color:#fff !important;}
.brand-sub {font-size:0.72rem; color:#A5B4FC !important;}
.side-label {font-size:0.68rem; letter-spacing:.09em; text-transform:uppercase;
  color:#818CF8 !important; margin: 14px 4px 4px 4px;}
.status-card {margin-top: 16px; background: rgba(255,255,255,0.07);
  border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 12px;}
.status-card .t {font-size:0.8rem; font-weight:600; color:#fff !important;}
.status-card .s {font-size:0.72rem; color:#A5B4FC !important; margin-top:4px; line-height:1.4;}

/* Top bar and hero */
.topbar {display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;
  gap:8px; background:rgba(255,255,255,0.85); border:1px solid #E2E8F0; border-radius:16px;
  padding:10px 16px; box-shadow:0 4px 14px rgba(15,23,42,0.05);}
.topbar .name {font-weight:700; color:#14243A; font-size:0.95rem;}
.topbar .sub {font-size:0.74rem; color:#64748B;}
.pill {padding:4px 12px; border-radius:999px; font-size:0.72rem; font-weight:600;}
.pill-on {background:#CCFBF1; color:#0F766E;}
.pill-off {background:#FEF3C7; color:#92400E;}
.hero {text-align:center; margin: 28px 0 20px 0;}
.hero h1 {font-size: 2.1rem; font-weight: 800; color:#14243A; margin:0; letter-spacing:-0.02em;}
.hero h1 span {background: linear-gradient(90deg,#0D9488,#7C3AED,#DB2777);
  -webkit-background-clip:text; background-clip:text; color:transparent;}
.hero p {color:#475569; font-size:0.98rem; margin:10px 0 0 0;}

/* Option cards */
.opt-card {border-radius:18px; padding:18px; min-height:140px; border:1px solid rgba(255,255,255,0.9);
  box-shadow:0 6px 18px rgba(15,23,42,0.08); transition: transform .18s ease, box-shadow .18s ease;}
.opt-card:hover {transform: translateY(-4px); box-shadow:0 14px 30px rgba(15,23,42,0.14);}
.opt-icon {width:42px; height:42px; border-radius:13px; display:flex; align-items:center;
  justify-content:center; font-size:1.2rem; color:#fff; margin-bottom:10px;}
.opt-title {font-weight:700; font-size:0.92rem; color:#14243A;}
.opt-desc {font-size:0.76rem; color:#475569; line-height:1.45; margin-top:4px;}
.main .stButton > button {border-radius:12px; font-size:0.8rem; font-weight:600;
  padding:0.4rem 0.6rem; min-height:36px; border:1px solid #CBD5E1; background:#fff; color:#14243A;
  width:100%; transition: all .15s ease;}
.main .stButton > button:hover {border-color:#7C3AED; color:#7C3AED; background:#FAF5FF;}
.main .stButton > button[kind="primary"] {
  background:linear-gradient(135deg,#14B8A6,#7C3AED); color:#fff; border:none;}

/* Chat bubbles */
[data-testid="stChatMessage"] {background:#fff; border:1px solid #E2E8F0; border-radius:16px;
  padding:12px 16px; margin-bottom:10px; box-shadow:0 2px 6px rgba(15,23,42,0.05);}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
  background:linear-gradient(135deg,#F0FDFA,#EDE9FE); border-color:#C4B5FD;}
[data-testid="stChatMessage"] p {font-size:0.9rem; line-height:1.6; color:#1E293B;}

/* Bottom chat bar (the Speak button is added next to the arrow by the script) */
[data-testid="stChatInput"] {border-radius:999px !important; border:2px solid #C4B5FD !important;
  box-shadow:0 10px 28px rgba(124,58,237,0.15); background:#fff !important;}
[data-testid="stChatInput"] textarea {font-size:0.92rem !important;}

/* Enquiry panel */
[data-testid="stExpander"] {background:#fff; border-radius:16px !important; border:1px solid #E2E8F0 !important;}
[data-testid="stExpander"] summary p {font-size:0.92rem; font-weight:600; color:#14243A;}
.stTextInput label p, .stTextArea label p, .stRadio label p, .stCheckbox label p {
  font-size:0.8rem !important; color:#334155 !important;}
.stTextInput input, .stTextArea textarea {font-size:0.86rem !important;}

.disclaimer {color:#64748B; font-size:0.72rem; text-align:center; margin-top:18px;}

@media (max-width: 760px) {
  .block-container {padding: 3.2rem 0.6rem 6rem 0.6rem !important;}
  .hero h1 {font-size:1.5rem;}
  .opt-card {min-height:auto;}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Adds a labeled "🎙 Speak" button inside the chat bar, next to the send arrow.
# Uses the browser's real-time speech recognition (Chrome or Edge).
MIC_JS = """
<script>
(function () {
  const win = window.parent;
  const doc = win.document;

  if (!win.__micInstalled) {
    win.__micInstalled = true;
    const SR = win.SpeechRecognition || win.webkitSpeechRecognition;
    let rec = null, listening = false, btn = null;

    // Pulse animation for the listening state
    const style = doc.createElement("style");
    style.textContent = `
      @keyframes micPulse {
        0% { box-shadow: 0 0 0 0 rgba(220,38,38,0.45); }
        70% { box-shadow: 0 0 0 10px rgba(220,38,38,0); }
        100% { box-shadow: 0 0 0 0 rgba(220,38,38,0); }
      }`;
    doc.head.appendChild(style);

    function setValue(el, value) {
      const setter = Object.getOwnPropertyDescriptor(win.HTMLTextAreaElement.prototype, "value").set;
      setter.call(el, value);
      el.dispatchEvent(new win.Event("input", { bubbles: true }));
    }

    function sendButton() {
      const box = doc.querySelector('[data-testid="stChatInput"]');
      if (!box) return null;
      const buttons = box.querySelectorAll("button");
      return buttons.length ? buttons[buttons.length - 1] : null;
    }

    function setLook(on) {
      if (!btn) return;
      btn.textContent = on ? "⏹ Listening..." : "🎙 Speak";
      btn.style.background = on ? "#FEE2E2" : "#F5F3FF";
      btn.style.borderColor = on ? "#FCA5A5" : "#C4B5FD";
      btn.style.color = on ? "#B91C1C" : "#6D28D9";
      btn.style.animation = on ? "micPulse 1.4s infinite" : "none";
    }

    function toggle() {
      if (!SR) {
        win.alert("Live speech needs Google Chrome or Microsoft Edge.");
        return;
      }
      if (listening) {
        if (rec) rec.stop();
        return;
      }
      const ta = doc.querySelector('[data-testid="stChatInput"] textarea');
      if (!ta) return;
      rec = new SR();
      rec.lang = "en-IN";
      rec.interimResults = true;
      rec.continuous = false;
      let finalText = "";
      rec.onstart = () => { listening = true; setLook(true); };
      rec.onresult = (e) => {
        let t = "";
        for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
        finalText = t.trim();
        setValue(ta, finalText);
      };
      rec.onerror = () => { listening = false; setLook(false); };
      rec.onend = () => {
        listening = false;
        setLook(false);
        if (finalText) {
          setTimeout(() => {
            const send = sendButton();
            if (send && !send.disabled) send.click();
          }, 400);
        }
      };
      rec.start();
    }

    function inject() {
      const box = doc.querySelector('[data-testid="stChatInput"]');
      if (!box || doc.getElementById("mic-btn-custom")) return;
      const send = sendButton();
      if (!send) return;
      btn = doc.createElement("button");
      btn.id = "mic-btn-custom";
      btn.type = "button";
      btn.title = "Click, ask your question, then wait. It is sent automatically.";
      btn.textContent = "🎙 Speak";
      btn.style.cssText =
        "border:1px solid #C4B5FD;background:#F5F3FF;color:#6D28D9;" +
        "font-size:0.85rem;font-weight:600;font-family:'Segoe UI',system-ui,sans-serif;" +
        "padding:0 12px;height:36px;border-radius:999px;cursor:pointer;" +
        "white-space:nowrap;margin-right:8px;display:inline-flex;align-items:center;";
      btn.onclick = toggle;
      send.parentElement.insertBefore(btn, send);
    }

    const observer = new win.MutationObserver(inject);
    observer.observe(doc.body, { childList: true, subtree: true });
    win.__micInject = inject;
  }
  if (win.__micInject) win.__micInject();
})();
</script>
"""

faq = load_faq()
company = faq.get("company_name", "Our Company")


# ---------------- Helpers ----------------
@st.cache_data(ttl=20)
def ai_online():
    """True only if the local Ollama service actually responds."""
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def speech_js(text):
    """Runs in the browser: reads text aloud with a natural voice, or stops speech."""
    payload = json.dumps(text).replace("</", "<\\/")
    return f"""
    <script>
      const synth = window.speechSynthesis;
      const text = {payload};
      synth.cancel();
      if (text !== "{STOP_SPEECH}") {{
        function speakNow() {{
          const voices = synth.getVoices();
          const prefs = [/Natural/i, /Aria|Jenny|Zira|Samantha|Google US English|Google UK English Female/i];
          let voice = null;
          for (const p of prefs) {{
            voice = voices.find(v => /^en/i.test(v.lang) && p.test(v.name));
            if (voice) break;
          }}
          if (!voice) voice = voices.find(v => /^en/i.test(v.lang)) || null;
          const u = new SpeechSynthesisUtterance(text);
          if (voice) {{
            u.voice = voice;
            u.lang = voice.lang;
          }} else {{
            u.lang = "en-US";
          }}
          u.rate = 1.05;
          u.pitch = 1.0;
          u.volume = 1.0;
          synth.speak(u);
        }}
        if (synth.getVoices().length) {{
          speakNow();
        }} else {{
          synth.onvoiceschanged = speakNow;
        }}
      }}
    </script>
    """


def save_lead(data):
    """Save an enquiry to leads.csv. Raises an error if saving fails."""
    new_file = not os.path.exists(LEADS_FILE)
    row = {f: "" for f in LEAD_FIELDS}
    row["timestamp"] = dt.datetime.now().isoformat(timespec="seconds")
    row.update(data)
    with open(LEADS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def fresh_chat():
    return {"title": "New chat", "messages": [], "history": []}


# ---------------- Session state ----------------
if "current" not in st.session_state:
    st.session_state.current = fresh_chat()
    st.session_state.archive = []
    st.session_state.show_form = False
    st.session_state.pending = None
    st.session_state.speak_text = None
    st.session_state.read_aloud = False


# ---------------- Callbacks ----------------
def send_suggestion(text):
    st.session_state.pending = text


def open_form():
    st.session_state.show_form = True


def close_form():
    st.session_state.show_form = False


def start_new_chat():
    cur = st.session_state.current
    if cur["messages"]:
        st.session_state.archive.insert(0, cur)
    st.session_state.current = fresh_chat()
    st.session_state.show_form = False
    st.session_state.pending = None
    st.session_state.speak_text = STOP_SPEECH


def open_past_chat(idx):
    chat = st.session_state.archive.pop(idx)
    cur = st.session_state.current
    if cur["messages"]:
        st.session_state.archive.insert(idx, cur)
    st.session_state.current = chat


def listen_to(text):
    st.session_state.speak_text = text


def stop_speaking():
    st.session_state.speak_text = STOP_SPEECH


def process_message(text):
    """Handles one customer message: contact, greeting, FAQ, then AI if needed. Logs it."""
    text = text.strip()
    if not text:
        return
    cur = st.session_state.current
    if not cur["messages"]:
        cur["title"] = text[:32] + ("..." if len(text) > 32 else "")
    cur["messages"].append({"role": "user", "content": text})

    simple = text.lower().strip(" !.?")
    if any(w in text.lower() for w in CONTACT_WORDS):
        st.session_state.show_form = True
        reply = ("I can arrange a follow-up with our team. Please complete the short "
                 "enquiry form below. It is only sent when you press Send.")
    elif simple in GREETINGS:
        reply = f"Hello! Welcome to {company}. How can I help you today?"
    else:
        match = find_faq_match(text, faq)
        if match:
            reply = match["answer"]
        else:
            with st.spinner("Thinking..."):
                reply = answer(text, faq, cur["history"])

    cur["messages"].append({"role": "assistant", "content": reply})
    cur["history"] += [{"role": "user", "content": text},
                       {"role": "assistant", "content": reply}]
    log_row(customer_said=text, agent_said=reply)

    if st.session_state.read_aloud:
        st.session_state.speak_text = reply


# ================= SIDEBAR =================
with st.sidebar:
    st.markdown(f"""
    <div class="brand">
      <div class="brand-logo">✨</div>
      <div><div class="brand-name">{company}</div><div class="brand-sub">AI Assistant</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.button("＋  New chat", key="new_chat", on_click=start_new_chat, type="primary")

    st.markdown('<div class="side-label">Voice</div>', unsafe_allow_html=True)
    st.toggle("Read replies aloud", key="read_aloud")
    st.button("⏹  Stop voice", key="stop_voice", on_click=stop_speaking)

    st.markdown('<div class="side-label">Navigate</div>', unsafe_allow_html=True)
    st.button("💬  Chat", key="nav_chat", on_click=close_form)
    st.button("🧭  Explore services", key="nav_services",
              on_click=send_suggestion, args=(OPTIONS[0][5],))
    st.button("💲  Pricing", key="nav_pricing",
              on_click=send_suggestion, args=(OPTIONS[1][5],))
    st.button("📝  Send an enquiry", key="nav_enquiry", on_click=open_form)

    st.markdown('<div class="side-label">Recent chats</div>', unsafe_allow_html=True)
    if not st.session_state.archive:
        st.caption("Your earlier chats will appear here.")
    for i, chat in enumerate(st.session_state.archive[:10]):
        st.button(f"🗨  {chat['title']}", key=f"past_{i}",
                  on_click=open_past_chat, args=(i,))

    online = ai_online()
    st.markdown(f"""
    <div class="status-card">
      <div class="t">{'● Online' if online else '● Approved answers only'}</div>
      <div class="s">{'Connected to the local AI model. Answers still come only from approved company details.' if online else 'AI model offline. Showing approved answers only.'}</div>
    </div>
    """, unsafe_allow_html=True)


# ================= MAIN =================
online = ai_online()
status_html = ('<span class="pill pill-on">● AI assistant online</span>' if online
               else '<span class="pill pill-off">Approved answers only</span>')
st.markdown(f"""
<div class="topbar">
  <div><div class="name">{company}</div><div class="sub">Customer assistant</div></div>
  {status_html}
</div>
<div class="hero">
  <h1>Hello, how can we <span>help you today?</span></h1>
  <p>Ask by typing or speaking. Get instant answers from our approved information,
  or request a follow-up from our team.</p>
</div>
""", unsafe_allow_html=True)

# Option cards
cols = st.columns(4)
for i, (icon, title, desc, bg, accent, question) in enumerate(OPTIONS):
    with cols[i]:
        st.markdown(f"""
        <div class="opt-card" style="background:{bg};">
          <div class="opt-icon" style="background:{accent};">{icon}</div>
          <div class="opt-title">{title}</div>
          <div class="opt-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        if question is None:
            st.button("Send enquiry →", key=f"opt_{i}", on_click=open_form)
        else:
            st.button("Ask →", key=f"opt_{i}", on_click=send_suggestion, args=(question,))

# Add the Speak button to the chat bar (runs in the browser)
components.html(MIC_JS, height=0)

# Bottom chat bar: typed text, Speak button (added above) and the send arrow
typed = st.chat_input("Ask anything about our services, pricing or next steps...")

new_question = None
if st.session_state.pending:
    new_question, st.session_state.pending = st.session_state.pending, None
elif typed:
    new_question = typed

if new_question:
    process_message(new_question)

# Conversation
cur = st.session_state.current
if not cur["messages"]:
    st.caption("Tip: pick an option above, tap 🎙 Speak in the bar, or type your question.")
for idx, m in enumerate(cur["messages"]):
    avatar = "🧑‍💼" if m["role"] == "user" else "✨"
    with st.chat_message(m["role"], avatar=avatar):
        st.write(m["content"])
        if m["role"] == "assistant":
            st.button("🔊 Listen", key=f"listen_{idx}", on_click=listen_to, args=(m["content"],))

# Speak the reply in the browser
if st.session_state.speak_text:
    components.html(speech_js(st.session_state.speak_text), height=0)
    st.session_state.speak_text = None

# Enquiry form
with st.expander("📝  Send an enquiry to our team", expanded=st.session_state.show_form):
    with st.form("enquiry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full name *")
            email = st.text_input("Business email *")
        with c2:
            company_name = st.text_input("Company")
            phone = st.text_input("Phone (optional)")
        requirement = st.text_area("What do you need? *",
                                   placeholder="Briefly describe your requirement")
        preferred = st.radio("Preferred contact method", ["Email", "Phone"], horizontal=True)
        consent = st.checkbox("I agree that the team may contact me about this enquiry.")
        submitted = st.form_submit_button("Send enquiry", type="primary")

    if submitted:
        if not name.strip() or not email.strip() or not requirement.strip():
            st.warning("Please fill in your name, email and requirement.")
        elif "@" not in email or "." not in email.split("@")[-1]:
            st.warning("Please enter a valid business email address.")
        elif not consent:
            st.warning("Please tick the consent box so we can contact you.")
        else:
            try:
                save_lead({
                    "name": name.strip(),
                    "email": email.strip(),
                    "phone": phone.strip(),
                    "company": company_name.strip(),
                    "requirement": requirement.strip(),
                    "preferred_contact": preferred,
                })
                st.session_state.show_form = False
                st.toast("Enquiry saved. Our team will follow up.", icon="✅")
                st.success("Thank you. Your enquiry has been saved.")
            except Exception:
                st.error("We could not save your enquiry right now. "
                         "Please try again or contact us directly.")

st.markdown(
    '<p class="disclaimer">Answers come only from approved company details. '
    'Live telephone calling is not part of this version.</p>',
    unsafe_allow_html=True,
)