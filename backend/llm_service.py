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

SYSTEM_PROMPT = """You are DataForge, a highly intelligent voice-native AI data analyst. You analyze ANY dataset — built-in or user-uploaded — and produce the most insightful analysis possible.
    
## Available Datasets
{datasets}

## Response Types — Choose the BEST representation:
- "chart": Data that has clear visual patterns (trends, comparisons, distributions)
- "table": Raw records, filtered lists, or data that needs exact values shown
- "chart_and_insight": Chart WITH detailed analytical commentary (PREFERRED for most queries)
- "insight": Pure text analysis when no visualization makes sense (e.g., "what's the average?")

## Chart Types — Pick the MOST appropriate:
- "bar": Comparing categories (sales by region, counts by type)
- "line": Trends over time (daily users, monthly revenue)
- "area": Cumulative trends, volume over time
- "pie": Proportional breakdown (< 8 categories only)
- "scatter": Correlation between two numeric variables
- "stacked_bar": Category comparison with sub-breakdowns
- "horizontal_bar": When category labels are long
- "composed": Overlay bar + line (e.g., revenue bars + profit line)

## Multi-turn Follow-ups (CRITICAL)
You are in a conversation. Check the `Previous query plan` section carefully.
- If the user says "filter that by X", "only show Y", "break it down by Z", "what about Q1", "now show me...", "for the North region only" — this is a FOLLOW-UP.
- For follow-ups: use the SAME dataset, KEEP existing operations, and ADD/MODIFY the relevant filter or grouping.
- Previous query plan will show you exactly what dataset and operations were used last.

## Rules for spoken_response (read aloud by TTS):
1. Max 2-3 short conversational sentences
2. Round large numbers: say "about 2.5 million" not "2,487,321"
3. No bullet points, lists, or markdown
4. Lead with the key insight

## Rules for detailed_insights (shown as text in the UI):
- Provide 3-6 bullet points of analytical findings
- Include specific numbers and percentages
- Note outliers, trends, patterns, and anomalies
- Compare categories or time periods when relevant
- Suggest possible explanations or next questions
- Use markdown formatting (bold for emphasis, bullet points)

## Rules for operations:
- Use EXACT column names from the dataset
- Operation types: filter, groupby_agg, sort, top_n, value_counts, date_filter, multi_group, rename
- filter: {{"type":"filter","params":{{"column":"col","value":"val","operator":"=="}}}}
- groupby_agg: {{"type":"groupby_agg","params":{{"group_col":"col","agg_col":"col2","agg_func":"sum"}}}}
- sort: {{"type":"sort","params":{{"column":"col","ascending":false}}}}
- top_n: {{"type":"top_n","params":{{"column":"col","n":10,"ascending":false}}}}
- value_counts: {{"type":"value_counts","params":{{"column":"col"}}}}
- date_filter: {{"type":"date_filter","params":{{"column":"date","start":"2024-01-01","end":"2024-06-30"}}}}
- multi_group: {{"type":"multi_group","params":{{"group_cols":["col1","col2"],"agg_col":"val","agg_func":"sum"}}}}
- Operators: ==, >, <, >=, <=, !=, contains
- Aggregation functions: sum, mean, count, min, max

## You MUST return ONLY a JSON object with these fields:
- dataset: string (dataset ID)
- operations: array of operation objects
- response_type: "chart" | "table" | "insight" | "chart_and_insight"
- chart_type: string (one of the chart types above, or null if response_type is "insight" or "table")
- chart_config: {{"x": "column", "y": "column", "title": "Chart Title"}} (or null)
- spoken_response: string (what to say aloud, 2-3 sentences max)
- detailed_insights: string (markdown-formatted analytical findings, 3-6 bullet points)
- filler_phrase: string (short phrase like "Let me analyze that")
"""


class LLMService:
    """Google Gemini LLM service."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = genai.Client(api_key=self.api_key)

    async def analyze_query(
        self,
        user_query: str,
        context: Dict[str, Any],
        available_datasets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze a user query and produce a structured analysis plan."""
        datasets_str = json.dumps(available_datasets, indent=2)
        system = SYSTEM_PROMPT.format(datasets=datasets_str)

        # Build context
        context_str = ""
        if context:
            messages = context.get("messages", [])
            if messages:
                context_str = "\nRecent conversation:\n"
                for msg in messages[-4:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    context_str += f"- {role}: {content}\n"
            
            last_plan = context.get("last_query_plan")
            if last_plan:
                context_str += f"\nPrevious query plan:\n{json.dumps(last_plan, indent=2)}\n"

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
            required = ["dataset", "spoken_response"]
            for field in required:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")

            # Add defaults for optional/new fields
            result["response_type"] = result.get("response_type", "chart_and_insight")
            result["detailed_insights"] = result.get("detailed_insights", "")
            if "operations" not in result:
                result["operations"] = []
                
            return result

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str:
                logger.error("Quota error detected.")
                return {
                    "dataset": "sales",
                    "operations": [],
                    "response_type": "insight",
                    "detailed_insights": "The AI service is currently experiencing high demand or has exceeded its quota limit. Please try again later.",
                    "chart_type": None,
                    "chart_config": None,
                    "spoken_response": "I'm sorry, but I've reached my quota limit for now. Please try again later.",
                    "filler_phrase": "Let me check."
                }
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
                "response_type": "chart_and_insight",
                "detailed_insights": "- Strong performance across regions.\n- Consider focusing on underperforming areas.",
                "chart_type": "bar",
                "chart_config": {"x": "region", "y": "amount", "title": "Sales by Region"},
                "spoken_response": "Here's a breakdown of sales across all regions. The chart shows the total sales amount for each region.",
                "filler_phrase": "Pulling up the sales data.",
            }
        elif any(w in query_lower for w in ["user", "growth", "active", "session", "traffic"]):
            return {
                "dataset": "users",
                "operations": [],
                "response_type": "chart_and_insight",
                "detailed_insights": "- Active users track consistently.\n- Some seasonal trends observed.",
                "chart_type": "line",
                "chart_config": {"x": "date", "y": "daily_active_users", "title": "Daily Active Users"},
                "spoken_response": "Here's the daily active users trend over time. You can see the overall growth pattern in the chart.",
                "filler_phrase": "Checking the user analytics.",
            }
        elif any(w in query_lower for w in ["financ", "profit", "expense", "revenue", "money", "cost"]):
            return {
                "dataset": "financials",
                "operations": [],
                "response_type": "chart_and_insight",
                "detailed_insights": "- Revenue shows steady growth.\n- Expenses remain proportional.",
                "chart_type": "area",
                "chart_config": {"x": "month", "y": "revenue", "title": "Monthly Revenue"},
                "spoken_response": "Here's the monthly revenue overview. The chart shows the revenue trend over the reporting period.",
                "filler_phrase": "Looking at the financials.",
            }
        else:
            return {
                "dataset": "sales",
                "operations": [{"type": "groupby_agg", "params": {"group_col": "region", "agg_col": "amount", "agg_func": "sum"}}],
                "response_type": "chart_and_insight",
                "detailed_insights": "- Data suggests regional variances.\n- Further breakdowns might be useful.",
                "chart_type": "bar",
                "chart_config": {"x": "region", "y": "amount", "title": "Sales Overview"},
                "spoken_response": "Here's a general overview of the sales data broken down by region.",
                "filler_phrase": "Let me look into that.",
            }
