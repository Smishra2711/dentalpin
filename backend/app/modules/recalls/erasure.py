"""GDPR erasure contributor for the recalls module (#546).

Owns the ``recalls`` coverage scope: clears this module's own copies of
the erased contacts (contact-attempt notes) and reports its own
:class:`~app.core.erasure.types.ErasureCoverage`. Registered via
``RecallsModule.get_erasure_contributors``; pulled by ``gdpr`` inside the
erasure transaction (ADR 0038).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erasure.types import ErasureContributor, ErasureCoverage

from .models import Recall, RecallContactAttempt

#: Contact-attempt channels (``RecallContactAttempt.channel``) mapped to the
#: GDPR erasure category that blanks the contact the note may carry. Cleared
#: per-channel so an email-only erasure never discards a phone-attempt note
#: (and vice versa), matching the notifications contributor (#546).
_ERASURE_CHANNEL_CATEGORY: dict[str, str] = {
    "email": "email",
    "phone": "phone",
    "whatsapp": "phone",
    "sms": "phone",
}


class RecallsErasureContributor(ErasureContributor):
    """Clear a patient's contact-attempt notes on a GDPR erasure."""

    @property
    def scope(self) -> str:
        return "recalls"

    async def erase(
        self,
        clinic_id: UUID,
        patient_id: UUID,
        erased: list[str],
        retained: list[str],
        db: AsyncSession,
    ) -> ErasureCoverage:
        """Clear contact-attempt notes whose channel matches an erased category.

        Runs inside the erasure's transaction, so the audit log and this
        redaction commit or roll back together. Only the free-text ``note``
        of an attempt whose channel matches an erased contact category is
        cleared — it records what was dialled and can carry the erased
        contact. The recall itself and its clinical ``reason_note`` are
        retained: a recall is treatment history, not a contact copy.
        """
        erased_set = set(erased)
        categories = {"email", "phone"} & erased_set
        if categories:
            channels = [
                channel
                for channel, category in _ERASURE_CHANNEL_CATEGORY.items()
                if category in categories
            ]

            recall_ids = select(Recall.id).where(
                Recall.patient_id == patient_id,
                Recall.clinic_id == clinic_id,
            )
            attempts = (
                (
                    await db.execute(
                        select(RecallContactAttempt).where(
                            RecallContactAttempt.clinic_id == clinic_id,
                            RecallContactAttempt.recall_id.in_(recall_ids),
                            RecallContactAttempt.channel.in_(channels),
                            RecallContactAttempt.note.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for attempt in attempts:
                attempt.note = None

        # Same three-state semantics as the notifications scope: scrubbed
        # only when a contact category was actually erasable.
        status: Literal["erased", "retained", "not_applicable"]
        if {"email", "phone"} & erased_set:
            status = "erased"
        elif {"email", "phone"} & set(retained):
            status = "retained"
        else:
            status = "not_applicable"
        return ErasureCoverage(
            scope=self.scope,
            status=status,
            detail="Contact-attempt notes on the patient's recalls.",
        )
