"""
Data Analysis Engine for DataForge
Generates synthetic datasets and executes Pandas operations.
"""

import pandas as pd
import numpy as np
import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("dataforge.data")


class DataEngine:
    """
    In-memory data analysis engine with three sample datasets.
    Uses fixed random seed for reproducibility.
    """

    def __init__(self):
        self.datasets: Dict[str, pd.DataFrame] = {}
        self._generate_synthetic_data()
        logger.info(f"DataEngine initialized with {len(self.datasets)} datasets")

    def _generate_synthetic_data(self):
        """Generate realistic synthetic datasets with fixed seed."""
        np.random.seed(42)

        # ──────────────────────────────────────────────────────
        # 1. Sales Data — 200 transactions across regions/products/quarters
        # ──────────────────────────────────────────────────────
        regions = ["North", "South", "East", "West"]
        products = ["Widget Alpha", "Widget Beta", "Gadget Pro", "Gadget Lite", "Service Plus"]
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        sales_reps = ["Alice", "Bob", "Carol", "David", "Eve", "Frank"]

        sales_rows = []
        for i in range(200):
            region = np.random.choice(regions)
            product = np.random.choice(products)
            quarter = np.random.choice(quarters)
            # Make sales somewhat realistic — different products have different price ranges
            base_price = {"Widget Alpha": 5000, "Widget Beta": 8000, "Gadget Pro": 15000,
                          "Gadget Lite": 3000, "Service Plus": 12000}
            amount = np.random.normal(base_price[product], base_price[product] * 0.3)
            amount = max(500, round(amount, 2))
            sales_rows.append({
                "region": region,
                "product": product,
                "quarter": quarter,
                "sales_rep": np.random.choice(sales_reps),
                "amount": amount,
                "units": np.random.randint(1, 50),
            })
        self.datasets["sales"] = pd.DataFrame(sales_rows)

        # ──────────────────────────────────────────────────────
        # 2. User Analytics — 365 days of daily metrics
        # ──────────────────────────────────────────────────────
        dates = pd.date_range(start="2024-01-01", periods=365)
        base_dau = 8000
        # Add growth trend + weekly seasonality
        trend = np.linspace(0, 3000, 365)
        weekly = 1500 * np.sin(np.arange(365) * 2 * np.pi / 7)
        noise = np.random.normal(0, 500, 365)
        dau = (base_dau + trend + weekly + noise).astype(int).clip(min=2000)

        sessions = (dau * np.random.uniform(1.2, 1.8, 365)).astype(int)
        bounce_rate = np.clip(np.random.normal(0.45, 0.08, 365), 0.15, 0.85)
        avg_duration = np.clip(np.random.normal(4.5, 1.2, 365), 1.0, 12.0)

        self.datasets["users"] = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "daily_active_users": dau,
            "sessions": sessions,
            "bounce_rate": bounce_rate.round(3),
            "avg_session_duration_min": avg_duration.round(1),
            "new_users": (dau * np.random.uniform(0.05, 0.15, 365)).astype(int),
            "page_views": (sessions * np.random.uniform(3, 8, 365)).astype(int),
        })

        # ──────────────────────────────────────────────────────
        # 3. Financial Data — 60 months of revenue/expenses
        # ──────────────────────────────────────────────────────
        months = pd.date_range(start="2020-01-01", periods=60, freq="MS")
        categories = ["Software", "Services", "Hardware"]
        
        fin_rows = []
        for i, month in enumerate(months):
            cat = categories[i % 3]
            # Revenue grows over time
            base_rev = 80000 + i * 1500
            revenue = np.random.normal(base_rev, base_rev * 0.15)
            expenses = np.random.normal(revenue * 0.65, revenue * 0.1)
            fin_rows.append({
                "month": month.strftime("%Y-%m"),
                "revenue": round(max(20000, revenue), 2),
                "expenses": round(max(15000, expenses), 2),
                "profit": round(revenue - expenses, 2),
                "category": cat,
                "headcount": int(30 + i * 0.8 + np.random.randint(-2, 3)),
            })
        self.datasets["financials"] = pd.DataFrame(fin_rows)

    def list_datasets(self) -> List[Dict[str, Any]]:
        """Return metadata about all available datasets."""
        return [
            {
                "name": "sales",
                "description": "Sales transactions by region, product, quarter, and rep",
                "rows": len(self.datasets["sales"]),
                "columns": list(self.datasets["sales"].columns),
            },
            {
                "name": "users",
                "description": "Daily user analytics: DAU, sessions, bounce rate, page views",
                "rows": len(self.datasets["users"]),
                "columns": list(self.datasets["users"].columns),
            },
            {
                "name": "financials",
                "description": "Monthly financial data: revenue, expenses, profit by category",
                "rows": len(self.datasets["financials"]),
                "columns": list(self.datasets["financials"].columns),
            },
        ]

    async def execute_query(
        self,
        query_plan: Dict[str, Any],
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Dict[str, Any]:
        """
        Execute an LLM-generated query plan against the datasets.
        Checks cancel_event between operations to support interruption.
        """
        dataset_name = query_plan.get("dataset", "")
        operations = query_plan.get("operations", [])

        if dataset_name not in self.datasets:
            logger.warning(f"Dataset '{dataset_name}' not found, falling back to 'sales'")
            dataset_name = "sales"

        df = self.datasets[dataset_name].copy()

        for op in operations:
            # Check for cancellation between operations
            if cancel_event and cancel_event.is_set():
                return {"data": [], "columns": [], "cancelled": True}

            op_type = op.get("type", "")
            params = op.get("params", {})

            try:
                if op_type == "filter":
                    col = params.get("column", "")
                    val = params.get("value")
                    operator = params.get("operator", "==")
                    if col in df.columns and val is not None:
                        if operator == "==":
                            df = df[df[col] == val]
                        elif operator == ">":
                            df = df[df[col] > float(val)]
                        elif operator == "<":
                            df = df[df[col] < float(val)]
                        elif operator == ">=":
                            df = df[df[col] >= float(val)]
                        elif operator == "<=":
                            df = df[df[col] <= float(val)]
                        elif operator == "!=":
                            df = df[df[col] != val]
                        elif operator == "contains":
                            df = df[df[col].astype(str).str.contains(str(val), case=False)]

                elif op_type == "groupby_agg":
                    group_col = params.get("group_col", "")
                    agg_col = params.get("agg_col", "")
                    agg_func = params.get("agg_func", "sum")
                    if group_col in df.columns and agg_col in df.columns:
                        df = df.groupby(group_col, as_index=False)[agg_col].agg(agg_func)

                elif op_type == "sort":
                    col = params.get("column", "")
                    ascending = params.get("ascending", False)
                    if col in df.columns:
                        df = df.sort_values(by=col, ascending=ascending)

            except Exception as e:
                logger.warning(f"Operation {op_type} failed: {e}")
                continue

            # Small yield to event loop
            await asyncio.sleep(0)

        # Handle NaN for JSON serialization
        df = df.fillna(0)

        # Round numeric columns for cleaner display
        for col in df.select_dtypes(include=[np.number]).columns:
            df[col] = df[col].round(2)

        records = df.head(100).to_dict(orient="records")  # Cap at 100 rows for charts
        return {"data": records, "columns": list(df.columns)}

    def get_chart_data(
        self,
        data: List[Dict],
        chart_type: str,
        x_col: str,
        y_col: str,
        title: str,
    ) -> Dict[str, Any]:
        """Format data for Recharts frontend consumption."""
        return {
            "chartType": chart_type,
            "data": data,
            "config": {"x": x_col, "y": y_col, "title": title},
        }
