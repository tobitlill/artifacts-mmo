import pytest

from src.api_client import ArtifactsAPIError, ArtifactsClient, CharacterInCooldownError

from conftest import run_async


class FakeAiohttpResponse:
    def __init__(self, status, json_data=None, text_data=""):
        self.status = status
        self._json = json_data
        self._text = text_data
        self.headers = {}

    @property
    def ok(self):
        return 200 <= self.status < 400

    async def json(self, content_type=None):
        if self._json is None:
            raise ValueError("no json body")
        return self._json

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeAiohttpSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self._responses.pop(0)


def _client_with_responses(responses, **kwargs):
    client = ArtifactsClient(token="test", **kwargs)

    async def fake_ensure_session():
        return FakeAiohttpSession(responses)

    client._ensure_session = fake_ensure_session
    return client


def test_success_response_returns_data():
    client = _client_with_responses([FakeAiohttpResponse(200, json_data={"data": {"ok": True}})])
    result = run_async(client.get("/my/characters"))
    assert result == {"data": {"ok": True}}


def test_499_raises_cooldown_error_not_treated_as_success():
    """Regression test for the 490/499 mix-up: 499 is the real
    'character in cooldown' code and must never be swallowed as success."""
    client = _client_with_responses(
        [FakeAiohttpResponse(499, json_data={"error": {"message": "cooldown, 3.2 seconds remaining"}})]
    )
    with pytest.raises(CharacterInCooldownError) as exc_info:
        run_async(client.post("/my/tib0t/action/move", {"x": 1, "y": 1}))

    assert exc_info.value.character_name == "tib0t"
    assert exc_info.value.cooldown_seconds == 3


def test_490_raises_generic_api_error_not_cooldown_error():
    """490 is 'character already on map', not a cooldown - must not be
    misrouted into CharacterInCooldownError."""
    client = _client_with_responses(
        [FakeAiohttpResponse(490, json_data={"error": {"message": "already on map"}})]
    )
    with pytest.raises(ArtifactsAPIError) as exc_info:
        run_async(client.post("/my/tib0t/action/move", {"x": 0, "y": 0}))

    assert exc_info.value.status_code == 490


def test_429_retries_then_succeeds(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("src.api_client.asyncio.sleep", fake_sleep)

    client = _client_with_responses(
        [
            FakeAiohttpResponse(429, json_data={"error": {"message": "rate limited"}}),
            FakeAiohttpResponse(200, json_data={"data": {"ok": True}}),
        ]
    )
    result = run_async(client.get("/my/characters"))
    assert result == {"data": {"ok": True}}
    assert len(sleeps) == 1


def test_max_retries_exceeded_raises(monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("src.api_client.asyncio.sleep", fake_sleep)

    client = _client_with_responses(
        [FakeAiohttpResponse(500, json_data={"error": {"message": "server error"}}) for _ in range(3)],
        max_retries=2,
    )
    with pytest.raises(ArtifactsAPIError) as exc_info:
        run_async(client.get("/my/characters"))
    assert exc_info.value.status_code == 500


def test_character_name_extracted_from_path():
    assert ArtifactsClient._character_name_from_path("/my/tib0t/action/move") == "tib0t"
    assert ArtifactsClient._character_name_from_path("/my/characters") == "unknown"
