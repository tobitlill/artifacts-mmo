#!/usr/bin/env python3

"""
Minimal Artifacts MMO API Client

Features:
- Bearer authentication
- JSON requests
- Retry handling
- Rate limit handling
- Cooldown handling
- Generic endpoint access

Usage:

from artifacts_client import ArtifactsClient

client = ArtifactsClient(
    token="YOUR_TOKEN"
)

me = client.get("/my/characters")
print(me)

"""

from __future__ import annotations

import time
import requests
from typing import Any, Dict, Optional


class ArtifactsAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        data: Any = None
    ):
        self.status_code = status_code
        self.message = message
        self.data = data

        super().__init__(
            f"[{status_code}] {message}"
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
        self.base_url = (
            base_url.rstrip("/")
            if base_url
            else self.BASE_URL
        )

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
        params: Dict[str, Any] | None = None
    ):
        return self.request(
            "GET",
            path,
            params=params
        )

    def post(
        self,
        path: str,
        json: Dict[str, Any] | None = None
    ):
        return self.request(
            "POST",
            path,
            json=json
        )

    def patch(
        self,
        path: str,
        json: Dict[str, Any] | None = None
    ):
        return self.request(
            "PATCH",
            path,
            json=json
        )

    def delete(
        self,
        path: str,
        json: Dict[str, Any] | None = None
    ):
        return self.request(
            "DELETE",
            path,
            json=json
        )

    # ---------------------------------------------------------
    # Core request handler
    # ---------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        **kwargs
    ):

        url = self.base_url + path
        retries = 0

        while True:

            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )

            try:
                data = response.json()
            except Exception:
                data = response.text


            # ---------------------------------------------
            # Success
            # ---------------------------------------------

            if response.ok or response.status_code == 499:

                self._handle_cooldown(data["data"])

                return data


            # ---------------------------------------------
            # Rate limit / temporary errors
            # ---------------------------------------------

            if response.status_code in (
                429,    # rate limit
                500,
                502,
                503,
                504,
            ):

                if retries >= self.max_retries:
                    raise ArtifactsAPIError(
                        response.status_code,
                        "Maximum retries exceeded",
                        data
                    )

                delay = self._retry_delay(
                    response,
                    retries
                )

                time.sleep(delay)

                retries += 1
                continue


            # ---------------------------------------------
            # API errors
            # ---------------------------------------------

            message = (
                data.get("message")
                if isinstance(data, dict)
                else str(data)
            )

            raise ArtifactsAPIError(
                response.status_code,
                message,
                data
            )


    # ---------------------------------------------------------
    # Cooldown handling
    # ---------------------------------------------------------

    def _handle_cooldown(
        self,
        data: Any
    ):
        if not isinstance(data, dict):
            return

        cooldown = data.get("cooldown")

        if not cooldown:
            return

        remaining = (
            cooldown.get("remaining_seconds")
            or cooldown.get("remaining")
        )

        if remaining:
            time.sleep(float(remaining))


    # ---------------------------------------------------------
    # Retry calculation
    # ---------------------------------------------------------

    def _retry_delay(
        self,
        response,
        retry_number
    ):

        retry_after = response.headers.get(
            "Retry-After"
        )

        if retry_after:
            return float(retry_after)

        # exponential backoff
        return min(
            2 ** retry_number,
            30
        )
