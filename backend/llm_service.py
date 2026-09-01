"""
LLM Service for DataForge — Google Gemini Integration (new SDK)
Translates natural language queries into data analysis plans.
"""

import json
import os
import logging
from typing import Dict, Any, List

from google import genai
from google.genai import types

logger = logging.getLogger("dataforge.llm")

SYSTEM_PROMPT = """You are DataForge, a voice-native AI data analyst. Your job is to translate natural language questions about data into structured analysis plans.

## Available Datasets
{datasets}

## Rules for spoken_response (CRITICAL — this text will be spoken aloud by Rime TTS):
1. Maximum 2-3 short sentences
2. Round large numbers naturally: say "about 2.5 million" not "2,487,321"
3. No bullet points, lists, or formatting
4. Conversational tone — imagine you're telling a colleague
5. Lead with the key insight, not methodology
6. Use words like "roughly", "around", "about" for approximations
7. Don't say "according to the data" — just state the finding

## Rules for operations:
- Use the exact column names from the dataset
- Available operation types: filter, groupby_agg, sort
- filter params: {{column, value, operator}} where operator is ==, >, <, >=, <=, !=, contains
- groupby_agg params: {{group_col, agg_col, agg_func}} where agg_func is sum, mean, count, min, max
- sort params: {{column, ascending}}

## Return ONLY valid JSON in this exact format:
{{
  "dataset": "sales",
  "operations": [
    {{"type": "groupby_agg", "params": {{"group_col": "region", "agg_col": "amount", "agg_func": "sum"}}}}
  ],
  "chart_type": "bar",
  "chart_config": {{"x": "region", "y": "amount", "title": "Total Sales by Region"}},
  "spoken_response": "The West region leads sales with roughly 1.5 million, followed closely by the North at 1.3 million.",
  "filler_phrase": "Let me pull up the regional sales data."
}}

Chart types: bar, line, area, pie
"""


class LLMService:
    """Google Gemini LLM service using the new google.genai SDK."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = genai.Client(api_key=self.api_key)

    async def analyze_query(
        self,
        user_query: str,
        context: List[Dict[str, str]],
        available_datasets: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Analyze a user query and produce a structured analysis plan.
        """
        datasets_str = json.dumps(available_datasets, indent=2)
        system = SYSTEM_PROMPT.format(datasets=datasets_str)

        # Build conversation for context
        context_str = ""
        if context:
            context_str = "\n\nRecent conversation:\n"
            for msg in context[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context_str += f"- {role}: {content}\n"

        prompt = f"{system}\n{context_str}\n\nUser's current question: {user_query}\n"

        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)

            # Validate required fields
            required = ["dataset", "chart_type", "chart_config", "spoken_response"]
            for field in required:
                if field not in result:
                    raise ValueError(f"Missing field: {field}")

            if "operations" not in result:
                result["operations"] = []

            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}")
            return self._fallback_response(user_query)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._fallback_response(user_query)

    def _fallback_response(self, query: str) -> Dict[str, Any]:
        """Produce a safe fallback response when LLM fails."""
        query_lower = query.lower()
        if any(w in query_lower for w in ["sale", "region", "product"]):
            dataset = "sales"
            x, y = "region", "amount"
        elif any(w in query_lower for w in ["user", "session", "active"]):
            dataset = "users"
            x, y = "date", "daily_active_users"
        else:
            dataset = "financials"
            x, y = "month", "revenue"

        return {
            "dataset": dataset,
            "operations": [],
            "chart_type": "bar",
            "chart_config": {"x": x, "y": y, "title": "Data Overview"},
            "spoken_response": "I had trouble analyzing that. Here's an overview of the data to get started.",
            "filler_phrase": "Let me check on that.",
        }
