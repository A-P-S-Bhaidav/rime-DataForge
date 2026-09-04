"""
DataForge Backend — FastAPI WebSocket Server
Voice-native real-time data analysis with Rime TTS
"""

import os
import json
import asyncio
import logging
import time
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import pandas as pd
import io
from collections import deque

from conversation import ConversationState
from data_engine import DataEngine
from rime_tts import RimeTTS
from llm_service import LLMService

# Load .env for local development (Railway injects env vars directly)
try:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    local_env = Path(__file__).resolve().parent / ".env"
    if local_env.exists():
        load_dotenv(local_env)
except Exception:
    pass  # On Railway/Render, env vars are injected by the platform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("dataforge")

app = FastAPI(
    title="DataForge API",
    description="Voice-native real-time data analyst powered by Rime TTS",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared services (stateless)
data_engine = DataEngine()
rime_api_key = os.getenv("RIME_API_KEY", "")
gemini_api_key = os.getenv("GEMINI_API_KEY", "")

class MetricsCollector:
    def __init__(self):
        self.queries = deque(maxlen=100)
        self.total_queries = 0

    def add_metric(self, metric: dict):
        self.queries.append(metric)
        self.total_queries += 1

    def get_metrics(self):
        queries_list = list(self.queries)
        if not queries_list:
            return {
                "queries": [],
                "averages": {"avg_filler": 0, "avg_llm": 0, "avg_tts": 0, "avg_total": 0},
                "query_count": self.total_queries
            }
        
        return {
            "queries": queries_list,
            "averages": {
                "avg_filler": sum(m.get("filler_latency_ms", 0) for m in queries_list) / len(queries_list),
                "avg_llm": sum(m.get("llm_latency_ms", 0) for m in queries_list) / len(queries_list),
                "avg_tts": sum(m.get("tts_latency_ms", 0) for m in queries_list) / len(queries_list),
                "avg_total": sum(m.get("total_latency_ms", 0) for m in queries_list) / len(queries_list)
            },
            "query_count": self.total_queries
        }

metrics_collector = MetricsCollector()



@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "rime_configured": bool(rime_api_key),
        "gemini_configured": bool(gemini_api_key),
    }


@app.get("/debug-llm")
async def debug_llm():
    """Debug endpoint to test LLM directly."""
    try:
        llm = LLMService(api_key=gemini_api_key)
        datasets = data_engine.list_datasets()
        result = await llm.analyze_query("Show me total sales by region", [], datasets)
        return {"status": "ok", "result": result}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/datasets")
async def list_datasets():
    """List available datasets with metadata."""
    return {"datasets": data_engine.list_datasets()}


@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV dataset."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    # Read file content and check size (10MB limit)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        
    try:
        # Parse CSV
        df = pd.read_csv(io.BytesIO(contents))
        
        # Auto-generate dataset ID from filename (lowercase, no spaces)
        dataset_id = file.filename.rsplit('.', 1)[0].lower().replace(" ", "_")
        
        # Store in data_engine
        data_engine.add_dataset(dataset_id, df, f"Uploaded dataset: {file.filename}")
        
        return {
            "id": dataset_id,
            "name": dataset_id,
            "columns": list(df.columns),
            "row_count": len(df),
            "sample_data": df.head(5).to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")


@app.get("/api/metrics")
async def get_metrics():
    """Get query latency metrics."""
    return metrics_collector.get_metrics()



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for voice-driven data analysis.
    Each connection gets its own ConversationState, RimeTTS, and LLMService.
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    # Per-connection state
    conv_state = ConversationState()
    tts_service = RimeTTS(api_key=rime_api_key)
    llm_service = LLMService(api_key=gemini_api_key)
    active_query_tasks: dict[int, asyncio.Task] = {}

    async def send_json_safe(data: dict):
        """Send JSON to client, handling closed connections."""
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    async def handle_query(text: str, gen_id: int):
        """
        Full query pipeline:
        1. Send filler speech immediately
        2. Run LLM analysis
        3. Execute data query
        4. Stream Rime TTS audio
        5. Send chart data
        """
        cancel_event = conv_state.active_tasks.get(gen_id)
        if not cancel_event:
            return

        t_start = time.monotonic()
        logger.info(f"[gen={gen_id}] Processing query: {text[:80]}...")

        try:
            # Get conversation context and available datasets
            context_data = conv_state.get_context_for_llm()
            datasets = data_engine.list_datasets()

            # --- STEP 1: Fire filler speech ASAP (< 500ms target) ---
            filler_task = asyncio.create_task(
                tts_service.synthesize_filler(text)
            )
            # --- STEP 2: Fire LLM analysis concurrently ---
            llm_task = asyncio.create_task(
                llm_service.analyze_query(text, context_data, datasets)
            )

            # Wait for filler (should be fast for short phrases)
            filler_audio = await filler_task
            t_filler = time.monotonic()
            filler_latency_ms = (t_filler - t_start) * 1000
            logger.info(f"[gen={gen_id}] Filler latency: {filler_latency_ms:.0f}ms")

            if not cancel_event.is_set() and filler_audio:
                # Send filler transcript
                await send_json_safe({
                    "type": "transcript",
                    "text": tts_service.last_filler_text,
                    "generationId": gen_id,
                    "isFiller": True
                })
                # Send filler audio
                await send_json_safe({
                    "type": "audio",
                    "data": filler_audio,
                    "generationId": gen_id,
                    "isFinal": False
                })
                await send_json_safe({
                    "type": "status",
                    "state": "speaking",
                    "generationId": gen_id
                })

            # --- STEP 3: Wait for LLM result ---
            llm_result = await llm_task
            if cancel_event.is_set():
                logger.info(f"[gen={gen_id}] Cancelled after LLM")
                return
            
            conv_state.store_query_plan(llm_result)

            t_llm = time.monotonic()
            logger.info(f"[gen={gen_id}] LLM latency: {(t_llm - t_start) * 1000:.0f}ms")

            # --- STEP 4: Execute data query ---
            query_result = await data_engine.execute_query(llm_result, cancel_event)
            if cancel_event.is_set():
                logger.info(f"[gen={gen_id}] Cancelled after data query")
                return

            # --- STEP 5: Send chart data ---
            if "data" in query_result and query_result["data"]:
                chart_config = llm_result.get("chart_config") or {}
                chart_payload = {
                    "type": "chart",
                    "chartType": llm_result.get("chart_type", "bar"),
                    "responseType": llm_result.get("response_type", "chart_and_insight"),
                    "insights": llm_result.get("detailed_insights", ""),
                    "tableData": query_result.get("data", []),
                    "tableColumns": query_result.get("columns", []),
                    "data": query_result["data"],
                    "title": chart_config.get("title", "Analysis Result"),
                    "xKey": chart_config.get("x", ""),
                    "yKey": chart_config.get("y", ""),
                    "generationId": gen_id
                }
                await send_json_safe(chart_payload)

            insights = llm_result.get("detailed_insights", "")
            if insights:
                await send_json_safe({
                    "type": "transcript",
                    "text": insights,
                    "generationId": gen_id,
                    "isFiller": False,
                    "isInsight": True
                })

            # --- STEP 6: Stream main spoken response via Rime TTS ---
            spoken_text = llm_result.get("spoken_response", "Here are the results.")
            if cancel_event.is_set():
                return

            await send_json_safe({
                "type": "transcript",
                "text": spoken_text,
                "generationId": gen_id,
                "isFiller": False
            })
            await send_json_safe({
                "type": "status",
                "state": "speaking",
                "generationId": gen_id
            })

            # Stream audio chunks
            chunk_count = 0
            async for chunk_b64 in tts_service.synthesize_streaming(spoken_text, gen_id):
                if cancel_event.is_set():
                    logger.info(f"[gen={gen_id}] Cancelled during TTS streaming (after {chunk_count} chunks)")
                    return
                await send_json_safe({
                    "type": "audio",
                    "data": chunk_b64,
                    "generationId": gen_id,
                    "isFinal": False
                })
                chunk_count += 1

            # Send final audio marker
            if not cancel_event.is_set():
                await send_json_safe({
                    "type": "audio",
                    "data": "",
                    "generationId": gen_id,
                    "isFinal": True
                })
                conv_state.add_response(spoken_text, gen_id, was_heard=True)
                conv_state.mark_heard(gen_id)
                await send_json_safe({
                    "type": "status",
                    "state": "idle",
                    "generationId": gen_id
                })

                t_end = time.monotonic()
                total_latency_ms = (t_end - t_start) * 1000
                llm_latency_ms = (t_llm - t_start) * 1000
                tts_latency_ms = total_latency_ms - llm_latency_ms # Approx TTS processing/streaming latency
                
                logger.info(
                    f"[gen={gen_id}] Complete. Total: {total_latency_ms:.0f}ms, "
                    f"Chunks: {chunk_count}"
                )
                
                # Record metrics
                metrics_collector.add_metric({
                    "timestamp": time.time(),
                    "query_text": text[:50],
                    "filler_latency_ms": filler_latency_ms,
                    "llm_latency_ms": llm_latency_ms,
                    "tts_latency_ms": tts_latency_ms,
                    "total_latency_ms": total_latency_ms
                })

        except asyncio.CancelledError:
            logger.info(f"[gen={gen_id}] Task cancelled")
        except Exception as e:
            logger.error(f"[gen={gen_id}] Error: {e}", exc_info=True)
            if not cancel_event.is_set():
                await send_json_safe({
                    "type": "error",
                    "message": f"Analysis failed: {str(e)}",
                    "generationId": gen_id
                })
                await send_json_safe({
                    "type": "status",
                    "state": "idle",
                    "generationId": gen_id
                })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")
                continue

            msg_type = data.get("type")

            if msg_type == "query":
                text = data.get("text", "").strip()
                if not text:
                    continue

                # Create new generation
                gen_id = conv_state.new_query(text)

                # Send processing status
                await send_json_safe({
                    "type": "status",
                    "state": "processing",
                    "generationId": gen_id
                })

                # Cancel any previous running task
                for old_id, old_task in list(active_query_tasks.items()):
                    if not old_task.done():
                        conv_state.interrupt(old_id)
                        tts_service.cancel()

                # Launch query handler
                task = asyncio.create_task(handle_query(text, gen_id))
                active_query_tasks[gen_id] = task

                # Cleanup completed tasks
                done_ids = [gid for gid, t in active_query_tasks.items() if t.done()]
                for gid in done_ids:
                    del active_query_tasks[gid]

            elif msg_type == "interrupt":
                target_gen_id = data.get("generationId")
                if target_gen_id is not None:
                    # Cancel the specified generation
                    conv_state.interrupt(target_gen_id)
                    tts_service.cancel()

                    await send_json_safe({
                        "type": "interrupted",
                        "generationId": target_gen_id
                    })
                    await send_json_safe({
                        "type": "status",
                        "state": "idle",
                        "generationId": target_gen_id
                    })
                    logger.info(f"[gen={target_gen_id}] Interrupted by client")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        # Cancel all active tasks
        for task in active_query_tasks.values():
            if not task.done():
                task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting DataForge on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
