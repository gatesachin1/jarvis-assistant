"""Routes study questions to the existing Study Assistant prompt (unchanged)."""

from __future__ import annotations

from jarvis.core.registry import command


@command(
    "study mode",
    r"(?:start )?study mode",
    r"help me (?:to )?study",
    priority=30,
    examples=["help me study"],
)
def study_mode(ctx, req):
    return (
        "Study mode ready. Start your question with 'study', for example: "
        "'study explain normalization in DBMS' or 'study 5 mark answer on CNN'."
    )


@command(
    "study question",
    r"(?:study|teach me|help me (?:to )?study|explain to me)[:,]?\s+(?P<q>.+)",
    priority=30,
    atomic=True,
    examples=["study what is a binary search tree"],
)
def study_question(ctx, req):
    if ctx.llm is None:
        return "The study assistant needs the local AI model."
    return ctx.llm.study(req["q"])
