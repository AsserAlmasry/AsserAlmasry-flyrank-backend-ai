"""Talking to the model: an explicit timeout and a retry policy WE chose (the SDK's own retries are switched off)."""
import email.utils
import os
import random
import time

import httpx
from openai import (APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI,
                    PermissionDeniedError)

MAX_ATTEMPTS = 3          # 1 try + 2 retries
BASE_BACKOFF_S = 1.0      # 1 s, 2 s, 4 s ... plus jitter
MAX_RETRY_AFTER_S = 20.0  # never sleep longer than this inside an HTTP request, whatever the server says


class LLMTimeout(Exception):
    """The model took longer than LLM_TIMEOUT_S (after retries) -> 504."""


class LLMUnavailable(Exception):
    """Provider rate limit / outage that retries did not fix -> 503."""


class LLMConfigError(Exception):
    """Bad key, no permission, wrong model id: retrying cannot help -> 502, fail fast."""


def timeout_s() -> float:
    return float(os.getenv("LLM_TIMEOUT_S", "30"))


def make_client(http_client: httpx.Client | None = None) -> OpenAI:
    # The SDK defaults are a 10-minute timeout and 2 silent retries: both wrong for an HTTP endpoint.
    return OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"],
                  timeout=timeout_s(), max_retries=0, http_client=http_client)


def model_name() -> str:
    return os.environ["LLM_MODEL"]


def retry_after_seconds(exc: APIStatusError) -> float | None:
    """Retry-After comes in two formats: seconds ("7") or an HTTP date. Handle both."""
    value = exc.response.headers.get("retry-after") if exc.response is not None else None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        parsed = email.utils.parsedate_to_datetime(value)
        return max(0.0, parsed.timestamp() - time.time()) if parsed else None


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False  # 400, 401, 403, 404, 422...: the same request will fail the same way


def complete(client: OpenAI, messages: list[dict]) -> tuple[object, int]:
    """One logical model call. Returns (response, attempts_used). Raises LLMTimeout / LLMUnavailable / LLMConfigError."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            res = client.chat.completions.create(model=model_name(), messages=messages, temperature=0)
            return res, attempt
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise LLMConfigError(f"provider rejected the credentials ({exc.status_code}); check LLM_API_KEY") from exc
        except Exception as exc:
            if not is_retryable(exc):
                if isinstance(exc, APIStatusError):
                    raise LLMConfigError(f"provider returned {exc.status_code}: {exc.message}") from exc
                raise
            if attempt == MAX_ATTEMPTS:
                if isinstance(exc, APITimeoutError):
                    raise LLMTimeout(f"model did not answer within {timeout_s():.0f}s ({attempt} attempts)") from exc
                raise LLMUnavailable(f"provider unavailable after {attempt} attempts: {exc}") from exc
            wait = BASE_BACKOFF_S * 2 ** (attempt - 1) + random.uniform(0, 0.5)  # backoff + jitter
            if isinstance(exc, APIStatusError) and (ra := retry_after_seconds(exc)) is not None:
                wait = ra  # the server said exactly how long: obey it instead of guessing
                if wait > MAX_RETRY_AFTER_S:
                    raise LLMUnavailable(f"provider asked us to wait {wait:.0f}s; not holding the request that long") from exc
            time.sleep(wait)
    raise AssertionError("unreachable")
