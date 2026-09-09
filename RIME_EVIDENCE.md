# RIME_EVIDENCE.md — DataForge Voice Continuity Evidence

## Hard Voice Claim

**Problem**: Conversation continuity during tool work.

When a voice-first data analyst executes a complex query, the LLM reasoning and data processing pipeline takes 2–5 seconds. During this time, the voice channel goes silent — dead air that makes users think the app froze. If the user interrupts mid-response to refine their question, the system must immediately stop audio, cancel stale background work, fence obsolete results from leaking into the new response, and ensure follow-up queries only reference what the user actually heard.

**Why it's hard**: This requires coordinating four asynchronous subsystems (TTS playback, LLM reasoning, data execution, WebSocket transport) around a shared cancellation primitive, while maintaining conversational state that distinguishes "generated" from "heard."

**What we built**: DataForge solves this with:
1. **Immediate filler speech** — contextual Rime TTS audio plays within 500ms while tools run
2. **Generation ID fencing** — monotonic IDs with `asyncio.Event` cancellation; stale results are silently discarded at every pipeline stage
3. **Sub-300ms interrupt** — frontend `AudioBufferSourceNode.stop()` cuts hardware audio instantly; backend cancels in-flight TTS and LLM work
4. **Heard-context tracking** — interrupted utterances are stripped from conversation history so follow-ups don't hallucinate from unheard speech

---

## Acceptance Tests

| # | Test | What It Proves | Criterion |
|---|------|---------------|-----------|
| 1 | Filler Latency | Voice stays responsive during tool work | First Rime audio < 500ms after query |
| 2 | Interrupt Stop | Queued TTS stops promptly on interrupt | Zero stale audio after interrupt signal; server sends `interrupted` acknowledgment |
| 3 | Stale Fencing | Old results never leak into new context | Zero stale-result leaks across 10 rapid interrupt+requery cycles |
| 4 | Context Preservation | Follow-ups reference what was heard | Follow-up correctly references prior query context after interruption |
| 5 | E2E Latency | Perceived response time is fast | P50 first-audio latency < 800ms across 5 queries |

---

## Procedure

### Prerequisites
```bash
# Backend running with valid API keys
cd backend
pip install -r requirements.txt
pip install websockets
uvicorn main:app --port 8000
```

### Run the test suite
```bash
cd backend
python test_voice_continuity.py
# Or against a remote deployment:
python test_voice_continuity.py wss://your-deployment.up.railway.app/ws
```

### What the script does

**Test 1 — Filler Latency**: Opens a WebSocket connection, sends a data query, and measures wall-clock time to the first `audio` message (the pre-cached filler phrase). The filler is synthesized by Rime TTS at startup and stored in an in-memory class-level cache, so subsequent requests return in <10ms.

**Test 2 — Interrupt Stop**: Sends a query, waits for the first audio chunk (filler), then sends an `interrupt` message with the server-assigned `generationId`. Verifies: (a) the server responds with `{"type": "interrupted"}`, and (b) zero non-filler audio chunks arrive for the interrupted generation after the signal.

**Test 3 — Stale Fencing**: Runs 10 rapid cycles of: send query A → wait 300ms → interrupt A → send query B. Each cycle uses a fresh WebSocket connection. After each interrupt, drains all messages and counts any non-filler transcript/audio/chart messages tagged with query A's generation ID. A single leak across all 10 cycles fails the test.

**Test 4 — Context Preservation**: Sends "Show me total sales by region", waits for the full response (chart + idle status), then sends a follow-up: "Now filter that for North region only." Verifies that the follow-up produces a chart and that the spoken/text response references the filtering context (mentions "North", "filter", "region", or "sales").

**Test 5 — E2E Latency**: Sends 5 independent queries on separate WebSocket connections (to avoid cache effects between queries) with 3-second pauses between them. Measures time from query dispatch to first audio byte. Computes P50 and P95.

---

## Results

Run `python test_voice_continuity.py` to populate. Results are saved to `evidence_results.json`.

> **Note**: Results depend on network conditions and API response times. Filler latency benefits from the pre-warmed cache (first call after startup may be slower). E2E latency includes Rime TTS network round-trip time.

---

## Limitations

1. **Cold-start filler latency**: The very first filler request after a fresh deployment (before cache pre-warming completes) may exceed 500ms due to Rime API cold start. Subsequent requests use the in-memory cache (<10ms).
2. **Interrupt precision**: Limited by WebSocket round-trip time (~50–100ms network overhead). The 300ms target accounts for this.
3. **Context preservation**: Relies on the LLM correctly interpreting truncated conversation history. Deeply nested multi-step follow-ups may occasionally lose context.
4. **Browser audio latency**: Web Audio API adds ~20–50ms to perceived interrupt stop time due to internal buffering.
5. **STT accuracy**: Speech recognition uses the browser's Web Speech API, which is outside Rime's scope. Misrecognized queries may produce unexpected results.
6. **Rate limits**: Groq's free tier has an 8,000 TPM limit. Rapid successive queries may hit this limit; the system falls back to hardcoded generic responses with an error message displayed in the UI.

---

## Rime Configuration

| Parameter | Value |
|-----------|-------|
| **Model ID** | `coda` (flagship) |
| **Speaker** | `celeste` |
| **Language** | `en` (English) |
| **Endpoint** | `https://users.rime.ai/v1/rime-tts` (default, us-west-2) |
| **Regional** | `https://users-east.rime.ai/v1/rime-tts` (if `RIME_REGION=east`) |
| **Audio Format** | MP3 (`Accept: audio/mpeg`) |
| **Transport** | HTTP POST via `httpx.AsyncClient` with connection pooling |
| **Payload Tuning** | `reduceLatency: true`, `speedAlpha: 1.1` (fillers), `speedAlpha: 1.0` (main) |
| **Text Normalization** | Currency → spoken, `%` → "percent", `Q1` → "quarter 1", markdown stripped |
| **Preflight Check** | Validates model+voice against live catalog at startup (`/data/voices/all-v2.json`) |
| **Cache Strategy** | Deterministic filler selection + class-level in-memory cache, pre-warmed at startup |

---

## Failure Behavior

| Scenario | Behavior |
|----------|----------|
| Rime API key missing | Falls back to text-only; no audio played; error logged |
| Rime API returns error | Error logged; response delivered as text-only in chat panel |
| Rime model/voice deprecated | Preflight check logs warning at startup; falls back gracefully |
| LLM (Groq) rate limited | Falls back to hardcoded generic response; error displayed in UI |
| LLM (Groq) unavailable | Falls back to Gemini; if both fail, uses hardcoded response |
| WebSocket disconnects | All active tasks cancelled; frontend shows connection status |
| User interrupts | Audio stops instantly; stale results fenced; context updated |
