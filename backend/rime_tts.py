"""
Rime TTS Client for DataForge
Handles synthesis, filler speech, and cancellation.

Rime Configuration:
  - Model: coda (flagship)
  - Speaker: celeste
  - Language: en
  - Endpoint: https://users.rime.ai/v1/rime-tts
  - Audio Format: mp3 (Accept: audio/mpeg)
  - Transport: HTTP (full response, then chunk for streaming)
"""

import httpx
import asyncio
import os
import base64
import logging
import random
from typing import AsyncGenerator, Optional

logger = logging.getLogger("dataforge.rime")

# Contextual filler phrases categorized by query type
FILLER_PHRASES = {
    "sales": [
        "Let me pull up the sales figures.",
        "Analyzing the sales data now.",
        "Crunching those sales numbers for you.",
    ],
    "users": [
        "Let me check the user analytics.",
        "Pulling up the user data now.",
        "Looking into the user metrics.",
    ],
    "financials": [
        "Let me review the financial data.",
        "Analyzing the financial records now.",
        "Crunching the revenue numbers.",
    ],
    "default": [
        "Let me analyze that for you.",
        "Working on that right now.",
        "Let me crunch those numbers.",
        "Pulling up the data now.",
        "Analyzing the information.",
        "Give me just a moment.",
    ],
}


def pick_filler(query_text: str) -> str:
    """Select a contextual filler phrase based on the query content."""
    query_lower = query_text.lower()
    if any(w in query_lower for w in ["sale", "revenue", "product", "region"]):
        phrases = FILLER_PHRASES["sales"]
    elif any(w in query_lower for w in ["user", "session", "bounce", "active"]):
        phrases = FILLER_PHRASES["users"]
    elif any(w in query_lower for w in ["financ", "profit", "expense", "cost"]):
        phrases = FILLER_PHRASES["financials"]
    else:
        phrases = FILLER_PHRASES["default"]
    return random.choice(phrases)


class RimeTTS:
    """
    Rime TTS client with cancellation support.
    
    Uses the Coda model with the celeste voice.
    Synthesizes full audio, then sends in properly-sized chunks
    to avoid broken MP3 frames in the browser.
    """

    RIME_ENDPOINT = "https://users.rime.ai/v1/rime-tts"
    MODEL_ID = "coda"
    SPEAKER = "celeste"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("RIME_API_KEY", "")
        self.active_generation_id: Optional[int] = None
        self.last_filler_text: str = ""
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Reuse httpx client for connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    def _body(self, text: str, speed: float = 1.0) -> dict:
        return {
            "text": text,
            "speaker": self.SPEAKER,
            "modelId": self.MODEL_ID,
            "speedAlpha": speed,
            "reduceLatency": True,
        }

    def cancel(self):
        """Cancel the current synthesis by invalidating generation ID."""
        self.active_generation_id = None

    async def synthesize_filler(self, query_text: str) -> Optional[str]:
        """
        Synthesize a short contextual filler phrase.
        Returns base64-encoded MP3 audio string, or None on failure.
        """
        filler_text = pick_filler(query_text)
        self.last_filler_text = filler_text

        if not self.api_key:
            logger.warning("No Rime API key — skipping filler")
            return None

        try:
            client = await self._get_client()
            response = await client.post(
                self.RIME_ENDPOINT,
                headers=self._headers(),
                json=self._body(filler_text, speed=1.05),
            )
            response.raise_for_status()
            return base64.b64encode(response.content).decode("utf-8")
        except Exception as e:
            logger.error(f"Filler synthesis failed: {e}")
            return None

    async def synthesize_streaming(
        self, text: str, generation_id: int
    ) -> AsyncGenerator[str, None]:
        """
        Synthesize full audio then yield in large chunks for smooth playback.
        
        Instead of streaming tiny 4KB chunks (which cause broken MP3 frames
        and crackling in the browser), we fetch the complete audio and split
        it into properly-sized chunks that the browser can decode cleanly.
        """
        self.active_generation_id = generation_id

        if not self.api_key:
            logger.warning("No Rime API key — yielding nothing")
            return

        try:
            # Fetch complete audio (Rime is fast enough for <3 sentence responses)
            client = await self._get_client()
            response = await client.post(
                self.RIME_ENDPOINT,
                headers=self._headers(),
                json=self._body(text),
                timeout=20.0,
            )
            response.raise_for_status()
            
            audio_data = response.content
            
            if self.active_generation_id != generation_id:
                return
            
            # Send as a single complete audio chunk for clean playback
            # This avoids MP3 frame boundary issues entirely
            if audio_data:
                yield base64.b64encode(audio_data).decode("utf-8")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Rime API error {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
