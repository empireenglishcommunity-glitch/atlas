"""Understanding tests — a fake LLM client, no network, no key."""
from __future__ import annotations

import json

import pytest

from src.atlas.understand import interpret, Understanding, UNASSIGNED

DOMAINS = [
    ("empire", "Empire / English"),
    ("trading", "Trading"),
    ("gym", "Gym / fitness"),
    ("deen", "Deen / worship"),
]


class FakeLLM:
    """Returns whatever string it's told to — simulates a Groq reply."""
    def __init__(self, reply="", raise_it=False):
        self.reply = reply
        self.raise_it = raise_it
        self.last_user = None

    def complete(self, system, user):
        self.last_user = user
        if self.raise_it:
            raise RuntimeError("groq down")
        return self.reply


def _json(**kw):
    base = {"type": "task", "title": "x", "domain": "empire", "size": "medium",
            "due": None, "trigger": None, "confidence": 0.9, "clarify": None}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def test_task_routed_to_domain():
    llm = FakeLLM(_json(type="task", title="record the B2 lesson",
                        domain="empire", size="deep", confidence=0.9))
    u = interpret("sagel el lesson bta3et B2", DOMAINS, llm)
    assert u.type == "task"
    assert u.domain == "empire"
    assert u.size == "deep"
    assert not u.needs_clarification
    assert "B2 lesson" in u.title


def test_idea_and_journal_types_preserved():
    llm = FakeLLM(_json(type="idea", title="a hook for a reel", domain="macal",
                        size=None, confidence=0.8))
    u = interpret("فكرة لريل", DOMAINS, llm)
    # 'macal' isn't in DOMAINS here → unassigned, but an IDEA doesn't force a clarify
    assert u.type == "idea"
    assert u.domain == UNASSIGNED
    assert not u.needs_clarification


def test_low_confidence_forces_a_question():
    llm = FakeLLM(_json(type="task", title="do the thing", domain="empire",
                        confidence=0.3, clarify=None))
    u = interpret("اعمل الحاجة", DOMAINS, llm)
    assert u.needs_clarification
    assert u.confirmation_line().startswith("❓")


def test_unassigned_task_forces_a_question():
    llm = FakeLLM(_json(type="task", title="call the guy", domain="nope",
                        confidence=0.9, clarify=None))
    u = interpret("kallem el raagel", DOMAINS, llm)
    assert u.domain == UNASSIGNED
    assert u.needs_clarification


def test_llm_provided_clarify_is_respected():
    llm = FakeLLM(_json(type="task", title="x", domain="empire",
                        confidence=0.9, clarify="أنهي فيديو بالظبط؟"))
    u = interpret("انزل الفيديو", DOMAINS, llm)
    assert u.clarify == "أنهي فيديو بالظبط؟"


def test_code_fenced_json_is_parsed():
    llm = FakeLLM("```json\n" + _json(title="leg day", domain="gym", size="medium") + "\n```")
    u = interpret("gym leg day", DOMAINS, llm)
    assert u.domain == "gym"
    assert u.title == "leg day"


def test_prose_around_json_is_tolerated():
    llm = FakeLLM("Sure! Here you go:\n" + _json(title="pray", domain="deen") + "\nHope that helps")
    u = interpret("صلي الضهر", DOMAINS, llm)
    assert u.domain == "deen"


def test_invalid_type_falls_back_to_idea_not_fake_task():
    llm = FakeLLM(_json(type="banana", title="whatever", domain="empire"))
    u = interpret("something", DOMAINS, llm)
    assert u.type == "idea"  # never fabricate a task


def test_llm_failure_is_graceful_and_keeps_raw():
    llm = FakeLLM(raise_it=True)
    u = interpret("حاجة مهمة", DOMAINS, llm)
    assert u.needs_clarification            # asks rather than guessing
    assert u.raw == "حاجة مهمة"             # original retained for retry (R2.7)
    assert u.confidence == 0.0


def test_unparseable_reply_is_graceful():
    llm = FakeLLM("I couldn't do that")
    u = interpret("x", DOMAINS, llm)
    assert u.needs_clarification


def test_empty_text_asks():
    llm = FakeLLM(_json())
    u = interpret("   ", DOMAINS, llm)
    assert u.needs_clarification
    assert llm.last_user is None  # never even called the LLM on empty input


def test_domain_list_is_passed_to_the_model():
    llm = FakeLLM(_json())
    interpret("test", DOMAINS, llm, names=["Mai", "MACAL"])
    assert "empire" in llm.last_user
    assert "Mai" in llm.last_user          # known names given for meaning-correction


def test_confirmation_line_uses_domain_label():
    u = Understanding(type="task", title="record lesson", domain="empire",
                      size="deep", confidence=0.9)
    line = u.confirmation_line(domain_label="Empire / English")
    assert "record lesson" in line
    assert "Empire / English" in line
    assert line.startswith("✅")
