import asyncio
import os
from backend.llm_service import LLMService

async def main():
    service = LLMService(api_key="dummy")
    service.groq_api_key = "dummy"
    try:
        res = await service._primary_analyze_query("test", "test system", "test context")
        print(res)
    except Exception as e:
        print(f"Error: {repr(e)}")

asyncio.run(main())
