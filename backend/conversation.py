"""
Conversation State Manager for DataForge
Handles generation IDs, cancellation fencing, and heard-context tracking.
"""

import asyncio
from typing import List, Dict, Any, Optional


class ConversationState:
    """
    Manages per-connection conversation state with generation-based fencing.
    
    Key concepts:
    - Each user query gets a monotonically increasing generationId
    - Interruptions mark a generation as cancelled via asyncio.Event
    - heard_context tracks what the user actually heard (for follow-ups)
    - Stale results are silently discarded if their generation is cancelled
    """

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.current_generation_id: int = 0
        self.active_tasks: Dict[int, asyncio.Event] = {}
        self.heard_context: List[Dict[str, Any]] = []

    def new_query(self, text: str) -> int:
        """
        Register a new user query.
        Returns the assigned generationId.
        """
        self.current_generation_id += 1
        gen_id = self.current_generation_id

        msg = {
            "role": "user",
            "content": text,
            "generationId": gen_id,
            "wasHeard": True,
        }
        self.messages.append(msg)
        self.heard_context.append(msg)

        # Create cancellation event (set = cancelled)
        self.active_tasks[gen_id] = asyncio.Event()
        return gen_id

    def interrupt(self, generation_id: int):
        """
        Mark a generation as cancelled.
        Sets the cancellation event so background tasks can check it.
        """
        if generation_id in self.active_tasks:
            self.active_tasks[generation_id].set()

        # Mark any assistant response for this generation as not heard
        for msg in self.messages:
            if (
                msg.get("generationId") == generation_id
                and msg.get("role") == "assistant"
            ):
                msg["wasHeard"] = False
                if msg in self.heard_context:
                    self.heard_context.remove(msg)

    def add_response(
        self, text: str, generation_id: int, was_heard: bool = True
    ):
        """Record an assistant response."""
        msg = {
            "role": "assistant",
            "content": text,
            "generationId": generation_id,
            "wasHeard": was_heard,
        }
        self.messages.append(msg)
        if was_heard:
            self.heard_context.append(msg)

    def is_cancelled(self, generation_id: int) -> bool:
        """Check if a generation has been cancelled."""
        evt = self.active_tasks.get(generation_id)
        if evt is None:
            return True  # Unknown generation = treat as cancelled
        return evt.is_set()

    def get_context_for_llm(self) -> List[Dict[str, str]]:
        """
        Return conversation context based on what the user actually heard.
        This ensures follow-up queries reference the correct state.
        """
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.heard_context[-10:]  # Last 10 messages
        ]

    def mark_heard(self, generation_id: int):
        """Mark all messages for a generation as heard."""
        for msg in self.messages:
            if msg.get("generationId") == generation_id:
                msg["wasHeard"] = True
                if msg not in self.heard_context:
                    self.heard_context.append(msg)

    def cleanup_old_generations(self, keep_last: int = 20):
        """Remove old cancellation events to prevent memory leaks."""
        if len(self.active_tasks) > keep_last:
            old_ids = sorted(self.active_tasks.keys())[:-keep_last]
            for old_id in old_ids:
                del self.active_tasks[old_id]
