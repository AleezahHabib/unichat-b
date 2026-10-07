import sys
from openai import OpenAI
from google import genai
from google.genai import types

from app.core.config import settings


def check_ai() -> int:
    if not settings.GEMINI_API_KEY:
        print(
            "Error: GEMINI_API_KEY is not set in backend/.env. "
            "Obtain a free key at https://aistudio.google.com/apikey and add it to backend/.env.",
            file=sys.stderr,
        )
        return 1

    client = OpenAI(
        api_key=settings.GEMINI_API_KEY,
        base_url=settings.GEMINI_BASE_URL,
    )

    # 1. Chat Completion Check
    try:
        chat_resp = client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=[{"role": "user", "content": "Respond with the single word: OK"}],
            max_tokens=10,
        )
        msg = chat_resp.choices[0].message.content or ""
        print(f"Gemini chat OK (model {settings.CHAT_MODEL}): {msg.strip()}")
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg or "API_KEY_INVALID" in err_msg or "INVALID_ARGUMENT" in err_msg:
            print(
                f"Error: Invalid GEMINI_API_KEY. Details: {e}",
                file=sys.stderr,
            )
        elif "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            print(
                f"Error: Gemini rate limit exceeded. Details: {e}",
                file=sys.stderr,
            )
        else:
            print(f"Error during Gemini chat completion: {e}", file=sys.stderr)
        return 1

    # 2. Embeddings Check via google-genai
    try:
        genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        res = genai_client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents="FistaChat foundation test embedding",
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=settings.EMBEDDING_DIM,
            ),
        )
        dims = len(res.embedding.values)
        print(f"Gemini embeddings OK ({dims} dims)")
    except Exception as e:
        print(f"Error during Gemini embedding call: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(check_ai())
