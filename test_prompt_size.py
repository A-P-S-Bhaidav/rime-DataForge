import json
from backend.data_engine import DataEngine
from backend.llm_service import SYSTEM_PROMPT

engine = DataEngine()
datasets = engine.list_datasets()
datasets_str = json.dumps(datasets, separators=(',', ':'))
print("Datasets string length:", len(datasets_str))
print("System prompt length:", len(SYSTEM_PROMPT))
print("Formatted system prompt length:", len(SYSTEM_PROMPT.format(datasets=datasets_str)))
