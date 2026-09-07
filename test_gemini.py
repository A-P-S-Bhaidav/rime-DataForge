import asyncio
from google import genai
from google.genai import types

async def main():
    client = genai.Client(api_key="dummy_key_to_test_model_name")
    try:
        response = await client.aio.models.generate_content(
            model="gemini-1.5-flash",
            contents="hello"
        )
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
