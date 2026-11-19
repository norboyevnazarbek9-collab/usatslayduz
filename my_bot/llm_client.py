import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str = (os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL: str = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()

OPENAI_API_KEY: str = (os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_MODEL: str = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()


async def call_llm(prompt: str) -> str:
    """
    GEMINI_API_KEY yoki OPENAI_API_KEY mavjudligiga qarab matn qaytaradi.
    """
    if GEMINI_API_KEY:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text or ""

    if OPENAI_API_KEY:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        completion = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return completion.choices[0].message.content or ""

    raise RuntimeError(
        "LLM API kaliti topilmadi. .env faylga GEMINI_API_KEY yoki OPENAI_API_KEY kiriting."
    )
