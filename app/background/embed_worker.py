import asyncio
import logging
from uuid import UUID
from sqlalchemy import select, text
from app.core.database import async_session
from app.core.leader import is_leader
from app.features.ai_assistant.embeddings import embed_documents, is_ai_enabled
from app.features.ai_assistant.models import MessageEmbedding

logger = logging.getLogger(__name__)

embed_queue: asyncio.Queue[tuple[UUID, str, str, str]] | None = None


def get_embed_queue() -> asyncio.Queue[tuple[UUID, str, str, str]]:
    global embed_queue
    if embed_queue is None:
        embed_queue = asyncio.Queue()
    return embed_queue


def enqueue_message_embedding(message_id: UUID, channel_name: str, author_name: str, body: str) -> None:
    if not is_ai_enabled():
        return
    if not body or not body.strip():
        return
    try:
        get_embed_queue().put_nowait((message_id, channel_name, author_name, body))
    except Exception as e:
        logger.warning(f"Failed to enqueue message {message_id} for embedding: {e}")


async def process_single_embedding(message_id: UUID, channel_name: str, author_name: str, body: str) -> None:
    formatted_text = f"#{channel_name} {author_name}: {body}"
    vectors = await embed_documents([formatted_text])
    if not vectors:
        return

    async with async_session() as db:
        try:
            # Check if embedding exists, update if so, else insert
            stmt = select(MessageEmbedding).where(MessageEmbedding.message_id == message_id)
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.embedding = vectors[0]
            else:
                emb = MessageEmbedding(
                    message_id=message_id,
                    embedding=vectors[0],
                    model="gemini-embedding-001",
                )
                db.add(emb)
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to save embedding for message {message_id}: {e}")
            await db.rollback()


async def embed_worker_loop() -> None:
    logger.info("Starting embedding worker queue loop")
    while True:
        try:
            message_id, channel_name, author_name, body = await get_embed_queue().get()
            await process_single_embedding(message_id, channel_name, author_name, body)
            get_embed_queue().task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in embed_worker_loop: {e}")
            await asyncio.sleep(1)


async def embedding_sweep_loop() -> None:
    logger.info("Starting embedding sweep loop (60s interval)")
    while True:
        try:
            await asyncio.sleep(60)
            if not is_ai_enabled():
                continue
            if not is_leader():
                continue

            async with async_session() as db:
                query = text(
                    """
                    SELECT m.id, c.name, COALESCE(u.name, m.external_author_name, 'Unknown') as author_name, m.body
                    FROM messages m
                    JOIN channels c ON m.channel_id = c.id
                    LEFT JOIN users u ON m.author_id = u.id
                    LEFT JOIN message_embeddings me ON m.id = me.message_id
                    WHERE me.message_id IS NULL AND m.deleted_at IS NULL AND m.body != ''
                    LIMIT 50
                    """
                )
                result = await db.execute(query)
                unembedded = result.fetchall()

                if not unembedded:
                    continue

                texts = [f"#{row.name} {row.author_name}: {row.body}" for row in unembedded]
                vectors = await embed_documents(texts)

                if len(vectors) == len(unembedded):
                    for row, vec in zip(unembedded, vectors):
                        emb = MessageEmbedding(
                            message_id=row.id,
                            embedding=vec,
                            model="gemini-embedding-001",
                        )
                        db.add(emb)
                    await db.commit()
                    logger.info(f"Swept and embedded {len(unembedded)} missing message embeddings")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in embedding_sweep_loop: {e}")
