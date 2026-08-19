"""
Register shift detection.

Register is a property of a relationship over time, not only of a sentence.
Someone who was saying তুমি and starts saying আপনি has put distance between
you; the reverse is an invitation. No translator surfaces this, because none
of them track register per participant across a conversation.

Most of these tests are about *not* firing. A false "they have cooled towards
you" is not a cosmetic bug — it is a false claim about somebody's feelings,
delivered to the person those feelings are about. The detector has to be
harder to convince than it is to satisfy, so the silence cases are the ones
worth defending.
"""

from __future__ import annotations

import pytest

from pipeline import Conversation, Participant
from register import CASUAL, POLITE

CASUAL_BN = "তুমি কেমন আছ?"
POLITE_BN = "আপনি কেমন আছেন?"
NO_MARKER_BN = "আজ আবহাওয়া ভালো।"


def _conversation(*lines: str) -> Conversation:
    convo = Conversation(Participant("Priya", "bn"), Participant("You", "en"))
    for text in lines:
        convo.say("Priya", text, allow_network=False)
    return convo


# ------------------------------------------------------------------ it fires


def test_a_sustained_move_to_the_polite_form_is_reported():
    convo = _conversation(CASUAL_BN, CASUAL_BN, POLITE_BN, POLITE_BN)
    shift = convo.latest_shift()
    assert shift is not None
    assert (shift.from_level, shift.to_level) == (CASUAL, POLITE)
    assert shift.direction == "cooler"
    assert shift.speaker == "Priya"


def test_a_sustained_move_the_other_way_is_reported_too():
    convo = _conversation(POLITE_BN, POLITE_BN, CASUAL_BN, CASUAL_BN)
    shift = convo.latest_shift()
    assert shift is not None
    assert shift.direction == "warmer"


def test_a_conversation_can_shift_more_than_once_and_keeps_the_order():
    convo = _conversation(
        CASUAL_BN, POLITE_BN, POLITE_BN, CASUAL_BN, CASUAL_BN
    )
    shifts = convo.shifts()
    assert [s.direction for s in shifts] == ["cooler", "warmer"]
    assert shifts[0].at_turn < shifts[1].at_turn


# ---------------------------------------------------------------- it is quiet


def test_one_odd_turn_is_not_a_shift():
    """The single most important case. One turn is noise."""
    convo = _conversation(CASUAL_BN, CASUAL_BN, POLITE_BN, CASUAL_BN)
    assert convo.shifts() == []


def test_alternating_between_forms_is_not_a_shift():
    """Somebody varying their speech has not changed how they regard you."""
    convo = _conversation(CASUAL_BN, POLITE_BN, CASUAL_BN, POLITE_BN)
    assert convo.shifts() == []


def test_turns_with_no_register_marker_are_skipped_not_counted():
    """
    Silence about register is not a change of register. Counting an unreadable
    turn as a change is how a detector like this starts inventing things.
    """
    convo = _conversation(CASUAL_BN, NO_MARKER_BN, NO_MARKER_BN, CASUAL_BN)
    assert [level for _, level, _ in convo.register_history("Priya")] == [CASUAL, CASUAL]
    assert convo.shifts() == []


def test_a_short_conversation_says_nothing():
    assert _conversation(CASUAL_BN, POLITE_BN).shifts() == []


def test_low_confidence_readings_do_not_carry_a_claim():
    convo = _conversation(CASUAL_BN, CASUAL_BN, POLITE_BN, POLITE_BN)
    assert convo.shifts(min_confidence=0.99) == []


# ------------------------------------------------------------------- the rest


def test_the_message_describes_and_does_not_interpret():
    """
    "They moved to the polite form" is an observation. "They are annoyed with
    you" is a guess, and not the machine's to make — a speaker changes register
    because a stranger walked in, or the topic turned to work, or they are
    being playful.
    """
    shift = _conversation(CASUAL_BN, CASUAL_BN, POLITE_BN, POLITE_BN).latest_shift()
    assert "more formal" in shift.message
    for guess in ("annoyed", "upset", "angry", "offended", "unhappy", "rude"):
        assert guess not in shift.message.lower()


def test_confidence_is_the_weakest_link():
    convo = _conversation(CASUAL_BN, CASUAL_BN, POLITE_BN, POLITE_BN)
    shift = convo.latest_shift()
    readings = [conf for _, _, conf in convo.register_history("Priya")]
    assert shift.confidence == pytest.approx(min(readings))


def test_shifts_ride_along_in_the_serialised_conversation():
    convo = _conversation(CASUAL_BN, CASUAL_BN, POLITE_BN, POLITE_BN)
    payload = convo.as_dict()
    assert len(payload["shifts"]) == 1
    assert payload["shifts"][0]["direction"] == "cooler"
    assert payload["turns"][0]["detected_confidence"] > 0


def test_history_rejects_a_name_that_is_not_in_the_conversation():
    with pytest.raises(KeyError):
        _conversation(CASUAL_BN).register_history("Nobody")
