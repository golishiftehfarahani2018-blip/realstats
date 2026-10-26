"""Ports for future integrations. No success simulation or live calls in phase 1."""

from typing import Protocol


class SmsProvider(Protocol):
    def send(self, phone: str, message: str, *, idempotency_key: str) -> str: ...


class MapProvider(Protocol):
    def geocode(self, address: str) -> tuple[float, float]: ...


class MediaStore(Protocol):
    def put(
        self, key: str, content: bytes, content_type: str, *, private: bool
    ) -> None: ...
