import pytest
from fastapi import HTTPException
from google.genai import types

import analytics
import llm


class FakeAPIError(Exception):
    def __init__(self, code):
        super().__init__(f"error {code}")
        self.code = code


def text_response(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text=text)]))])


def call_response(name, args, call_id="call-1"):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(
            function_call=types.FunctionCall(id=call_id, name=name, args=args))]))])


def scripted(*responses):
    """A fake `generate` that returns the given responses in order and
    records the conversation it was sent each time."""
    seen = []
    queue = list(responses)

    def generate(contents):
        seen.append(list(contents))
        return queue.pop(0)

    generate.seen = seen
    return generate


# --- retry ------------------------------------------------------------
def test_retry_recovers_from_temporary_errors():
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise FakeAPIError(503)
        return "ok"

    sleeps = []
    result, retries = llm.call_with_retry(flaky, sleep=sleeps.append)
    assert (result, retries) == ("ok", 2)
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]  # backoff grows


def test_retry_fails_fast_on_permanent_errors():
    calls = {"n": 0}

    def bad_key():
        calls["n"] += 1
        raise FakeAPIError(403)

    with pytest.raises(HTTPException) as e:
        llm.call_with_retry(bad_key, sleep=lambda s: None)
    assert e.value.status_code == 502 and calls["n"] == 1


def test_retry_gives_up_after_max_attempts():
    calls = {"n": 0}

    def always_busy():
        calls["n"] += 1
        raise FakeAPIError(429)

    with pytest.raises(HTTPException):
        llm.call_with_retry(always_busy, sleep=lambda s: None)
    assert calls["n"] == llm.MAX_ATTEMPTS


# --- function-calling loop -----------------------------------------------
def test_model_calls_a_function_then_answers(df):
    gen = scripted(
        call_response("get_top_n", {"dimension": "region", "n": 1}),
        text_response("Ljubljana led with EUR 35,000."),
    )
    out = llm.answer_question("Which region is best?", df, gen, sleep=lambda s: None)

    assert out["answer"] == "Ljubljana led with EUR 35,000."
    assert out["llm_calls"] == 2
    assert out["tool_calls"][0]["name"] == "get_top_n"
    assert out["tool_calls"][0]["result"][0]["region"] == "Ljubljana"

    # The 2nd request carries question, the model's call, and our response.
    second = gen.seen[1]
    assert [c.role for c in second] == ["user", "model", "user"]
    fr = second[2].parts[0].function_response
    assert fr.name == "get_top_n" and fr.id == "call-1"


def test_no_raw_rows_ever_reach_the_model(df):
    gen = scripted(call_response("get_summary", {}), text_response("done"))
    llm.answer_question("q", df, gen, sleep=lambda s: None)
    sent = repr(gen.seen[1]) + llm.build_system_prompt(df)
    assert "Widget B" in sent          # names of values are fine...
    assert "12500" not in sent         # ...individual sale rows are not
    assert "340" not in sent


def test_answer_without_tools_is_returned_directly(df):
    gen = scripted(text_response("I can't forecast."))
    out = llm.answer_question("next year?", df, gen)
    assert out["tool_calls"] == [] and out["llm_calls"] == 1


def test_bad_tool_call_is_reported_back_to_the_model(df):
    gen = scripted(call_response("get_totals_by", {"group_by": "nonsense"}), text_response("Sorry."))
    out = llm.answer_question("q", df, gen, sleep=lambda s: None)
    assert "error" in out["tool_calls"][0]["result"]


def test_runaway_tool_loop_is_stopped(df):
    gen = scripted(*[call_response("get_summary", {}) for _ in range(llm.MAX_TOOL_ROUNDS + 1)])
    with pytest.raises(HTTPException) as e:
        llm.answer_question("q", df, gen, sleep=lambda s: None)
    assert e.value.status_code == 502


def test_declarations_match_the_tool_registry():
    declared = {d.name for d in llm.DECLARATIONS}
    assert declared == set(analytics.TOOLS)
