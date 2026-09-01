"""
Rime TTS Streaming Client for DataForge
Handles streaming synthesis, filler speech, and cancellation.

Rime Configuration:
  - Model: coda (flagship)
  - Speaker: celeste
  - Language: en
  - Endpoint: https://users.rime.ai/v1/rime-tts
  - Audio Format: mp3 (Accept: audio/mpeg)
  - Transport: Streaming HTTP
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
    Rime TTS streaming client with cancellation support.
    
    Uses the Coda model with the celeste voice via streaming HTTP.
    Supports both full synthesis (for fillers) and streaming synthesis
    (for main responses).
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
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

    def _body(self, text: str) -> dict:
        return {
            "text": text,
            "speaker": self.SPEAKER,
            "modelId": self.MODEL_ID,
        }

    def cancel(self):
        """Cancel the current synthesis by invalidating generation ID."""
        self.active_generation_id = None

    async def synthesize_filler(self, query_text: str) -> Optional[str]:
        """
        Synthesize a short contextual filler phrase.
        Returns base64-encoded MP3 audio string, or None on failure.
        Designed to complete in < 500ms for low perceived latency.
        """
        filler_text = pick_filler(query_text)
        self.last_filler_text = filler_text

        if not self.api_key:
            logger.warning("No Rime API key — returning mock filler")
            return base64.b64encode(b"mock_filler_audio").decode("utf-8")

        try:
            client = await self._get_client()
            response = await client.post(
                self.RIME_ENDPOINT,
                headers=self._headers(),
                json=self._body(filler_text),
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
        Stream Rime TTS audio in base64-encoded MP3 chunks.
        
        Yields base64 strings. Checks active_generation_id between
        chunks to support cancellation.
        """
        self.active_generation_id = generation_id

        if not self.api_key:
            logger.warning("No Rime API key — yielding mock audio")
            yield base64.b64encode(b"mock_audio_chunk_data").decode("utf-8")
            return

        try:
            client = await self._get_client()
            async with client.stream(
                "POST",
                self.RIME_ENDPOINT,
                headers=self._headers(),
                json=self._body(text),
                timeout=15.0,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    # Check for cancellation
                    if self.active_generation_id != generation_id:
                        logger.info(f"TTS cancelled for gen={generation_id}")
                        return
                    if chunk:
                        yield base64.b64encode(chunk).decode("utf-8")
        except httpx.HTTPStatusError as e:
            logger.error(f"Rime API error {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.error(f"TTS streaming error: {e}")

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
