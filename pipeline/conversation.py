"""
Conversation mode — asymmetric by default.

Your uncle says তুই to you. You say আপনি back. Both are correct, and neither is
the other's mirror. This is not an edge case; it is how most Indian
conversations across a generation gap actually work.

Every translation product on the market applies one register to a whole
session, which gets that exactly wrong in the most emotionally loaded case.
A :class:`Conversation` holds **two independent register settings, one per
direction**, so when the languages flip the register flips with them: the elder
speaks down, you speak up, and nobody touches a control (blueprint 13.2 #2).

It also carries the per-participant details the register layer needs and MT
cannot supply — the vocative slot Indian languages require, and the speaker
gender that Hindi, Marathi, Punjabi and Gujarati mark on the verb.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from register import (
    AUTO,
    CASUAL,
    coerce_level,
    detect as detect_register,
    has_table,
    level_name,
)

from .core import ExchangeResult, Phrasebook, translate_text

__all__ = ["Participant", "Turn", "RegisterShift", "Conversation"]


@dataclass
class Participant:
    """One side of a conversation."""

    name: str
    language: str
    #: The register this participant *speaks in*. AUTO mirrors what they say.
    register: object = AUTO
    #: How the other side should be addressed when speaking to them —
    #: "older_man", "elder_woman", "official"... Fills the vocative slot.
    addressee: Optional[str] = None
    #: This participant's own gender, for first-person verb agreement.
    gender: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "language": self.language,
            "register": self.register,
            "addressee": self.addressee,
            "gender": self.gender,
        }


@dataclass
class Turn:
    speaker: str
    text: str
    translated: str
    register_level: int
    detected_level: Optional[int]
    detected_confidence: float = 0.0
    at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "translated": self.translated,
            "register_level": self.register_level,
            "register_name": level_name(self.register_level),
            "detected_level": self.detected_level,
            "detected_name": (
                level_name(self.detected_level) if self.detected_level is not None else None
            ),
            "detected_confidence": round(self.detected_confidence, 3),
            "at": self.at,
        }


@dataclass(frozen=True)
class RegisterShift:
    """
    A participant changed how they address the other one, and it stuck.

    Register is not only a property of a sentence, it is a property of a
    relationship over time — and when it moves, something social has happened.
    Somebody who was saying তুমি and starts saying আপনি has put distance
    between you. The reverse is an invitation. Nobody surfaces this, because
    nobody tracks register per participant across a conversation.

    Two things this deliberately does not do.

    It does not fire on a single turn. Detection is not perfect, conversation
    is noisy, and a spurious "they have cooled towards you" is not a cosmetic
    bug — it is a false claim about somebody's feelings, told to the person
    those feelings are about. The bar is a sustained change backed by
    confident readings on both sides of it.

    And it does not interpret. "They moved to the polite form" is an
    observation; "they are annoyed with you" is a guess, and it is not the
    machine's guess to make. A speaker changes register for all sorts of
    reasons — a stranger walked in, the topic turned to work, they are being
    playful. The message states what changed and leaves the meaning to the
    person who is actually in the conversation.
    """

    speaker: str
    from_level: int
    to_level: int
    #: Index into ``Conversation.turns`` where the new register was confirmed.
    at_turn: int
    #: "warmer" when the register moved down the scale, "cooler" when up.
    direction: str
    #: The weakest reading the shift rests on.
    confidence: float

    @property
    def message(self) -> str:
        moved = "more familiar" if self.direction == "warmer" else "more formal"
        return (
            f"{self.speaker} has moved to the {moved} form "
            f"({level_name(self.from_level)} → {level_name(self.to_level)})."
        )

    def as_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "from_level": self.from_level,
            "from_name": level_name(self.from_level),
            "to_level": self.to_level,
            "to_name": level_name(self.to_level),
            "at_turn": self.at_turn,
            "direction": self.direction,
            "confidence": round(self.confidence, 3),
            "message": self.message,
        }


class Conversation:
    """
    A two-party conversation with a register setting per direction.

    ``a`` and ``b`` each carry the register *they speak in*. Saying something as
    ``a`` translates into ``b``'s language at ``a``'s register — so the two
    directions never have to agree, which is the whole point.
    """

    def __init__(
        self,
        a: Participant,
        b: Participant,
        *,
        phrasebook: Optional[Phrasebook] = None,
        conversation_id: Optional[str] = None,
    ):
        self.id = conversation_id or uuid.uuid4().hex[:12]
        self.a = a
        self.b = b
        self.turns: List[Turn] = []
        self._phrasebook = phrasebook

    # ------------------------------------------------------------------

    def participant(self, name: str) -> Participant:
        if name == self.a.name:
            return self.a
        if name == self.b.name:
            return self.b
        raise KeyError(
            f"{name!r} is not in this conversation "
            f"({self.a.name!r}, {self.b.name!r})"
        )

    def other(self, name: str) -> Participant:
        return self.b if name == self.a.name else self.a

    # ------------------------------------------------------------------

    def say(
        self,
        speaker_name: str,
        text: str,
        *,
        allow_network: bool = True,
        with_audio: bool = False,
    ) -> ExchangeResult:
        """
        One turn. Translates from the speaker's language into the listener's,
        at the *speaker's* register — not a session-wide one.
        """
        speaker = self.participant(speaker_name)
        listener = self.other(speaker_name)

        result = translate_text(
            text,
            target_lang=listener.language,
            source_lang=speaker.language,
            register_level=speaker.register,
            addressee=speaker.addressee,
            speaker_gender=speaker.gender,
            with_audio=with_audio,
            allow_network=allow_network,
            phrasebook=self._phrasebook,
        )

        self.turns.append(
            Turn(
                speaker=speaker.name,
                text=text,
                translated=result.translated_text,
                register_level=result.register_level,
                detected_level=result.detected_level,
                detected_confidence=result.detected_confidence,
            )
        )
        return result

    def observed_registers(self) -> Dict[str, Optional[int]]:
        """
        The register each participant has actually been using, read from their
        own turns rather than from what they configured.

        This is what makes the asymmetry visible: after a few turns you can show
        that one side is speaking Close and the other Polite, which is exactly
        the situation a single session-wide dial cannot represent.
        """
        out: Dict[str, Optional[int]] = {}
        for participant in (self.a, self.b):
            levels = [
                turn.detected_level
                for turn in self.turns
                if turn.speaker == participant.name and turn.detected_level is not None
            ]
            out[participant.name] = levels[-1] if levels else None
        return out

    def register_history(
        self, speaker_name: str, *, min_confidence: float = 0.5
    ) -> List[Tuple[int, int, float]]:
        """
        What one participant has been doing, turn by turn.

        ``(turn index, level, confidence)`` for their turns that carried a
        readable register. Turns with no second-person marker are skipped
        rather than counted as a change — silence about register is not a
        change of register, and treating it as one is how a shift detector
        starts inventing things.
        """
        self.participant(speaker_name)  # raises on an unknown name
        return [
            (index, turn.detected_level, turn.detected_confidence)
            for index, turn in enumerate(self.turns)
            if turn.speaker == speaker_name
            and turn.detected_level is not None
            and turn.detected_confidence >= min_confidence
        ]

    def shifts(
        self,
        speaker_name: Optional[str] = None,
        *,
        support: int = 2,
        min_confidence: float = 0.5,
    ) -> List[RegisterShift]:
        """
        Every sustained change of register, oldest first.

        ``support`` is how many consecutive confident turns at the new level
        it takes to believe it. Two by default, which is what makes this
        usable: one turn is noise, and somebody alternating between forms is
        not shifting, they are just varying. Both cases stay silent.
        """
        names = (
            [speaker_name] if speaker_name is not None else [self.a.name, self.b.name]
        )
        out: List[RegisterShift] = []
        for name in names:
            history = self.register_history(name, min_confidence=min_confidence)
            if len(history) < support + 1:
                continue

            baseline = history[0][1]
            run_level: Optional[int] = None
            run: List[Tuple[int, int, float]] = []
            for entry in history[1:]:
                _, level, _ = entry
                if level == baseline:
                    run_level, run = None, []
                    continue
                if level != run_level:
                    run_level, run = level, [entry]
                else:
                    run.append(entry)
                if len(run) >= support:
                    out.append(
                        RegisterShift(
                            speaker=name,
                            from_level=baseline,
                            to_level=level,
                            at_turn=run[-1][0],
                            direction="warmer" if level < baseline else "cooler",
                            # The weakest link, including the reading the shift
                            # moved away from — a shift is only as sure as the
                            # baseline it is measured against.
                            confidence=min(
                                [history[0][2]] + [conf for _, _, conf in run]
                            ),
                        )
                    )
                    baseline, run_level, run = level, None, []
        out.sort(key=lambda shift: shift.at_turn)
        return out

    def latest_shift(self, **kwargs) -> Optional[RegisterShift]:
        """The most recent sustained change, if there has been one."""
        found = self.shifts(**kwargs)
        return found[-1] if found else None

    def is_asymmetric(self) -> bool:
        """True when the two sides are speaking at different levels."""
        observed = self.observed_registers()
        levels = [lvl for lvl in observed.values() if lvl is not None]
        return len(levels) == 2 and levels[0] != levels[1]

    def mirror(self, speaker_name: str) -> None:
        """
        Set one participant's register from what they last actually said.

        Useful after a turn or two of Auto: freeze what the elder is doing so it
        stops re-detecting, while leaving your own side untouched.
        """
        speaker = self.participant(speaker_name)
        observed = self.observed_registers().get(speaker_name)
        if observed is not None:
            speaker.register = observed

    def as_dict(self) -> dict:
        observed = self.observed_registers()
        return {
            "id": self.id,
            "participants": {
                self.a.name: self.a.as_dict(),
                self.b.name: self.b.as_dict(),
            },
            "observed_registers": {
                name: (level_name(level) if level is not None else None)
                for name, level in observed.items()
            },
            "asymmetric": self.is_asymmetric(),
            "shifts": [shift.as_dict() for shift in self.shifts()],
            "turns": [turn.as_dict() for turn in self.turns],
        }
