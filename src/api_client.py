#!/usr/bin/env python3

"""
Minimal Artifacts MMO API Client

Features:
- Bearer authentication
- JSON requests
- Retry handling
- Rate limit handling
- Per-character cooldown handling
- Generic endpoint access
"""

from __future__ import annotations

import logging
import time
import requests
from datetime import datetime, timezone
from typing import Any, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ArtifactsAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        data: Any = None,
    ):
        self.status_code = status_code
        self.message = message
        self.data = data

        super().__init__(f"[{status_code}] {message}")


class CharacterInCooldownError(Exception):
    def __init__(
        self,
        character_name: str,
        cooldown_seconds: int,
    ):
        self.character_name = character_name
        self.cooldown_seconds = cooldown_seconds

        super().__init__(
            f"Character {character_name} is on cooldown for {cooldown_seconds} seconds"
        )


class ArtifactsClient:

    BASE_URL = "https://api.artifactsmmo.com"

    def __init__(
        self,
        token: str,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 5,
    ):
        self.base_url = base_url.rstrip("/") if base_url else self.BASE_URL

        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "artifacts-python-client/1.0",
            }
        )

    # ---------------------------------------------------------
    # Public HTTP methods
    # ---------------------------------------------------------

    def get(
        self,
        path: str,
        params: Dict[str, Any] | None = None,
    ):
        return self.request(
            "GET",
            path,
            params=params,
        )

    def post(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return self.request(
            "POST",
            path,
            json=json,
        )

    def patch(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return self.request(
            "PATCH",
            path,
            json=json,
        )

    def delete(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return self.request(
            "DELETE",
            path,
            json=json,
        )

    # ---------------------------------------------------------
    # Core request handler
    # ---------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        **kwargs,
    ):
        logger.debug(f"{method} {path} with params {kwargs.get('params', {})}")

        url = self.base_url + path
        retries = 0

        while True:

            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs,
            )

            try:
                data = response.json()
            except Exception:
                data = response.text

            # ---------------------------------------------
            # Success
            # ---------------------------------------------

            if response.ok or response.status_code == 499:
                return data

            # ---------------------------------------------
            # Rate limit / temporary errors
            # ---------------------------------------------

            if response.status_code in (
                429,
                500,
                502,
                503,
                504,
            ):

                if retries >= self.max_retries:
                    raise ArtifactsAPIError(
                        response.status_code,
                        "Maximum retries exceeded",
                        data,
                    )

                delay = self._retry_delay(
                    response,
                    retries,
                )

                time.sleep(delay)

                retries += 1
                continue

            # ---------------------------------------------
            # API errors
            # ---------------------------------------------

            message = (
                data.get("error", {}).get("message")
                if isinstance(data, dict)
                else str(data)
            )

            if response.status_code == 490:
                cooldown_seconds = self._extract_cooldown_seconds(data)
                if cooldown_seconds is not None and cooldown_seconds > 0:
                    raise CharacterInCooldownError(
                        kwargs.get("character_name") or "unknown",
                        cooldown_seconds,
                    )

            raise ArtifactsAPIError(
                response.status_code,
                message,
                data,
            )

    # ---------------------------------------------------------
    # Retry calculation
    # ---------------------------------------------------------

    def _extract_cooldown_seconds(self, payload: Any) -> int | None:
        if not isinstance(payload, dict):
            return None

        data = payload.get("data")
        if not isinstance(data, dict):
            return None

        cooldown = data.get("cooldown")
        if not isinstance(cooldown, dict):
            return None

        remaining_seconds = cooldown.get("remaining_seconds")
        if isinstance(remaining_seconds, (int, float)):
            return int(remaining_seconds)
        if isinstance(remaining_seconds, str):
            try:
                return int(remaining_seconds)
            except ValueError:
                return None

        expiration = cooldown.get("expiration")
        if isinstance(expiration, str):
            try:
                expiration_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                return max(0, int((expiration_dt - now_dt).total_seconds()))
            except ValueError:
                return None

        return None

    def _retry_delay(
        self,
        response,
        retry_number,
    ):

        retry_after = response.headers.get("Retry-After")

        if retry_after:
            return float(retry_after)

        # exponential backoff
        return min(
            2**retry_number,
            30,
        )
