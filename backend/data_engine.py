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
        self.dataset_descriptions: Dict[str, str] = {}
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
        
        self.dataset_descriptions["sales"] = "Sales transactions by region, product, quarter, and rep"
        self.dataset_descriptions["users"] = "Daily user analytics: DAU, sessions, bounce rate, page views"
        self.dataset_descriptions["financials"] = "Monthly financial data: revenue, expenses, profit by category"

    def get_dataset_profile(self, dataset_name: str) -> dict:
        """Return detailed profile of a dataset."""
        df = self.datasets.get(dataset_name)
        if df is None:
            return {}
        
        columns_info = []
        for col in df.columns:
            dtype_str = "text"
            if pd.api.types.is_numeric_dtype(df[col]):
                dtype_str = "numeric"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                dtype_str = "datetime"
            elif pd.api.types.is_categorical_dtype(df[col]) or df[col].nunique() < 20:
                dtype_str = "categorical"

            unique_vals = df[col].dropna().unique()
            col_info = {
                "name": col,
                "dtype": dtype_str,
                "unique_count": len(unique_vals),
                "sample_values": [str(v) for v in unique_vals[:5]]
            }
            if dtype_str == "numeric":
                col_info["min"] = float(df[col].min()) if not pd.isna(df[col].min()) else None
                col_info["max"] = float(df[col].max()) if not pd.isna(df[col].max()) else None
                col_info["mean"] = float(df[col].mean()) if not pd.isna(df[col].mean()) else None
            
            columns_info.append(col_info)

        return {
            "name": dataset_name,
            "description": self.dataset_descriptions.get(dataset_name, "Uploaded dataset"),
            "rows": len(df),
            "columns": columns_info,
            "sample_rows": df.head(3).fillna("").to_dict(orient="records")
        }

    def list_datasets(self) -> List[Dict[str, Any]]:
        """Return metadata about all available datasets."""
        metadata = []
        for name in self.datasets.keys():
            metadata.append(self.get_dataset_profile(name))
        return metadata

    def add_dataset(self, name: str, df: pd.DataFrame, description: str = "Uploaded dataset"):
        """Add a new dataset to the engine."""
        self.datasets[name] = df
        self.dataset_descriptions[name] = description
        logger.info(f"Added new dataset '{name}' with {len(df)} rows")

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

                elif op_type == "top_n":
                    col = params.get("column", "")
                    n = params.get("n", 10)
                    ascending = params.get("ascending", False)
                    if col in df.columns:
                        df = df.sort_values(by=col, ascending=ascending).head(n)

                elif op_type == "value_counts":
                    col = params.get("column", "")
                    if col in df.columns:
                        df = df[col].value_counts().reset_index()
                        df.columns = [col, 'count']

                elif op_type == "describe":
                    df = df.describe().reset_index()

                elif op_type == "date_filter":
                    col = params.get("column", "")
                    start = params.get("start")
                    end = params.get("end")
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col])
                        if start:
                            df = df[df[col] >= pd.to_datetime(start)]
                        if end:
                            df = df[df[col] <= pd.to_datetime(end)]
                        df[col] = df[col].dt.strftime('%Y-%m-%d')

                elif op_type == "multi_group":
                    group_cols = params.get("group_cols", [])
                    agg_col = params.get("agg_col", "")
                    agg_func = params.get("agg_func", "sum")
                    valid_cols = [c for c in group_cols if c in df.columns]
                    if valid_cols and agg_col in df.columns:
                        df = df.groupby(valid_cols, as_index=False)[agg_col].agg(agg_func)

                elif op_type == "rename":
                    mapping = params.get("mapping", {})
                    df = df.rename(columns=mapping)

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
