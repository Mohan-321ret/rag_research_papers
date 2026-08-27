"""Data access for the query lifecycle (queries, logs, answers, citations)."""

import uuid

from sqlalchemy import func, select

from app.models.interaction import (
    Answer,
    Citation,
    Feedback,
    FeedbackRating,
    Query,
    RetrievalLog,
)
from app.repositories.base import BaseRepository


class InteractionRepository(BaseRepository):
    async def create_query(
        self,
        *,
        user_id: uuid.UUID | None,
        query_text: str,
        normalized_text: str | None = None,
        intent: str | None = None,
    ) -> Query:
        query = Query(
            user_id=user_id,
            query_text=query_text,
            normalized_text=normalized_text,
            intent=intent,
        )
        self._session.add(query)
        await self._session.flush()
        return query

    async def add_retrieval_logs(
        self,
        query_id: uuid.UUID,
        hits: list[tuple[uuid.UUID, int, float, str]],
    ) -> None:
        """hits: (chunk_id, rank, score, retriever)."""
        self._session.add_all(
            RetrievalLog(
                query_id=query_id, chunk_id=chunk_id, rank=rank, score=score,
                retriever=retriever,
            )
            for chunk_id, rank, score, retriever in hits
        )
        await self._session.flush()

    async def create_answer(
        self,
        *,
        query_id: uuid.UUID,
        answer_text: str,
        model: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: float | None,
        grounded: bool | None = None,
        confidence: float | None = None,
    ) -> Answer:
        answer = Answer(
            query_id=query_id,
            answer_text=answer_text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            grounded=grounded,
            confidence=confidence,
        )
        self._session.add(answer)
        await self._session.flush()
        return answer

    async def add_citations(
        self,
        answer_id: uuid.UUID,
        citations: list[tuple[uuid.UUID, int, str | None]],
    ) -> None:
        """citations: (chunk_id, marker, snippet)."""
        self._session.add_all(
            Citation(answer_id=answer_id, chunk_id=chunk_id, marker=marker, snippet=snippet)
            for chunk_id, marker, snippet in citations
        )
        await self._session.flush()

    # ---- history ---------------------------------------------------------

    async def list_history(
        self, *, user_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[Query], int]:
        """A user's past queries, newest first. ``Query.answers`` (and each
        answer's citations) are selectin-loaded by the model."""
        base = select(Query).where(Query.user_id == user_id)
        total = await self._session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        result = await self._session.execute(
            # id breaks created_at ties into a total order. Postgres' now()
            # is microsecond-resolution so ties are rare in production, but
            # without a tiebreak paging can repeat or skip rows whenever two
            # rows do share a timestamp.
            base.order_by(Query.created_at.desc(), Query.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_answer(self, answer_id: uuid.UUID) -> Answer | None:
        return await self._session.get(Answer, answer_id)

    # ---- feedback --------------------------------------------------------

    async def create_feedback(
        self,
        *,
        answer_id: uuid.UUID,
        user_id: uuid.UUID | None,
        rating: FeedbackRating,
        comment: str | None,
    ) -> Feedback:
        entry = Feedback(
            answer_id=answer_id, user_id=user_id, rating=rating, comment=comment
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def feedback_counts(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Feedback.rating, func.count()).group_by(Feedback.rating)
        )
        return {str(rating.value if hasattr(rating, "value") else rating): int(count)
                for rating, count in result.all()}

    # ---- aggregates (analytics) -----------------------------------------

    async def count_queries(self) -> int:
        return int(await self._session.scalar(select(func.count()).select_from(Query)) or 0)

    async def count_answers(self) -> int:
        return int(await self._session.scalar(select(func.count()).select_from(Answer)) or 0)

    async def answer_stats(self) -> dict[str, float | int | None]:
        averages = (
            await self._session.execute(
                select(func.avg(Answer.latency_ms), func.avg(Answer.confidence))
            )
        ).one()
        ungrounded = await self._session.scalar(
            select(func.count()).select_from(Answer).where(Answer.grounded.is_(False))
        )
        return {
            "avg_latency_ms": float(averages[0]) if averages[0] is not None else None,
            "avg_confidence": float(averages[1]) if averages[1] is not None else None,
            "ungrounded_answers": int(ungrounded or 0),
        }

    async def intent_counts(self) -> dict[str, int]:
        result = await self._session.execute(
            select(Query.intent, func.count())
            .where(Query.intent.is_not(None))
            .group_by(Query.intent)
            .order_by(func.count().desc())
        )
        return {intent: int(count) for intent, count in result.all()}

    async def retriever_counts(self) -> dict[str, int]:
        result = await self._session.execute(
            select(RetrievalLog.retriever, func.count())
            .group_by(RetrievalLog.retriever)
            .order_by(func.count().desc())
        )
        return {retriever: int(count) for retriever, count in result.all()}
