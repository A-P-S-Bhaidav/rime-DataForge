"""
LLM Service for DataForge — Google Gemini Integration
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

SYSTEM_PROMPT = """You are DataForge, a highly intelligent voice-native AI data analyst. You analyze ANY dataset — built-in or user-uploaded — and produce the most insightful analysis possible.

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

### Multi-dimension cross-tabulations (use multi_group):
- "sales by region and quarter" → multi_group(group_cols=["quarter","region"], agg_col="amount", agg_func="sum"), stacked_bar, x=quarter
- "sales by product and region" → multi_group(group_cols=["region","product"], agg_col="amount", agg_func="sum"), stacked_bar, x=region
- "quarterly sales by product" → multi_group(group_cols=["quarter","product"], agg_col="amount", agg_func="sum"), stacked_bar, x=quarter
- "sales by quarter and sales rep" → multi_group(group_cols=["quarter","sales_rep"], agg_col="amount", agg_func="sum"), stacked_bar
- "product performance by quarter" → multi_group(group_cols=["quarter","product"], agg_col="amount", agg_func="sum"), line chart, x=quarter

### Filtering to specific items:
- "show North region only" → filter(column="region", value="North", operator="==") + groupby_agg by another dimension (product/quarter)
- "show North and South only" → filter(column="region", value=["North","South"], operator="in") + groupby_agg
- "sales for Gadget Pro" → filter(column="product", value="Gadget Pro", operator="==") + groupby_agg(group_col="quarter", ...) for temporal trend
- "Q1 sales only" → filter(column="quarter", value="Q1", operator="==") + groupby_agg(group_col="region" or "product", ...)
- "sales above 10000" → filter(column="amount", value=10000, operator=">")
- "exclude Widget Alpha" → filter(column="product", value="Widget Alpha", operator="!=")

### CRITICAL DRILL-DOWN RULE:
When filtering to a SINGLE item (one region, one product, one quarter), NEVER show a single ungrouped bar.
Instead, group by a DIFFERENT dimension to show meaningful breakdown:
- Filter to 1 region → group by product or quarter
- Filter to 1 product → group by region or quarter
- Filter to 1 quarter → group by region or product
When filtering to MULTIPLE items (e.g., "North and South"), group by the same column to compare them side-by-side.

### Sorting and ranking:
- "top selling products" → groupby_agg(product, amount, sum) + sort(amount, ascending=false)
- "top 3 sales reps" → groupby_agg(sales_rep, amount, sum) + top_n(column="amount", n=3)
- "lowest performing region" → groupby_agg(region, amount, sum) + sort(amount, ascending=true)

### Aggregate / statistical queries (response_type="insight"):
- "what is the average sale amount" → response_type="insight", compute mentally from data
- "total revenue" → response_type="insight"
- "which product has the highest average" → groupby_agg(product, amount, mean) + sort

## USERS DATASET — All Possible Query Patterns:

### Time series (use "line" or "area" chart):
- "daily active users over time" → no operations needed, line chart, x=date, y=daily_active_users
- "show sessions trend" → line chart, x=date, y=sessions
- "bounce rate over time" → line chart, x=date, y=bounce_rate
- "new users trend" → line chart, x=date, y=new_users
- "page views over time" → area chart, x=date, y=page_views

### Multi-metric comparison:
- "compare DAU and sessions" → line chart with both daily_active_users and sessions as y keys
- "compare sessions vs new users vs bounce rate" → line chart with multiple y keys
- "show all user metrics" → composed chart

### Date range filtering:
- "users in January 2024" → date_filter(column="date", start="2024-01-01", end="2024-01-31")
- "last 3 months" → date_filter(column="date", start="2024-10-01", end="2024-12-30")
- "Q1 user data" → date_filter(column="date", start="2024-01-01", end="2024-03-31")
- "first half of the year" → date_filter(column="date", start="2024-01-01", end="2024-06-30")

### Aggregate queries:
- "average daily active users" → response_type="insight"
- "peak DAU" → response_type="insight", mention the max value
- "total page views" → response_type="insight"
- "average bounce rate" → response_type="insight"

## FINANCIALS DATASET — All Possible Query Patterns:

### Time series:
- "monthly revenue trend" → line chart, x=month, y=revenue
- "revenue vs expenses" → composed or line chart with both revenue and expenses
- "profit trend" → line chart or area chart, x=month, y=profit
- "revenue, expenses and profit over time" → line chart, 3 lines
- "headcount growth" → line chart, x=month, y=headcount

### Category breakdowns:
- "revenue by category" → groupby_agg(group_col="category", agg_col="revenue", agg_func="sum"), bar chart
- "profit by category" → groupby_agg(group_col="category", agg_col="profit", agg_func="sum"), bar/pie chart
- "compare categories" → groupby_agg by category with revenue, bar chart

### Date filtering:
- "2024 financials" → date_filter(column="month", start="2024-01", end="2024-12")
- "last year's revenue" → date_filter for 2024
- "2020 vs 2024" → two separate filters or full data with insight comparison

### Category + time:
- "software revenue over time" → filter(column="category", value="Software") + line chart x=month y=revenue
- "hardware profit trend" → filter(column="category", value="Hardware") + line chart

### Aggregate queries:
- "total revenue" → response_type="insight"
- "average monthly profit" → response_type="insight"
- "highest revenue month" → sort + top_n or insight

## Multi-turn Follow-ups (CRITICAL)
You are in a conversation. Check the `Previous query plan` section carefully.
- If the user says "filter that by X", "only show Y", "break it down by Z", "what about Q1", "now show me...", "for the North region only", "exclude X", "just North and South" — this is a FOLLOW-UP.
- For follow-ups: use the SAME dataset as before.
- START from the previous plan's operations, then ADD or MODIFY the relevant filter/grouping.
- If the user asks to "filter for X and Y only" (e.g., "show North and South only"), use the "in" operator: filter(column="region", value=["North","South"], operator="in")
- If the user asks to compare two items, show them side-by-side using a bar chart grouped by that dimension.
- If the user says "go back" or "show all", REMOVE the filters and show the full dataset again.

### Follow-up Examples:
1. User: "show sales by region" → groupby_agg(region, amount, sum)
   User: "filter for North and South only" → filter(region, ["North","South"], "in") + groupby_agg(region, amount, sum)
2. User: "show sales by product" → groupby_agg(product, amount, sum)
   User: "show Gadget Pro only" → filter(product, "Gadget Pro", "==") + groupby_agg(quarter, amount, sum) [drill to temporal]
3. User: "quarterly sales" → groupby_agg(quarter, amount, sum)
   User: "break that down by product" → multi_group([quarter, product], amount, sum)

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

## You MUST return ONLY a JSON object with these fields:
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
                context_str += f"\n## Previous query plan (the last chart/analysis shown to the user):\n{json.dumps(plan_summary, indent=2)}\n"
                context_str += "\nIMPORTANT: If the user's new query is a follow-up (filter, drill-down, comparison), you MUST build upon the previous plan's dataset and operations. Add/modify filters or groupings as needed.\n"

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
                    temperature=0.2,
                    max_output_tokens=2048,
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
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                logger.warning("Gemini quota error detected. Switching to fallback LLM.")
                return await self._fallback_analyze_query(user_query, context, available_datasets)
            
            logger.error(f"LLM analysis failed: {e}", exc_info=True)
            return self._fallback_response(user_query)

    async def _fallback_analyze_query(self, user_query: str, context: dict, available_datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback to Groq API (Llama-3-70B) if Gemini hits rate limits."""
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            logger.error("No GROQ_API_KEY found for fallback.")
            return self._fallback_response(user_query)
        datasets_str = json.dumps(available_datasets, indent=2)
        system = SYSTEM_PROMPT.format(datasets=datasets_str)
        context_str = ""
        if context:
            messages = context.get("messages", [])
            if messages:
                context_str += "\n## Recent conversation (what the user heard so far):\n"
                for msg in messages[-6:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    context_str += f"- {role}: {content}\n"
            
            last_plan = context.get("last_query_plan")
            if last_plan:
                plan_summary = {
                    "dataset": last_plan.get("dataset"),
                    "operations": last_plan.get("operations", []),
                    "chart_type": last_plan.get("chart_type"),
                    "chart_config": last_plan.get("chart_config"),
                }
                context_str += f"\n## Previous query plan (the last chart/analysis shown to the user):\n{json.dumps(plan_summary, indent=2)}\n"
                context_str += "\nIMPORTANT: If the user's new query is a follow-up (filter, drill-down, comparison), you MUST build upon the previous plan's dataset and operations.\n"

        user_prompt = f"{context_str}\nUser query: {user_query}\n\nReturn ONLY a valid JSON object, nothing else."

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama3-70b-8192",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=15.0
                )
                response.raise_for_status()
                result_json = response.json()
                raw_text = result_json["choices"][0]["message"]["content"]
                
                logger.info(f"Fallback LLM raw response: {raw_text[:200]}")
                result = self._extract_json(raw_text)

                required = ["dataset", "spoken_response"]
                for field in required:
                    if field not in result:
                        result[field] = ""
                
                return result
        except Exception as e:
            logger.error(f"Fallback LLM failed: {e}")
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
