# DataForge — Voice-Native Real-Time Data Analyst

> **Rime Hackathon Submission** | Team DataForge  
> Hard Voice Problem: **Conversation Continuity During Tool Work**

DataForge is a voice-first data exploration tool where users speak natural-language queries and receive **streaming spoken insights** via Rime TTS while interactive visualizations render simultaneously. The voice channel is essential — users explore data hands-free through conversation, with the assistant narrating trends, calling out anomalies, and confirming actions while their eyes stay on the charts.

---

## 🎯 Target User & Problem

**Who**: Data analysts, operations managers, and business users who need to explore data quickly — in meetings, on the go, or during hands-busy fieldwork.

**Problem**: Traditional data tools require typing SQL/queries and reading text results. This creates friction and context-switching that slows exploration.

**Solution**: DataForge replaces typing with speech and reading with listening. Users speak queries like *"Show me sales by region for Q3"* and hear spoken insights while charts animate on screen.

**Why Voice is Essential**: Removing speech leaves the product materially worse. The spoken channel provides:
- Hands-free operation during meetings or fieldwork
- Spoken summaries that surface insights faster than reading tables
- Contextual fillers that maintain engagement during computation
- Interruption support for rapid iterative exploration

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                FRONTEND (React + Vite + TypeScript)   │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │Voice     │ │Data          │ │Chat              │ │
│  │Control   │ │Visualization │ │Transcript        │ │
│  │(Web      │ │(Recharts)    │ │Panel             │ │
│  │Speech API│ │              │ │                  │ │
│  └────┬─────┘ └──────┬───────┘ └────────┬─────────┘ │
│       └──────────────┴─────────┬────────┘           │
│                         WebSocket                    │
└───────────────────────────┼──────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────┐
│              BACKEND (Python FastAPI)                  │
│  ┌──────────┐  ┌───────────┐  ┌────────────────────┐ │
│  │WebSocket │  │Convo State│  │Data Engine         │ │
│  │Manager   │──│+ Fencing  │──│(Pandas)            │ │
│  └────┬─────┘  └─────┬─────┘  └────────────────────┘ │
│       │              │                                │
│  ┌────┴─────┐  ┌─────┴──────┐  ┌──────────────────┐  │
│  │Interrupt │  │LLM Service │  │Rime TTS          │  │
│  │Handler   │  │(Gemini)    │  │(Streaming HTTP)  │  │
│  └──────────┘  └────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────┘
```

---

## 🛠️ Setup Instructions

### Prerequisites
- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **Rime API Key** — [Get from app.rime.ai](https://app.rime.ai)
- **Google Gemini API Key** — [Get from aistudio.google.com](https://aistudio.google.com)

### 1. Clone the Repository
```bash
git clone https://github.com/A-P-S-Bhaidav/rime-DataForge.git
cd rime-DataForge
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your API keys:
#   RIME_API_KEY=your_key_here
#   GEMINI_API_KEY=your_key_here
```

### 3. Start the Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```

### 5. Open the App
Navigate to `http://localhost:5173` in a browser that supports Web Speech API (Chrome recommended).

---

## 🔊 Rime TTS Configuration

| Parameter | Value |
|-----------|-------|
| **Model ID** | `coda` |
| **Speaker** | `celeste` |
| **Language** | `en` (English) |
| **Endpoint** | `https://users.rime.ai/v1/rime-tts` |
| **Audio Format** | `mp3` (`Accept: audio/mpeg`) |
| **Transport** | Streaming HTTP (chunked transfer encoding) |
| **Sample Rate** | Default (model-determined, ~24kHz) |

---

## 📦 Third-Party Services

| Service | Purpose | Required |
|---------|---------|----------|
| **Rime AI** | Text-to-Speech synthesis (primary spoken output) | ✅ Yes |
| **Google Gemini** | LLM for natural language → data analysis translation | ✅ Yes |
| **Web Speech API** | Browser-native speech recognition (no API key needed) | Built-in |

---

## 🎤 Hard Voice Problem: Conversation Continuity During Tool Work

See [RIME_EVIDENCE.md](./RIME_EVIDENCE.md) for complete acceptance tests, procedures, and results.

**Key mechanisms:**
1. **Filler Speech** — Contextual audio fillers play within 500ms while data queries execute
2. **Generation ID Fencing** — Each query gets a monotonic ID; stale results are silently discarded
3. **Interrupt Recovery** — Audio stops within 300ms; context updates to what was actually heard
4. **Heard Context Tracking** — Follow-up queries reference the correct conversational state

---

## ⚠️ Known Limitations

1. **Speech Recognition** — Uses browser Web Speech API; accuracy varies by browser and accent. Chrome provides the best experience.
2. **Cold Start** — First Rime TTS call may have higher latency (~1-2s) due to API warm-up. Subsequent calls are significantly faster.
3. **Dataset Scope** — Ships with 3 synthetic sample datasets. Real database integration is not included in this prototype.
4. **Browser Support** — Web Speech API requires Chrome or Edge. Firefox and Safari have limited support.
5. **Network Dependency** — Requires internet for Rime TTS and Gemini API calls.

---

## 🚨 Failure Behavior

| Scenario | Behavior |
|----------|----------|
| **Rime API unavailable** | Falls back to text-only response displayed in chat panel; error logged |
| **Gemini API unavailable** | Returns error message explaining the issue; suggests retrying |
| **WebSocket disconnected** | Frontend shows reconnecting indicator; auto-reconnects with backoff |
| **Speech recognition fails** | Text input fallback available in voice control bar |
| **Unsupported browser** | Displays message suggesting Chrome; text input available as fallback |

---

## 🚀 Deployment

### Frontend (Vercel)
```bash
cd frontend
npm run build
# Deploy the dist/ folder to Vercel
npx vercel --prod
```

Set environment variable in Vercel dashboard:
- `VITE_WS_URL` = `wss://your-backend-url.railway.app/ws`
- `VITE_API_URL` = `https://your-backend-url.railway.app`

### Backend (Railway / Render)
1. Push to GitHub
2. Connect repository to Railway/Render
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables: `RIME_API_KEY`, `GEMINI_API_KEY`

---

## 📂 Project Structure

```
rime-DataForge/
├── .env.example          # Environment template (placeholders only)
├── .gitignore
├── README.md             # This file
├── RIME_EVIDENCE.md      # Hard voice claim evidence
├── backend/
│   ├── requirements.txt  # Python dependencies
│   ├── main.py           # FastAPI application + WebSocket server
│   ├── rime_tts.py       # Rime TTS streaming client
│   ├── conversation.py   # Conversation state + generation fencing
│   ├── data_engine.py    # Pandas-based data analysis engine
│   ├── llm_service.py    # Google Gemini LLM integration
│   └── test_voice_continuity.py  # Automated evidence script
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
        ├── App.tsx               # Main application shell
        ├── types.ts              # TypeScript type definitions
        ├── styles/
        │   └── index.css         # Design system + global styles
        ├── components/
        │   ├── Header.tsx        # Top bar with status + Rime badge
        │   ├── VoiceControl.tsx  # Voice input/output controls
        │   ├── DataVisualization.tsx  # Dynamic charts (Recharts)
        │   ├── ChatTranscript.tsx    # Conversation history
        │   └── DatasetPanel.tsx      # Dataset info sidebar
        └── hooks/
            ├── useWebSocket.ts       # WebSocket communication
            ├── useAudioPlayer.ts     # Streaming MP3 playback
            └── useSpeechRecognition.ts  # Web Speech API
```

---

## 📄 License

MIT License. Built for the Rime Hackathon.
