import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer dummy"},
            json={
                "model": "invalid-model-name",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        print(response.status_code, response.text)

asyncio.run(main())
