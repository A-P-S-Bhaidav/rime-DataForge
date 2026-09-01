# RIME_EVIDENCE.md — DataForge Voice Continuity Evidence

## Hard Voice Claim

**Claim**: DataForge maintains conversation continuity during data analysis tool work.  
The voice session remains responsive while queries execute (2-5 seconds), supports mid-speech interruption with prompt audio cancellation, fences stale results to prevent them from being spoken as current, and preserves conversational context based on what the user actually heard.

---

## Acceptance Test Definitions

| # | Test Name | What It Proves | Acceptance Criteria |
|---|-----------|---------------|-------------------|
| 1 | **Filler Latency** | Voice stays responsive during compute | Contextual filler speech starts < 500ms after query receipt |
| 2 | **Interrupt Stop Time** | Queued TTS stops promptly on interrupt | Audio playback ceases within 300ms of interrupt signal |
| 3 | **Stale Result Fencing** | Old query results never leak into new context | Zero stale-result leaks across 10 consecutive interrupt+requery cycles |
| 4 | **Context Preservation** | Follow-ups reference what was heard, not what was generated | 100% correct context in follow-up queries after interruption |
| 5 | **End-to-End Latency** | Perceived response time is fast | First Rime audio byte arrives < 800ms after query dispatch (excl. STT) |

---

## Test Procedure

### Automated Test Script
```bash
# Prerequisites: Backend running on localhost:8000
cd backend
python test_voice_continuity.py
```

The script performs the following sequence:

### Test 1: Filler Latency
1. Connect to WebSocket at `ws://localhost:8000/ws`
2. Send `{"type": "query", "text": "show me quarterly sales breakdown by region", "generationId": 1}`
3. Start timer at send time
4. Measure time to first `{"type": "audio", ...}` message
5. **Pass**: First audio chunk arrives within 500ms

### Test 2: Interrupt Stop Time
1. Send a query that triggers a long spoken response
2. Wait for audio streaming to begin (first 2-3 audio chunks received)
3. Send `{"type": "interrupt", "generationId": 2}`
4. Start timer at interrupt send time
5. Measure time until no more audio chunks arrive for the old generationId
6. **Pass**: No audio chunks received for old generationId within 300ms of interrupt

### Test 3: Stale Result Fencing
1. Repeat 10 times:
   a. Send query A with generationId N
   b. Wait 200ms (let processing begin)
   c. Send `{"type": "interrupt", "generationId": N+1}` and immediately send query B with generationId N+1
   d. Collect all responses
   e. Verify: No `transcript` or `audio` messages arrive with generationId N after the interrupt
2. **Pass**: Zero stale-result leaks across all 10 cycles

### Test 4: Context Preservation
1. Send: "Show me total revenue for Q1"
2. Wait for response to begin speaking
3. Interrupt after hearing "The total revenue..."
4. Send: "Now compare that with Q2" (follow-up referencing interrupted context)
5. Verify the response correctly references the Q1 context that was established, not a new unrelated context
6. **Pass**: Response correctly references prior heard context

### Test 5: End-to-End Response Latency
1. Send 5 simple queries: "What's the average revenue?", "Show user growth", etc.
2. Measure time from query send to first audio byte for each
3. Compute P50 and P95 latency
4. **Pass**: P50 < 800ms, P95 < 1500ms

---

## Results

| Test | Result | Measurement | Pass/Fail |
|------|--------|-------------|-----------|
| Filler Latency | *Run test to populate* | — | — |
| Interrupt Stop Time | *Run test to populate* | — | — |
| Stale Result Fencing | *Run test to populate* | — | — |
| Context Preservation | *Run test to populate* | — | — |
| E2E Response Latency | *Run test to populate* | — | — |

> **Note**: Results table is populated by running `python test_voice_continuity.py` with a valid Rime API key and Gemini API key configured in `.env`. The script outputs structured JSON to `evidence_results.json` and a formatted table to stdout.

---

## Implementation Details

### Generation ID Fencing Mechanism
Every user query is assigned a monotonically increasing `generationId`. When the user interrupts:

1. The current `generationId` is marked as **cancelled** in the `ConversationState`
2. A new `generationId` is assigned to the incoming query
3. Any background tasks (LLM reasoning, data queries, Rime TTS synthesis) check their `generationId` against the current active ID before emitting results
4. If a task's `generationId` is stale, its results are silently discarded — never sent to the client

### Heard Context Tracking
The `ConversationState` maintains a separate `heard_context` list that only includes:
- Messages that were fully spoken and heard by the user
- Messages that were partially spoken before interruption (marked with what was heard)
- This ensures follow-up queries reference the correct conversational state

### Filler Speech Strategy
Contextual filler phrases are:
- Pre-synthesized for common patterns to reduce latency
- Selected based on query type (data lookup → "Let me check the numbers...", comparison → "Comparing those datasets now...")
- Short (< 2 seconds of audio) to minimize the gap before real results

---

## Limitations

1. **Filler latency** depends on Rime API response time; on first request after cold start, latency may exceed 500ms
2. **Interrupt precision** is limited by WebSocket round-trip time (~50-100ms network overhead)
3. **Context preservation** relies on LLM correctly interpreting truncated conversation history; edge cases with deeply nested follow-ups may produce incorrect context
4. **Browser audio latency** adds ~50-100ms to perceived interrupt stop time due to Web Audio API buffering
5. **STT accuracy** affects query quality but is outside Rime's scope (using browser Web Speech API)
6. **Cached vs uncached**: First Rime TTS call may have higher latency due to model warm-up. Subsequent calls benefit from connection reuse. All measurements are labeled accordingly.

---

## Rime Configuration Used

| Parameter | Value |
|-----------|-------|
| Model ID | `coda` |
| Speaker | `celeste` |
| Language | `en` |
| Endpoint | `https://users.rime.ai/v1/rime-tts` |
| Audio Format | `mp3` (Accept: `audio/mpeg`) |
| Transport | Streaming HTTP (chunked transfer) |
| Sample Rate | Default (model-determined) |
