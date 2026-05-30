"""
gemini_parser.parse_cooking_steps 예외 처리 테스트 (이슈 #5).

핵심: Gemini 호출/파싱 실패를 []로 삼키면 '정상적으로 0건'과 구분되지 않아
recipe가 COMPLETED로 캐싱·오염된다. 실패는 GeminiParseError로 raise하고,
'정상적으로 빈 리스트'인 경우만 []를 반환하는지 검증한다.

실제 Gemini API를 호출하지 않도록 모듈 전역 client를 가짜로 교체한다.
(DB도, 네트워크도, 실제 키도 필요 없음)
"""

import json
import os
from types import SimpleNamespace

# 모듈 로드 시 genai.Client(api_key=...)가 생성되므로, import 전에 더미 키를 채운다.
os.environ.setdefault("GEMINI_API_KEY", "test-key-for-import")

import pytest

from api import gemini_parser
from api.gemini_parser import GeminiParseError, parse_cooking_steps


class _FakeModels:
    """client.models 대체: generate_content 호출 시 주어진 동작을 실행한다."""

    def __init__(self, behavior):
        self._behavior = behavior

    def generate_content(self, *args, **kwargs):
        return self._behavior()


class _FakeClient:
    def __init__(self, behavior):
        self.models = _FakeModels(behavior)


def _set_client(monkeypatch, behavior):
    """gemini_parser.client를 가짜로 교체. behavior()는 응답을 반환하거나 예외를 던진다."""
    monkeypatch.setattr(gemini_parser, "client", _FakeClient(behavior))


def test_api_error_raises(monkeypatch):
    """Gemini 호출 자체가 실패하면(키 만료·할당량 등) GeminiParseError로 전파된다."""
    def boom():
        raise RuntimeError("API key expired")

    _set_client(monkeypatch, boom)
    with pytest.raises(GeminiParseError):
        parse_cooking_steps("자막")


def test_invalid_json_raises(monkeypatch):
    """Gemini가 JSON이 아닌 응답을 주면 GeminiParseError로 전파된다."""
    _set_client(monkeypatch, lambda: SimpleNamespace(text="이건 JSON이 아니다"))
    with pytest.raises(GeminiParseError):
        parse_cooking_steps("자막")


def test_non_list_json_raises(monkeypatch):
    """Gemini가 리스트가 아닌 JSON(객체)을 주면 GeminiParseError로 전파된다."""
    _set_client(monkeypatch, lambda: SimpleNamespace(text='{"action": "감자 썰기"}'))
    with pytest.raises(GeminiParseError):
        parse_cooking_steps("자막")


def test_empty_list_returned(monkeypatch):
    """정상적으로 빈 배열이면 예외가 아니라 []를 반환한다 (진짜 0건 → COMPLETED 캐싱 대상)."""
    _set_client(monkeypatch, lambda: SimpleNamespace(text="[]"))
    assert parse_cooking_steps("자막") == []


def test_valid_steps_returned(monkeypatch):
    """정상 응답은 파싱된 리스트를 그대로 반환한다."""
    payload = [
        {"action": "감자 썰기", "start_time": "00:10", "end_time": "00:30", "gesture": "썰기"},
    ]
    _set_client(monkeypatch, lambda: SimpleNamespace(text=json.dumps(payload)))
    assert parse_cooking_steps("자막") == payload
