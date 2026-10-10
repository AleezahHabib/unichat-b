import json
import logging
from uuid import UUID
from agents import Runner
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.core.errors import AppError
from app.core.rate_limit import check_ai_rate_limit
from app.features.ai_assistant.agents.assistant_agent import create_assistant_agent
from app.features.ai_assistant.agents.context import AssistantContext
from app.features.ai_assistant.agents.drafter_agent import create_drafter_agent
from app.features.ai_assistant.agents.model_provider import get_openai_client
from app.features.ai_assistant.agents.qa_agent import create_qa_agent
from app.features.ai_assistant.agents.summarizer_agent import create_summarizer_agent
from app.features.ai_assistant.embeddings import embed_query, is_ai_enabled
from app.features.ai_assistant.repository import ai_assistant_repository
from app.features.ai_assistant.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    Citation,
    DraftReplyRequest,
    DraftReplyResponse,
    SearchResult,
    SummarizeRequest,
    SummarizeResponse,
)
from app.features.messaging.repository import message_repository
from app.features.messaging.service import message_service
from app.features.workspaces_and_channels.models import Channel, ChannelMember, WorkspaceMember

logger = logging.getLogger(__name__)


class AIAssistantService:
    def _check_ai_enabled(self):
        if not is_ai_enabled():
            raise AppError(
                message="AI features are disabled because no GEMINI_API_KEY is configured",
                code="ai_disabled",
                status_code=503,
            )

    async def _check_rate_limit(self, redis: Redis, user_id: UUID):
        allowed, retry_after = await check_ai_rate_limit(redis, str(user_id))
        if not allowed:
            raise AppError(
                message=f"AI assistant is busy. Please try again in {retry_after}s",
                code="ai_busy",
                status_code=503,
            )

    async def _get_joined_channel_ids(self, db: AsyncSession, user_id: UUID, workspace_id: UUID) -> set[UUID]:
        stmt = (
            select(ChannelMember.channel_id)
            .join(Channel, ChannelMember.channel_id == Channel.id)
            .where(
                ChannelMember.user_id == user_id,
                Channel.workspace_id == workspace_id,
            )
        )
        result = await db.execute(stmt)
        return set(result.scalars().all())

    async def _is_workspace_member(self, db: AsyncSession, user_id: UUID, workspace_id: UUID) -> bool:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def chat(
        self,
        db: AsyncSession,
        redis: Redis,
        user_id: UUID,
        req: AssistantChatRequest,
    ) -> AssistantChatResponse:
        self._check_ai_enabled()
        if not await self._is_workspace_member(db, user_id, req.workspace_id):
            raise AppError("You are not a member of this workspace", code="forbidden", status_code=403)
        await self._check_rate_limit(redis, user_id)

        allowed_channels = await self._get_joined_channel_ids(db, user_id, req.workspace_id)
        ctx = AssistantContext(
            user_id=user_id,
            workspace_id=req.workspace_id,
            allowed_channel_ids=allowed_channels,
            session_factory=async_session,
        )

        agent = create_assistant_agent()

        try:
            res = await Runner.run(agent, input=req.message, context=ctx)
            answer = str(res.final_output) if res and res.final_output else "No response generated."
        except Exception as e:
            logger.error(f"Error running assistant_agent: {e}")
            raise AppError("AI service is currently busy. Please try again shortly.", code="ai_busy", status_code=503)

        # Build citations for seen messages
        citations: list[dict] = []
        if ctx.seen_message_ids:
            seen_msgs = await ai_assistant_repository.get_messages_by_ids(db, list(ctx.seen_message_ids))
            for m in seen_msgs:
                citations.append({
                    "message_id": str(m["message_id"]),
                    "channel_id": str(m["channel_id"]) if m.get("channel_id") else None,
                    "author_name": m["author_name"],
                    "channel_name": m["channel_name"],
                    "created_at": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
                    "snippet": m["body"][:100],
                    "source": m.get("source", "unichat"),
                })

        # Save to chat history
        await ai_assistant_repository.create_chat_entry(
            db, user_id, req.workspace_id, req.session_id, "user", req.message
        )
        ai_entry = await ai_assistant_repository.create_chat_entry(
            db, user_id, req.workspace_id, req.session_id, "assistant", answer, citations
        )

        return AssistantChatResponse(
            id=ai_entry.id,
            session_id=ai_entry.session_id,
            role="assistant",
            content=answer,
            citations=[Citation(**c) for c in citations],
            created_at=ai_entry.created_at,
        )

    async def get_history(
        self, db: AsyncSession, user_id: UUID, workspace_id: UUID, session_id: str
    ) -> list[AssistantChatResponse]:
        entries = await ai_assistant_repository.get_session_history(
            db, user_id, workspace_id, session_id
        )
        return [
            AssistantChatResponse(
                id=e.id,
                session_id=e.session_id,
                role=e.role,
                content=e.content,
                citations=[Citation(**c) for c in (e.citations or [])],
                created_at=e.created_at,
            )
            for e in entries
        ]

    async def summarize(
        self,
        db: AsyncSession,
        redis: Redis,
        user_id: UUID,
        req: SummarizeRequest,
    ) -> SummarizeResponse:
        self._check_ai_enabled()
        await self._check_rate_limit(redis, user_id)

        # Check membership
        channel = await message_repository.get_channel(db, req.channel_id) if hasattr(message_repository, "get_channel") else None
        messages = await ai_assistant_repository.get_recent_messages(
            db, req.channel_id, hours=req.since_hours
        )
        if not messages:
            return SummarizeResponse(
                summary="No messages found in this timeframe to summarize.",
                key_decisions=[],
                action_items=[],
                message_count=0,
            )

        context_lines = [
            f'<message id="{m["message_id"]}" channel="#{m["channel_name"]}" author="{m["author_name"]}" at="{m["created_at"].isoformat()}">{m["body"]}</message>'
            for m in messages
        ]
        prompt = f"Summarize recent messages in #{messages[0]['channel_name']}:\n" + "\n".join(context_lines)

        allowed_channels = {req.channel_id}
        ctx = AssistantContext(
            user_id=user_id,
            workspace_id=messages[0]["channel_id"] if "channel_id" in messages[0] else UUID("00000000-0000-0000-0000-000000000000"),
            allowed_channel_ids=allowed_channels,
            session_factory=async_session,
        )

        agent = create_summarizer_agent()

        try:
            res = await Runner.run(agent, input=prompt, context=ctx)
            out = res.final_output if res else None

            if hasattr(out, "key_points"):
                key_pts = out.key_points or []
                decisions = out.decisions or []
                open_qs = out.open_questions or []
                summary_text = f"Summary of {len(messages)} messages in #{messages[0]['channel_name']} over the last {req.since_hours}h."
            else:
                summary_text = str(out or "Summary generated.")
                key_pts = [summary_text]
                decisions = []
                open_qs = []

            # Build citations for the summarized messages
            citations = [
                Citation(
                    message_id=m["message_id"],
                    channel_id=m.get("channel_id"),
                    author_name=m["author_name"],
                    channel_name=m["channel_name"],
                    created_at=m["created_at"],
                    snippet=m["body"][:100],
                    source=m.get("source", "unichat"),
                )
                for m in messages
            ]

            return SummarizeResponse(
                summary=summary_text,
                key_points=key_pts,
                decisions=decisions,
                open_questions=open_qs,
                key_decisions=decisions,
                action_items=open_qs,
                citations=citations,
                message_count=len(messages),
            )
        except Exception as e:
            logger.error(f"Summarizer runner error: {e}")
            raise AppError("Failed to generate channel summary", code="ai_busy", status_code=503)

    async def draft_reply(
        self,
        db: AsyncSession,
        redis: Redis,
        user_id: UUID,
        req: DraftReplyRequest,
    ) -> DraftReplyResponse:
        self._check_ai_enabled()
        await self._check_rate_limit(redis, user_id)

        target = await message_repository.get_message_by_id(db, req.message_id)
        if not target:
            raise AppError("Target message not found", code="message_not_found", status_code=404)

        # Prefetch thread + channel context for 1 Gemini call
        thread_items = []
        if target.parent_id:
            _, replies = await message_repository.get_thread(db, target.parent_id)
            thread_items = [r["message"] for r in replies]

        recent_msgs_raw, _ = await message_repository.get_channel_messages(db, target.channel_id, limit=15)
        recent_msgs = [r["message"] for r in recent_msgs_raw]

        context_lines = [f"<message id='{m.id}'>{m.body}</message>" for m in recent_msgs]
        prompt = f"Target message to reply to:\n<target_message id='{target.id}'>{target.body}</target_message>\n\nRecent Channel Context:\n" + "\n".join(context_lines)

        agent = create_drafter_agent()
        ctx = AssistantContext(
            user_id=user_id,
            workspace_id=target.channel_id,
            allowed_channel_ids={target.channel_id},
            session_factory=async_session,
        )

        try:
            res = await Runner.run(agent, input=prompt, context=ctx)
            draft = str(res.final_output) if res and res.final_output else "Thanks for the update!"
            return DraftReplyResponse(draft=draft.strip())
        except Exception as e:
            logger.error(f"Draft reply runner error: {e}")
            raise AppError("Failed to generate reply draft", code="ai_busy", status_code=503)

    async def search(
        self, db: AsyncSession, user_id: UUID, workspace_id: UUID, query: str, limit: int = 20
    ) -> list[SearchResult]:
        query_clean = query.strip()
        if not query_clean:
            return []

        allowed_channels = await self._get_joined_channel_ids(db, user_id, workspace_id)
        if not allowed_channels:
            return []

        # Try semantic search via embedding vector if key is present
        if is_ai_enabled():
            q_vector = await embed_query(query_clean)
            if q_vector:
                results = await ai_assistant_repository.vector_search(
                    db, workspace_id, allowed_channels, q_vector, limit=limit
                )
                if results:
                    return [
                        SearchResult(
                            message_id=r["message_id"],
                            channel_id=r["channel_id"],
                            channel_name=r["channel_name"],
                            author_name=r["author_name"],
                            body=r["body"],
                            created_at=r["created_at"],
                            score=r.get("score", 0.9),
                            is_semantic=True,
                            source=r.get("source", "unichat"),
                        )
                        for r in results
                    ]

        # Graceful fallback: Keyword ILIKE search
        results = await ai_assistant_repository.keyword_search(
            db, workspace_id, allowed_channels, query_clean, limit=limit
        )
        return [
            SearchResult(
                message_id=r["message_id"],
                channel_id=r["channel_id"],
                channel_name=r["channel_name"],
                author_name=r["author_name"],
                body=r["body"],
                created_at=r["created_at"],
                score=1.0,
                is_semantic=False,
                source=r.get("source", "unichat"),
            )
            for r in results
        ]


ai_assistant_service = AIAssistantService()
