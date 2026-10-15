from datetime import datetime, timedelta

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from jarvis.web.server import create_app  # noqa: E402

PORT = 8765
ORIGIN = {"origin": f"http://127.0.0.1:{PORT}"}


@pytest.fixture
def client(assistant):
    assistant.ctx.health = lambda: {"cpu": 10.0, "ram": 20.0, "phone": {"connected": True}}
    with TestClient(create_app(assistant, assistant.bus, PORT)) as test_client:
        yield test_client


def test_dashboard_and_assets_are_served(client):
    assert "J.A.R.V.I.S" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_status(client):
    data = client.get("/api/status").json()
    assert data["cpu"] == 10.0 and "version" in data


def test_websocket_command_round_trip(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        assert ws.receive_json()["type"] == "history"
        ws.send_json({"type": "command", "text": "what time is it"})

        replies = []
        while not any(e.get("sender") == "jarvis" for e in replies):
            replies.append(ws.receive_json())

        assert replies[0] == {**replies[0], "sender": "user", "text": "what time is it"}
        assert any(e.get("text", "").startswith("The time is") for e in replies)


def test_websocket_from_other_site_is_rejected(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()


def test_reminder_api(client, ctx):
    reminder = ctx.reminders.add("revise", datetime.now() + timedelta(hours=1))
    assert client.get("/api/reminders").json()[0]["task"] == "revise"

    assert client.post(f"/api/reminders/{reminder.id}/done", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post(f"/api/reminders/{reminder.id}/done", headers=ORIGIN).json() == {"ok": True}
    assert client.get("/api/reminders").json() == []
