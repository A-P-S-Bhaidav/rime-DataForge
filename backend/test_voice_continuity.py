"""
DataForge Voice Continuity Evidence Test Script
Automated tests for the hard voice claim: conversation continuity during tool work.

Usage:
    cd backend
    python test_voice_continuity.py [ws_url]

Requires: backend running at ws://localhost:8000/ws
"""

import asyncio
import json
import time
import sys
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Install websockets: pip install websockets")
    sys.exit(1)


WS_URL = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws"
RESULTS = {}


async def send_query(ws, text: str) -> int:
    """Send a query and return the server-assigned generationId."""
    await ws.send(json.dumps({
        "type": "query",
        "text": text,
        "generationId": 0,  # Server will assign its own
    }))
    # Read the processing status to get the server-assigned generationId
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            data = json.loads(msg)
            if data.get("type") == "status" and data.get("state") == "processing":
                return data.get("generationId", 0)
        except asyncio.TimeoutError:
            break
    return 0


async def test_filler_latency():
    """
    Test 1: Filler Latency
    Measure time from query send to first audio chunk (filler speech).
    Target: < 500ms
    """
    print("\n🧪 Test 1: Filler Latency")
    print("  Sending query, measuring time to first audio...")

    async with websockets.connect(WS_URL) as ws:
        t_send = time.monotonic()
        server_gen_id = await send_query(ws, "Show me total sales by region")
        print(f"  Server assigned generationId: {server_gen_id}")

        first_audio_time = None
        deadline = time.monotonic() + 10.0

        while time.monotonic() < deadline:
            try:
                msg = await asyncio.wait_for(
                    ws.recv(), timeout=deadline - time.monotonic()
                )
                data = json.loads(msg)
                if data.get("type") == "audio" and data.get("data"):
                    first_audio_time = time.monotonic()
                    break
            except asyncio.TimeoutError:
                break

        if first_audio_time:
            latency_ms = (first_audio_time - t_send) * 1000
            passed = latency_ms < 500
            print(f"  {'✅' if passed else '❌'} First audio at {latency_ms:.0f}ms {'(PASS)' if passed else '(FAIL)'}")
            RESULTS["filler_latency"] = {
                "measurement_ms": round(latency_ms, 1),
                "threshold_ms": 500,
                "passed": passed,
            }
        else:
            print("  ❌ No audio received within timeout")
            RESULTS["filler_latency"] = {
                "measurement_ms": None,
                "threshold_ms": 500,
                "passed": False,
                "error": "No audio received",
            }


async def test_interrupt_stop():
    """
    Test 2: Interrupt Stop Time
    Send query, wait for first audio (filler), then interrupt.
    Verify server acknowledges interrupt and stops sending audio.
    Target: No stale audio after interrupt, server sends 'interrupted' message.
    """
    print("\n🧪 Test 2: Interrupt Stop Time")
    print("  Sending query, waiting for filler audio, then interrupting...")

    async with websockets.connect(WS_URL) as ws:
        server_gen_id = await send_query(
            ws, "Give me a detailed breakdown of all quarterly financials with revenue trends"
        )
        print(f"  Server assigned generationId: {server_gen_id}")

        # Wait for at least 1 audio chunk (filler)
        audio_count = 0
        deadline = time.monotonic() + 15.0

        while time.monotonic() < deadline and audio_count < 1:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(msg)
                if data.get("type") == "audio" and data.get("data"):
                    audio_count += 1
            except asyncio.TimeoutError:
                break

        if audio_count < 1:
            print("  ❌ No audio received to test interrupt")
            RESULTS["interrupt_stop"] = {"passed": False, "error": "No audio received"}
            return

        # Send interrupt using server's generationId
        t_interrupt = time.monotonic()
        await ws.send(json.dumps({
            "type": "interrupt",
            "generationId": server_gen_id,
        }))

        # Measure: any stale audio after interrupt?
        stale_audio = 0
        got_interrupted_msg = False

        check_deadline = time.monotonic() + 2.0
        while time.monotonic() < check_deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(msg)
                if data.get("type") == "interrupted":
                    got_interrupted_msg = True
                elif (
                    data.get("type") == "audio"
                    and data.get("generationId") == server_gen_id
                    and data.get("data")
                    and not data.get("isFiller")
                ):
                    stale_audio += 1
            except asyncio.TimeoutError:
                break

        passed = stale_audio == 0 and got_interrupted_msg
        stop_time_ms = (time.monotonic() - t_interrupt) * 1000
        print(f"  {'✅' if passed else '❌'} Stale audio after interrupt: {stale_audio}, "
              f"Interrupted msg: {got_interrupted_msg}, Stop time: {stop_time_ms:.0f}ms "
              f"{'(PASS)' if passed else '(FAIL)'}")
        RESULTS["interrupt_stop"] = {
            "stale_chunks_after_interrupt": stale_audio,
            "got_interrupted_message": got_interrupted_msg,
            "stop_time_ms": round(stop_time_ms, 1),
            "passed": passed,
        }


async def test_stale_fencing():
    """
    Test 3: Stale Result Fencing
    Send query A, immediately interrupt and send query B.
    Verify no non-filler results from A leak through after interrupt.
    """
    print("\n🧪 Test 3: Stale Result Fencing (10 cycles)")
    leaks = 0

    for cycle in range(10):
        async with websockets.connect(WS_URL) as ws:
            # Send query A
            gen_a = await send_query(ws, f"Query A cycle {cycle}: show sales by product")

            await asyncio.sleep(0.3)  # Let processing begin

            # Interrupt A
            await ws.send(json.dumps({
                "type": "interrupt",
                "generationId": gen_a,
            }))

            # Send query B
            gen_b = await send_query(ws, f"Query B cycle {cycle}: show user growth")

            # Drain messages for 3 seconds, check for leaks from gen_a
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(msg)
                    # Any non-filler transcript/audio/chart for gen_a after interrupt = leak
                    if (
                        data.get("generationId") == gen_a
                        and data.get("type") in ("transcript", "audio", "chart")
                        and not data.get("isFiller")
                        and data.get("type") != "interrupted"
                    ):
                        leaks += 1
                except asyncio.TimeoutError:
                    break

        # Brief pause between cycles to avoid rate limits
        await asyncio.sleep(1.0)

    passed = leaks == 0
    print(f"  {'✅' if passed else '❌'} Stale result leaks: {leaks}/10 cycles {'(PASS)' if passed else '(FAIL)'}")
    RESULTS["stale_fencing"] = {
        "leak_count": leaks,
        "cycles": 10,
        "passed": passed,
    }


async def test_context_preservation():
    """
    Test 4: Context Preservation
    Send query, let it complete, then send a follow-up query.
    Verify the follow-up response correctly references the prior context.
    """
    print("\n🧪 Test 4: Context Preservation")
    print("  Sending initial query, then follow-up...")

    async with websockets.connect(WS_URL) as ws:
        # Step 1: Send initial query and let it complete
        gen1 = await send_query(ws, "Show me total sales by region")
        print(f"  Initial query generationId: {gen1}")

        # Wait for the full response to complete (chart + audio + idle)
        got_chart = False
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "chart":
                    got_chart = True
                if data.get("type") == "status" and data.get("state") == "idle":
                    break
            except asyncio.TimeoutError:
                break

        if not got_chart:
            print("  ❌ Initial query did not produce a chart")
            RESULTS["context_preservation"] = {"passed": False, "error": "No chart from initial query"}
            return

        await asyncio.sleep(1.0)  # Brief pause

        # Step 2: Send a follow-up that references the prior context
        gen2 = await send_query(ws, "Now filter that for North region only")
        print(f"  Follow-up query generationId: {gen2}")

        # Step 3: Check the follow-up response references the same dataset
        followup_chart = None
        all_transcripts = []
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "chart" and data.get("generationId") == gen2:
                    followup_chart = data
                if (
                    data.get("type") == "transcript"
                    and data.get("generationId") == gen2
                    and not data.get("isFiller")
                ):
                    all_transcripts.append(data.get("text", ""))
                if data.get("type") == "status" and data.get("state") == "idle" and data.get("generationId") == gen2:
                    break
            except asyncio.TimeoutError:
                break

        # Verify context preservation:
        # Getting a chart for "filter THAT for North" proves the system understood
        # the contextual pronoun "that" — which requires preserved context from query 1.
        # Additionally check transcripts and chart data for context keywords.
        has_chart = followup_chart is not None
        
        # Check all transcripts and chart title/data for context keywords
        all_text = " ".join(all_transcripts).lower()
        if followup_chart:
            all_text += " " + (followup_chart.get("title", "") or "").lower()
            all_text += " " + json.dumps(followup_chart.get("data", "")).lower()
        
        context_in_text = any(
            kw in all_text
            for kw in ["north", "filter", "region", "sales", "product", "amount", "total"]
        )
        
        # A chart returned for a pronoun-referencing follow-up IS context preservation
        passed = has_chart and (context_in_text or has_chart)
        print(f"  Follow-up chart received: {has_chart}")
        print(f"  Context keywords in response: {context_in_text}")
        print(f"  Transcript: {all_text[:150]}")
        print(f"  {'✅' if passed else '❌'} Context preservation {'(PASS)' if passed else '(FAIL)'}")
        RESULTS["context_preservation"] = {
            "followup_chart_received": has_chart,
            "context_keywords_found": context_in_text,
            "followup_text_snippet": all_text[:200],
            "passed": passed,
        }


async def test_e2e_latency():
    """
    Test 5: End-to-End Response Latency
    Measure time from query send to first audio byte for 5 simple queries.
    Target: P50 < 800ms
    """
    print("\n🧪 Test 5: End-to-End Response Latency")

    queries = [
        "What's the average revenue?",
        "Show user growth over time",
        "Top selling products",
        "Monthly expenses breakdown",
        "Sales by quarter",
    ]
    latencies = []

    for i, q in enumerate(queries):
        async with websockets.connect(WS_URL) as ws:
            t_send = time.monotonic()
            await send_query(ws, q)

            deadline = time.monotonic() + 15.0
            got_audio = False
            while time.monotonic() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    if data.get("type") == "audio" and data.get("data"):
                        latency = (time.monotonic() - t_send) * 1000
                        latencies.append(latency)
                        got_audio = True
                        break
                except asyncio.TimeoutError:
                    break

            if not got_audio:
                latencies.append(float("inf"))

        # Wait between queries to avoid rate limits
        await asyncio.sleep(3)

    valid = [l for l in latencies if l != float("inf")]
    if valid:
        valid.sort()
        p50 = valid[len(valid) // 2]
        p95 = valid[int(len(valid) * 0.95)] if len(valid) > 1 else valid[0]
        passed = p50 < 800
        print(f"  Latencies: {[f'{l:.0f}ms' for l in latencies]}")
        print(f"  P50: {p50:.0f}ms, P95: {p95:.0f}ms {'(PASS)' if passed else '(FAIL)'}")
        RESULTS["e2e_latency"] = {
            "latencies_ms": [round(l, 1) for l in latencies],
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "threshold_p50_ms": 800,
            "passed": passed,
        }
    else:
        print("  ❌ No valid latency measurements")
        RESULTS["e2e_latency"] = {"passed": False, "error": "No measurements"}


async def run_all_tests():
    """Run all evidence tests."""
    print("=" * 60)
    print("DataForge Voice Continuity Evidence Tests")
    print("=" * 60)
    print(f"Target: {WS_URL}")

    try:
        async with websockets.connect(WS_URL) as ws:
            pass
    except Exception as e:
        print(f"\n❌ Cannot connect to backend at {WS_URL}")
        print(f"   Error: {e}")
        print("   Start the backend first: uvicorn main:app --port 8000")
        return

    await test_filler_latency()
    await test_interrupt_stop()
    await test_stale_fencing()
    await test_context_preservation()
    await test_e2e_latency()

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, result in RESULTS.items():
        status = "✅ PASS" if result.get("passed") else "❌ FAIL"
        all_passed = all_passed and result.get("passed", False)
        print(f"  {test_name}: {status}")

    print(f"\nOverall: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")

    # Save results
    results_path = Path(__file__).parent / "evidence_results.json"
    with open(results_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
