import math
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def is_ai_enabled() -> bool:
    return bool(settings.GEMINI_API_KEY)


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


async def embed_documents(texts: list[str]) -> list[list[float]]:
    if not is_ai_enabled() or not texts:
        return []

    results: list[list[float]] = []
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        batch_size = 50

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            res = client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=settings.EMBEDDING_DIM,
                ),
            )
            if res and hasattr(res, "embeddings") and res.embeddings:
                for item in res.embeddings:
                    results.append(l2_normalize(item.values))
            elif res and hasattr(res, "embedding") and res.embedding:
                results.append(l2_normalize(res.embedding.values))
    except Exception as e:
        logger.warning(f"embed_documents failed: {e}")

    return results


async def embed_query(text: str) -> list[float] | None:
    if not is_ai_enabled() or not text.strip():
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        res = client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=settings.EMBEDDING_DIM,
            ),
        )
        if res and hasattr(res, "embedding") and res.embedding:
            return l2_normalize(res.embedding.values)
        if res and hasattr(res, "embeddings") and res.embeddings:
            return l2_normalize(res.embeddings[0].values)
    except Exception as e:
        logger.warning(f"embed_query failed: {e}")

    return None
