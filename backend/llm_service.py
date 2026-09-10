"""
LLM Service for DataVocal — Google Gemini Integration
Translates natural language queries into data analysis plans.
"""

import json
import os
import re
import logging
import httpx
from typing import Dict, Any, List

from google import genai
from google.genai import types

logger = logging.getLogger("dataforge.llm")

SYSTEM_PROMPT = """You are DataVocal, a highly intelligent voice-native AI data analyst. You analyze ANY dataset — built-in or user-uploaded — and produce the most insightful analysis possible.

## Available Datasets
{datasets}

## EXACT Dataset Schemas (use these EXACT column names):

### Dataset: "sales" (200 rows)
Columns: region, product, quarter, sales_rep, amount, units
- region: "North", "South", "East", "West"
- product: "Widget Alpha", "Widget Beta", "Gadget Pro", "Gadget Lite", "Service Plus"
- quarter: "Q1", "Q2", "Q3", "Q4"
- sales_rep: "Alice", "Bob", "Carol", "David", "Eve", "Frank"
- amount: float (dollar value of sale)
- units: integer (units sold)

### Dataset: "users" (365 rows, daily for 2024)
Columns: date, daily_active_users, sessions, bounce_rate, avg_session_duration_min, new_users, page_views
- date: string "YYYY-MM-DD" (2024-01-01 to 2024-12-30)
- daily_active_users: integer
- sessions: integer
- bounce_rate: float 0.0-1.0
- avg_session_duration_min: float
- new_users: integer
- page_views: integer

### Dataset: "financials" (60 rows, monthly 2020-2024)
Columns: month, revenue, expenses, profit, category, headcount
- month: string "YYYY-MM" (2020-01 to 2024-12)
- revenue: float
- expenses: float
- profit: float (revenue - expenses)
- category: "Software", "Services", "Hardware"
- headcount: integer

## Response Types — Choose the BEST representation:
- "chart_and_insight": Chart WITH detailed analytical commentary (PREFERRED for most queries)
- "chart": Data that has clear visual patterns (trends, comparisons, distributions)
- "table": Raw records, filtered lists, or data that needs exact values shown
- "insight": Pure text analysis when no visualization makes sense (e.g., single-value aggregates like "what's the average?")

## Chart Types — Pick the MOST appropriate:
- "bar": Comparing categories (sales by region, by product, by quarter)
- "line": Trends over time (daily users, monthly revenue)
- "area": Cumulative trends, volume over time
- "pie": Proportional breakdown (< 8 categories only)
- "scatter": Correlation between two numeric variables
- "stacked_bar": Category comparison with sub-breakdowns (e.g., region sales stacked by product)
- "horizontal_bar": When category labels are long
- "composed": Overlay bar + line (e.g., revenue bars + profit line)

## SALES DATASET — All Possible Query Patterns:

### Single-dimension groupings:
- "sales by region" → groupby_agg(group_col="region", agg_col="amount", agg_func="sum"), bar chart
- "sales by product" → groupby_agg(group_col="product", agg_col="amount", agg_func="sum"), bar chart
- "sales by quarter" → groupby_agg(group_col="quarter", agg_col="amount", agg_func="sum"), bar chart
- "units sold by region" → groupby_agg(group_col="region", agg_col="units", agg_func="sum"), bar chart
- "sales by sales rep" → groupby_agg(group_col="sales_rep", agg_col="amount", agg_func="sum"), bar chart
- "number of transactions by region" → groupby_agg(group_col="region", agg_col="amount", agg_func="count"), bar chart
- "average sale amount by product" → groupby_agg(group_col="product", agg_col="amount", agg_func="mean"), bar chart
## Chart Selection Rules
- line: Trends over time (e.g., date vs revenue).
- bar: Comparing categories (e.g., region vs sales).
- pie: Parts of a whole (e.g., category market share).
- area: Cumulative or stacked trends over time.

### CRITICAL DRILL-DOWN RULE:
When filtering to a SINGLE item, group by a DIFFERENT dimension to show meaningful breakdown (e.g., Filter region -> Group by product/quarter). When filtering to MULTIPLE items, group by the same column to compare them side-by-side.

## Multi-turn Follow-ups (CRITICAL)
- If the user says "filter that by X", "only show Y" — this is a FOLLOW-UP.
- For follow-ups: use the SAME dataset as before.
- START from the previous plan's operations, then ADD or MODIFY the relevant filter/grouping.
- If the user asks to compare two items, show them side-by-side using a bar chart grouped by that dimension.
- Example: User: "show sales by region" -> groupby_agg(region). Next User: "filter for North only" -> filter(region, "North") + groupby_agg(quarter)

## Rules for spoken_response (read aloud by TTS):
1. Max 2-3 short conversational sentences
2. Round large numbers: say "about 2.5 million" not "2,487,321"
3. No bullet points, lists, or markdown
4. Lead with the key insight
5. Be conversational and natural

## Rules for detailed_insights (shown as text in the UI) — MUST BE RICH:
- Provide 4-7 bullet points of deep analytical findings
- ALWAYS include aggregate statistics: total, mean, median, min, max, range where relevant
- Calculate percentage shares (e.g., "North accounts for 32% of total sales")
- Calculate growth rates and changes between periods
- Identify the top AND bottom performers with exact values
- Note outliers, anomalies, and interesting patterns
- Compare across dimensions (e.g., "Gadget Pro in the North outsells all other region-product combos")
- Suggest actionable next steps or deeper dives
- Use markdown bold for emphasis (e.g., **$142,000**)
- Example: "- **Total sales: $1,847,320** across all regions. North leads at **$523,410** (28.3%), while South trails at **$387,200** (21.0%). The gap between highest and lowest region is **$136,210** (26%)."

## Rules for operations:
- Use EXACT column names from the dataset schemas above
- Operation types: filter, groupby_agg, sort, top_n, value_counts, date_filter, multi_group, rename
- filter: {{"type":"filter","params":{{"column":"col","value":"val","operator":"=="}}}}
- groupby_agg: {{"type":"groupby_agg","params":{{"group_col":"col","agg_col":"col2","agg_func":"sum"}}}}
- sort: {{"type":"sort","params":{{"column":"col","ascending":false}}}}
- top_n: {{"type":"top_n","params":{{"column":"col","n":10,"ascending":false}}}}
- value_counts: {{"type":"value_counts","params":{{"column":"col"}}}}
- date_filter: {{"type":"date_filter","params":{{"column":"date","start":"2024-01-01","end":"2024-06-30"}}}}
- multi_group: {{"type":"multi_group","params":{{"group_cols":["col1","col2"],"agg_col":"val","agg_func":"sum"}}}}
- Operators: ==, >, <, >=, <=, !=, contains, in, not_in (for 'in' and 'not_in', 'value' MUST be an array)
- Aggregation functions: sum, mean, count, min, max

## You MUST return ONLY a valid json object with these fields:
- dataset: string (dataset ID — "sales", "users", or "financials")
- operations: array of operation objects (can be empty for raw data)
- response_type: "chart" | "table" | "insight" | "chart_and_insight"
- chart_type: string (one of the chart types above, or null if response_type is "insight" or "table")
- chart_config: {{"x": "column", "y": "column", "title": "Descriptive Chart Title"}} (or null)
- spoken_response: string (what to say aloud, 2-3 sentences max)
- detailed_insights: string (markdown-formatted rich analytical findings, 4-7 bullet points with aggregates)
- filler_phrase: string (short phrase like "Let me analyze that")
"""


class LLMService:
    """LLM service prioritizing Groq with Gemini fallback."""

    def __init__(self, api_key: str = None):
        self.gemini_api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        else:
            self.gemini_client = None

    async def analyze_query(
        self,
        user_query: str,
        context: Dict[str, Any],
        available_datasets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze a user query and produce a structured analysis plan."""
        datasets_str = json.dumps(available_datasets, separators=(',', ':'))
        system = SYSTEM_PROMPT.format(datasets=datasets_str)

        # Build context
        context_str = ""
        if context:
            messages = context.get("messages", [])
            if messages:
                context_str = "\n## Recent conversation (what the user heard so far):\n"
                for msg in messages[-6:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    context_str += f"- {role}: {content}\n"
            
            last_plan = context.get("last_query_plan")
            if last_plan:
                # Only include relevant fields to keep context focused
                plan_summary = {
                    "dataset": last_plan.get("dataset"),
                    "operations": last_plan.get("operations", []),
                    "chart_type": last_plan.get("chart_type"),
                    "chart_config": last_plan.get("chart_config"),
                }
                context_str += f"\n## Previous query plan (the last chart/analysis shown to the user):\n{json.dumps(plan_summary, separators=(',', ':'))}\n"
                context_str += "\nIMPORTANT: If the user's new query is a follow-up (filter, drill-down, comparison), you MUST build upon the previous plan's dataset and operations. Add/modify filters or groupings as needed.\n"

        user_prompt = f"{context_str}\nUser query: {user_query}\n\nReturn ONLY a valid json object, nothing else."

        try:
            return await self._primary_analyze_query(user_prompt, system, context_str)
        except Exception as e:
            groq_error = str(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                groq_error += f"\nGroq Response Details: {e.response.text}"
            logger.warning(f"Groq failed: {groq_error}. Trying fallback LLM...")
            try:
                return await self._fallback_analyze_query(user_prompt, system, context_str)
            except Exception as fallback_err:
                gemini_error = str(fallback_err)
                if hasattr(fallback_err, 'response') and hasattr(fallback_err.response, 'text'):
                    gemini_error += f"\nGemini Response Details: {fallback_err.response.text}"
                logger.error(f"Fallback LLM also failed: {gemini_error}")
                fallback_res = self._fallback_response(user_query)
                # Surface the error to the user in the UI
                error_msg = f"**SYSTEM WARNING:** LLM Analysis failed and fell back to generic responses.\n- **Groq Error:** {groq_error}\n- **Gemini Error:** {gemini_error}\n\n---\n"
                fallback_res["detailed_insights"] = error_msg + fallback_res.get("detailed_insights", "")
                return fallback_res

    async def _primary_analyze_query(self, user_prompt: str, system: str, context_str: str) -> Dict[str, Any]:
        """Primary LLM using Groq API (Llama-3-70B)."""
        if not self.groq_api_key:
            raise ValueError("No GROQ_API_KEY found.")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2
                },
                timeout=15.0
            )
            response.raise_for_status()
            result_json = response.json()
            raw_text = result_json["choices"][0]["message"]["content"]
            
            logger.info(f"Primary LLM (Groq) raw response: {raw_text[:200]}")
            result = self._extract_json(raw_text)

            required = ["dataset", "spoken_response"]
            for field in required:
                if field not in result:
                    result[field] = ""
            
            # Add defaults for optional/new fields
            result["response_type"] = result.get("response_type", "chart_and_insight")
            result["detailed_insights"] = result.get("detailed_insights", "")
            if "operations" not in result:
                result["operations"] = []
                
            return result

    async def _fallback_analyze_query(self, user_prompt: str, system: str, context_str: str) -> Dict[str, Any]:
        """Fallback to Gemini if Groq hits rate limits or fails."""
        if not self.gemini_client:
            raise ValueError("No GEMINI_API_KEY found for fallback.")

        response = await self.gemini_client.aio.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_text(text=system + "\n\n" + user_prompt)
                ])
            ],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )

        raw_text = response.text.strip()
        logger.info(f"Fallback LLM (Gemini) raw response: {raw_text[:200]}")

        result = self._extract_json(raw_text)

        required = ["dataset", "spoken_response"]
        for field in required:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")

        result["response_type"] = result.get("response_type", "chart_and_insight")
        result["detailed_insights"] = result.get("detailed_insights", "")
        if "operations" not in result:
            result["operations"] = []
            
        return result

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

        # Sales dataset — detect specific sub-patterns
        if any(w in query_lower for w in ["product", "widget", "gadget", "service plus"]):
            return {
                "dataset": "sales",
                "operations": [
                    {"type": "groupby_agg", "params": {"group_col": "product", "agg_col": "amount", "agg_func": "sum"}},
                    {"type": "sort", "params": {"column": "amount", "ascending": False}}
                ],
                "response_type": "chart_and_insight",
                "detailed_insights": "- **Total sales across all products** shown in descending order.\n- Gadget Pro typically leads with the highest average transaction value at around $15,000 per sale.\n- Widget Alpha and Widget Beta are mid-range performers.\n- Gadget Lite has the lowest per-transaction value but may have high volume.\n- Consider drilling down by region or quarter for deeper analysis.",
                "chart_type": "bar",
                "chart_config": {"x": "product", "y": "amount", "title": "Total Sales by Product"},
                "spoken_response": "Here's total sales broken down by product. You can see which products are driving the most revenue.",
                "filler_phrase": "Pulling up product data.",
            }
        elif any(w in query_lower for w in ["quarter", "q1", "q2", "q3", "q4", "quarterly"]):
            return {
                "dataset": "sales",
                "operations": [{"type": "groupby_agg", "params": {"group_col": "quarter", "agg_col": "amount", "agg_func": "sum"}}],
                "response_type": "chart_and_insight",
                "detailed_insights": "- **Quarterly sales distribution** across Q1 through Q4.\n- Look for seasonal patterns — Q4 often shows holiday-driven spikes.\n- Compare quarters to identify growth or decline trends.\n- Try breaking down by product or region for deeper patterns.",
                "chart_type": "bar",
                "chart_config": {"x": "quarter", "y": "amount", "title": "Sales by Quarter"},
                "spoken_response": "Here's the quarterly sales breakdown. You can see how performance varies across the year.",
                "filler_phrase": "Checking quarterly numbers.",
            }
        elif any(w in query_lower for w in ["sale", "region", "north", "south", "east", "west"]):
            return {
                "dataset": "sales",
                "operations": [{"type": "groupby_agg", "params": {"group_col": "region", "agg_col": "amount", "agg_func": "sum"}}],
                "response_type": "chart_and_insight",
                "detailed_insights": "- **Regional sales comparison** across North, South, East, and West.\n- Each region has roughly 50 transactions in the dataset.\n- Differences in total amount reflect product mix and average deal size.\n- Try asking 'show me North only' to drill down into a specific region.",
                "chart_type": "bar",
                "chart_config": {"x": "region", "y": "amount", "title": "Sales by Region"},
                "spoken_response": "Here's the total sales across all four regions. The chart compares performance side by side.",
                "filler_phrase": "Pulling up regional sales.",
            }
        elif any(w in query_lower for w in ["dau", "daily active", "active user", "user growth", "user trend"]):
            return {
                "dataset": "users",
                "operations": [],
                "response_type": "chart_and_insight",
                "detailed_insights": "- **Daily Active Users** tracked across all of 2024 (365 data points).\n- Base DAU starts around 8,000 with a growth trend reaching about 11,000+.\n- Weekly seasonality creates visible cyclical patterns.\n- New users represent roughly 5-15% of daily active users.\n- Try filtering by date range or comparing with sessions for richer analysis.",
                "chart_type": "line",
                "chart_config": {"x": "date", "y": "daily_active_users", "title": "Daily Active Users Over Time"},
                "spoken_response": "Here's the daily active users trend for 2024. You can see steady growth with weekly seasonal patterns.",
                "filler_phrase": "Checking user analytics.",
            }
        elif any(w in query_lower for w in ["user", "session", "bounce", "traffic", "page view"]):
            return {
                "dataset": "users",
                "operations": [],
                "response_type": "chart_and_insight",
                "detailed_insights": "- **User engagement metrics** for 2024.\n- Sessions correlate strongly with DAU (1.2x to 1.8x multiplier).\n- Average bounce rate hovers around 45% with moderate variance.\n- Page views range from 30K to 180K daily depending on traffic.\n- Try asking about specific metrics like 'bounce rate trend' or 'compare sessions vs new users'.",
                "chart_type": "line",
                "chart_config": {"x": "date", "y": "daily_active_users", "title": "User Analytics Overview"},
                "spoken_response": "Here's an overview of user analytics over time. The chart shows the daily active users trend.",
                "filler_phrase": "Checking the user data.",
            }
        elif any(w in query_lower for w in ["financ", "profit", "expense", "revenue", "money", "cost", "headcount"]):
            return {
                "dataset": "financials",
                "operations": [],
                "response_type": "chart_and_insight",
                "detailed_insights": "- **Monthly financial data** spanning 2020 to 2024 (60 months).\n- Revenue shows a strong upward trend from ~$80K/month to ~$170K/month.\n- Expenses run at approximately 65% of revenue.\n- Profit margins have remained relatively stable.\n- Categories cycle between Software, Services, and Hardware.\n- Try asking 'revenue vs expenses' or 'profit by category' for deeper dives.",
                "chart_type": "line",
                "chart_config": {"x": "month", "y": "revenue", "title": "Monthly Revenue Trend"},
                "spoken_response": "Here's the monthly revenue trend from 2020 to 2024. You can see steady growth over the five-year period.",
                "filler_phrase": "Looking at the financials.",
            }
        else:
            return {
                "dataset": "sales",
                "operations": [{"type": "groupby_agg", "params": {"group_col": "region", "agg_col": "amount", "agg_func": "sum"}}],
                "response_type": "chart_and_insight",
                "detailed_insights": "- **Sales overview** broken down by region.\n- 200 total transactions across 4 regions, 5 products, and 4 quarters.\n- Try asking more specific questions like 'top selling products', 'quarterly trends', or 'sales by rep'.",
                "chart_type": "bar",
                "chart_config": {"x": "region", "y": "amount", "title": "Sales Overview by Region"},
                "spoken_response": "Here's a general overview of sales data broken down by region.",
                "filler_phrase": "Let me look into that.",
            }
