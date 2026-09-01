"""
LLM Service for DataForge — Google Gemini Integration
Translates natural language queries into data analysis plans.
"""

import json
import os
import re
import logging
from typing import Dict, Any, List

from google import genai
from google.genai import types

logger = logging.getLogger("dataforge.llm")

SYSTEM_PROMPT = """You are DataForge, a voice-native AI data analyst. Your job is to translate natural language questions about data into structured analysis plans and return JSON.

## Available Datasets
{datasets}

## Rules for spoken_response (CRITICAL — this text will be read aloud by text-to-speech):
1. Maximum 2-3 short sentences
2. Round large numbers: say "about 2.5 million" not "2,487,321"
3. No bullet points, lists, or markdown formatting
4. Conversational tone
5. Lead with the key insight

## Rules for operations:
- Use exact column names from the dataset
- Operation types: filter, groupby_agg, sort
- filter: {{"type":"filter","params":{{"column":"region","value":"North","operator":"=="}}}}
- groupby_agg: {{"type":"groupby_agg","params":{{"group_col":"region","agg_col":"amount","agg_func":"sum"}}}}
- sort: {{"type":"sort","params":{{"column":"amount","ascending":false}}}}
- Operators: ==, >, <, >=, <=, !=, contains
- Aggregation functions: sum, mean, count, min, max

## You MUST return ONLY a JSON object with these fields:
- dataset: string (one of the dataset IDs)
- operations: array of operation objects
- chart_type: "bar" | "line" | "area" | "pie"
- chart_config: {{"x": "column_name", "y": "column_name", "title": "Chart Title"}}
- spoken_response: string (what to say aloud)
- filler_phrase: string (short phrase like "Let me check that")
"""


class LLMService:
    """Google Gemini LLM service."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = genai.Client(api_key=self.api_key)

    async def analyze_query(
        self,
        user_query: str,
        context: List[Dict[str, str]],
        available_datasets: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Analyze a user query and produce a structured analysis plan."""
        datasets_str = json.dumps(available_datasets, indent=2)
        system = SYSTEM_PROMPT.format(datasets=datasets_str)

        # Build context
        context_str = ""
        if context:
            context_str = "\nRecent conversation:\n"
            for msg in context[-4:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context_str += f"- {role}: {content}\n"

        user_prompt = f"{context_str}\nUser query: {user_query}\n\nReturn ONLY a valid JSON object, nothing else."

        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-3.6-flash",
                contents=[
                    types.Content(role="user", parts=[
                        types.Part.from_text(text=system + "\n\n" + user_prompt)
                    ])
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                ),
            )

            raw_text = response.text.strip()
            logger.info(f"LLM raw response: {raw_text[:200]}")

            # Extract JSON from response (handle markdown code blocks)
            result = self._extract_json(raw_text)

            # Validate required fields
            required = ["dataset", "chart_type", "chart_config", "spoken_response"]
            for field in required:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")

            if "operations" not in result:
                result["operations"] = []

            return result

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}", exc_info=True)
            return self._fallback_response(user_query)

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ``` blocks
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding first { ... } block
        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract JSON from LLM response: {text[:100]}")

    def _fallback_response(self, query: str) -> Dict[str, Any]:
        """Produce a safe fallback response when LLM fails."""
        query_lower = query.lower()

        if any(w in query_lower for w in ["sale", "revenue", "region", "product", "quarter"]):
            return {
                "dataset": "sales",
                "operations": [{"type": "groupby_agg", "params": {"group_col": "region", "agg_col": "amount", "agg_func": "sum"}}],
                "chart_type": "bar",
                "chart_config": {"x": "region", "y": "amount", "title": "Sales by Region"},
                "spoken_response": "Here's a breakdown of sales across all regions. The chart shows the total sales amount for each region.",
                "filler_phrase": "Pulling up the sales data.",
            }
        elif any(w in query_lower for w in ["user", "growth", "active", "session", "traffic"]):
            return {
                "dataset": "users",
                "operations": [],
                "chart_type": "line",
                "chart_config": {"x": "date", "y": "daily_active_users", "title": "Daily Active Users"},
                "spoken_response": "Here's the daily active users trend over time. You can see the overall growth pattern in the chart.",
                "filler_phrase": "Checking the user analytics.",
            }
        elif any(w in query_lower for w in ["financ", "profit", "expense", "revenue", "money", "cost"]):
            return {
                "dataset": "financials",
                "operations": [],
                "chart_type": "area",
                "chart_config": {"x": "month", "y": "revenue", "title": "Monthly Revenue"},
                "spoken_response": "Here's the monthly revenue overview. The chart shows the revenue trend over the reporting period.",
                "filler_phrase": "Looking at the financials.",
            }
        else:
            return {
                "dataset": "sales",
                "operations": [{"type": "groupby_agg", "params": {"group_col": "region", "agg_col": "amount", "agg_func": "sum"}}],
                "chart_type": "bar",
                "chart_config": {"x": "region", "y": "amount", "title": "Sales Overview"},
                "spoken_response": "Here's a general overview of the sales data broken down by region.",
                "filler_phrase": "Let me look into that.",
            }
