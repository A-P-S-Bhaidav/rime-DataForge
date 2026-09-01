"""
DataForge Voice Continuity Evidence Test Script
Automated tests for the hard voice claim: conversation continuity during tool work.

Usage:
    cd backend
    python test_voice_continuity.py

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


WS_URL = "ws://localhost:8000/ws"
RESULTS = {}


async def test_filler_latency():
    """
    Test 1: Filler Latency
    Measure time from query send to first audio chunk.
    Target: < 500ms
    """
    print("\n🧪 Test 1: Filler Latency")
    print("  Sending query, measuring time to first audio...")

    async with websockets.connect(WS_URL) as ws:
        query = {
            "type": "query",
            "text": "Show me total sales by region",
            "generationId": 1,
        }

        t_send = time.monotonic()
        await ws.send(json.dumps(query))

        first_audio_time = None
        timeout = 10.0
        deadline = time.monotonic() + timeout

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
            print(f"  ✅ First audio at {latency_ms:.0f}ms {'(PASS)' if passed else '(FAIL)'}")
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
    Send query, wait for audio, interrupt, measure stop time.
    Target: No audio after 300ms of interrupt.
    """
    print("\n🧪 Test 2: Interrupt Stop Time")
    print("  Sending query, waiting for audio, then interrupting...")

    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({
            "type": "query",
            "text": "Give me a detailed breakdown of all quarterly financials with revenue trends",
            "generationId": 1,
        }))

        # Wait for at least 2 audio chunks
        audio_count = 0
        timeout = 15.0
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline and audio_count < 2:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(msg)
                if data.get("type") == "audio" and data.get("data"):
                    audio_count += 1
            except asyncio.TimeoutError:
                break

        if audio_count < 1:
            print("  ❌ Insufficient audio received to test interrupt")
            RESULTS["interrupt_stop"] = {"passed": False, "error": "No audio to interrupt"}
            return

        # Send interrupt
        t_interrupt = time.monotonic()
        await ws.send(json.dumps({
            "type": "interrupt",
            "generationId": 1,
        }))

        # Measure: any audio for gen=1 after interrupt?
        stale_audio = 0
        got_interrupted_msg = False

        check_deadline = time.monotonic() + 1.0  # Check for 1 second
        while time.monotonic() < check_deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.3)
                data = json.loads(msg)
                if data.get("type") == "interrupted":
                    got_interrupted_msg = True
                if (
                    data.get("type") == "audio"
                    and data.get("generationId") == 1
                    and data.get("data")
                ):
                    stale_audio += 1
            except asyncio.TimeoutError:
                break

        stop_time_ms = (time.monotonic() - t_interrupt) * 1000
        passed = stale_audio == 0 and got_interrupted_msg
        print(f"  {'✅' if passed else '❌'} Stale audio after interrupt: {stale_audio}, "
              f"Interrupted msg: {got_interrupted_msg} {'(PASS)' if passed else '(FAIL)'}")
        RESULTS["interrupt_stop"] = {
            "stale_chunks_after_interrupt": stale_audio,
            "got_interrupted_message": got_interrupted_msg,
            "passed": passed,
        }


async def test_stale_fencing():
    """
    Test 3: Stale Result Fencing
    Send query A, immediately interrupt and send query B.
    Verify no results from A leak through.
    """
    print("\n🧪 Test 3: Stale Result Fencing (10 cycles)")
    leaks = 0

    async with websockets.connect(WS_URL) as ws:
        for cycle in range(10):
            gen_a = cycle * 2 + 1
            gen_b = cycle * 2 + 2

            # Send query A
            await ws.send(json.dumps({
                "type": "query",
                "text": f"Query A cycle {cycle}: show sales by product",
                "generationId": gen_a,
            }))

            await asyncio.sleep(0.2)

            # Interrupt A and send query B
            await ws.send(json.dumps({
                "type": "interrupt",
                "generationId": gen_a,
            }))
            await ws.send(json.dumps({
                "type": "query",
                "text": f"Query B cycle {cycle}: show user growth",
                "generationId": gen_b,
            }))

            # Drain messages for 2 seconds, check for leaks
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(msg)
                    # Any transcript or audio for gen_a after interrupt = leak
                    if (
                        data.get("generationId") == gen_a
                        and data.get("type") in ("transcript", "audio", "chart")
                        and not data.get("isFiller")
                    ):
                        # Check it's not the interrupted message
                        if data.get("type") != "interrupted":
                            leaks += 1
                except asyncio.TimeoutError:
                    break

    passed = leaks == 0
    print(f"  {'✅' if passed else '❌'} Stale result leaks: {leaks}/10 cycles {'(PASS)' if passed else '(FAIL)'}")
    RESULTS["stale_fencing"] = {
        "leak_count": leaks,
        "cycles": 10,
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

    async with websockets.connect(WS_URL) as ws:
        for i, q in enumerate(queries):
            t_send = time.monotonic()
            await ws.send(json.dumps({
                "type": "query",
                "text": q,
                "generationId": 100 + i,
            }))

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

            # Wait for completion before next query
            await asyncio.sleep(2)

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
