"""End-to-end routing: text in -> correct action on the fake phone/laptop."""

from datetime import datetime


def test_time_and_date_work(run):
    # v1 crashed here because `from datetime import datetime` shadowed the module.
    assert run("what time is it")[0].startswith("The time is")
    assert run("what is today's date")[0].startswith(f"Today is {datetime.now():%A}")


def test_open_known_app_prefers_phone_when_connected(run, ctx):
    assert run("open instagram") == ["Opening instagram on your phone."]
    assert ("launch", "com.instagram.android") in ctx.adb.calls


def test_open_falls_back_to_laptop_when_phone_missing(run, ctx):
    ctx.adb.connected = False
    assert run("open youtube") == ["Opening youtube on your laptop."]
    assert ctx.extras["urls"] == ["https://www.youtube.com"]


def test_explicit_targets(run, ctx):
    run("open youtube on my laptop")
    assert ctx.extras["urls"] == ["https://www.youtube.com"]
    run("open notepad")
    assert ctx.extras["launched"] == [["notepad.exe"]]


def test_open_discovers_installed_app(run, ctx):
    assert run("open notesapp on my phone") == ["Opening notesapp on your phone."]
    assert ("launch", "com.example.notesapp") in ctx.adb.calls


def test_unknown_app_without_phone_goes_to_llm(run, ctx):
    ctx.adb.connected = False
    assert run("start a conversation about space") == ["LLM: start a conversation about space"]


def test_youtube_on_phone_and_laptop(run, ctx):
    run("play lofi beats")
    assert ctx.adb.calls[-1][0] == "view" and "lofi+beats" in ctx.adb.calls[-1][1]

    ctx.adb.connected = False
    run("search youtube for dbms")
    assert ctx.extras["urls"][-1].endswith("search_query=dbms")


def test_spotify_uses_deep_link(run, ctx):
    run("play believer on spotify")
    assert ctx.adb.calls[-1] == ("view", "https://open.spotify.com/search/believer", "com.spotify.music")


def test_media_controls(run, ctx):
    assert run("pause") == ["Paused on your phone."]
    run("volume up")
    assert ctx.adb.calls.count(("key", "KEYCODE_VOLUME_UP")) == 3

    ctx.adb.connected = False
    run("next song")
    assert ctx.media_keys.pressed == [("next", 1)]


def test_multi_task_chain(run, ctx):
    replies = run("open instagram and then search youtube for cats")
    assert len(replies) == 2
    assert ctx.adb.calls[0] == ("launch", "com.instagram.android")


def test_whatsapp_draft_keeps_message_case_and_never_splits(run, ctx):
    run("draft a whatsapp message to 91 98765 43210 saying Reach by 6 and then call me")
    _, url, package = ctx.adb.calls[-1]
    assert package == "com.whatsapp"
    assert url == "https://wa.me/919876543210?text=Reach%20by%206%20and%20then%20call%20me"


def test_call_number_and_contact(run, ctx):
    run("call 98765 43210")
    assert ctx.adb.calls[-1] == ("dial", "9876543210")

    assert run("call mom") == ["Dialer opened for Mom (+919876543210). Review and tap Call."]

    reply = run("call rahul")[0]
    assert "several contacts" in reply and "Rahul Verma" in reply


def test_reminder_flow(run, ctx):
    assert run("remind me to submit assignment in 30 minutes")[0].startswith("Reminder set: submit assignment")
    assert "1. submit assignment" in run("show my reminders")[0]
    assert run("mark reminder 1 done") == ["Marked 'submit assignment' as done."]
    assert run("show reminders") == ["You have no pending reminders."]


def test_study_routes_to_study_prompt(run, ctx):
    assert run("study what is normalization") == ["STUDY: what is normalization"]


def test_general_questions_go_to_llm(run, ctx):
    assert run("tell me a joke") == ["LLM: tell me a joke"]


def test_google_search_does_not_split_on_and(run, ctx):
    run("search for salt and pepper")
    assert ctx.extras["urls"] == ["https://www.google.com/search?q=salt+and+pepper"]


def test_help_lists_examples(run):
    assert "open instagram on my phone" in run("what can you do")[0]
