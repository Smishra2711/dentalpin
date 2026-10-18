"""Regression: the root .env must not break the local backend import.

`.env` does triple duty: docker compose interpolates it, Nuxt reads NUXT_*
from it, and `app/config.py` loads it through pydantic-settings, which
defaults to ``extra="forbid"``. So the keys the other two consumers need
made ``import app.config`` raise ``extra_forbidden`` — and `.env.example`
itself ships four of them (POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD /
API_BASE_URL), so the documented `cp .env.example .env` + run-the-backend-locally
path failed on a clean checkout.

These tests pin both halves: the coexistence that must work, and the strictness
that must NOT be given up to achieve it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import MIN_SECRET_KEY_LENGTH, Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_ENV = REPO_ROOT / ".env.example"

REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://dental:pw@localhost:5432/dental_clinic",
    "SECRET_KEY": "a" * MIN_SECRET_KEY_LENGTH,
    "ENVIRONMENT": "development",
}

# The keys .env.example writes that this model does not declare.
COMPOSE_ONLY = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "API_BASE_URL")


@pytest.fixture(autouse=True)
def _env_file_is_the_only_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """Process env outranks the env file in pydantic-settings.

    Without this, a developer (or CI) that already exports DATABASE_URL and
    SECRET_KEY would satisfy every required field from the environment and
    these tests would pass without ever exercising the env-file path they exist
    to cover - including the required-field test, which would then not raise.
    """
    for key in (*REQUIRED, *COMPOSE_ONLY, "NUXT_PUBLIC_COPILOT_ENABLED", "TESTING"):
        monkeypatch.delenv(key, raising=False)


def write_env(tmp_path: Path, extra_lines: list[str]) -> Path:
    body = [f"{k}={v}" for k, v in REQUIRED.items()]
    body += extra_lines
    path = tmp_path / ".env"
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def test_compose_and_nuxt_keys_alongside_app_settings_are_tolerated(tmp_path: Path) -> None:
    path = write_env(
        tmp_path,
        [
            "POSTGRES_DB=dental_clinic",
            "POSTGRES_USER=dental",
            "POSTGRES_PASSWORD=secret",
            "API_BASE_URL=http://localhost:8000",
            "NUXT_PUBLIC_COPILOT_ENABLED=true",
        ],
    )
    settings = Settings(_env_file=str(path))  # type: ignore[call-arg]
    assert settings.DATABASE_URL.endswith("/dental_clinic")
    assert settings.ENVIRONMENT == "development"


def test_the_shipped_env_example_would_not_have_crashed(tmp_path: Path) -> None:
    """The strongest form of the regression: the template users are told to copy."""
    if not EXAMPLE_ENV.exists():
        pytest.skip(".env.example not present")
    text = EXAMPLE_ENV.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    ]
    # Substitute the placeholders the template ships with.
    body = []
    for line in lines:
        key, _, value = line.partition("=")
        if value.strip() in {"", "your_secret_key_here_use_openssl_rand_hex_32"}:
            value = "a" * MIN_SECRET_KEY_LENGTH if "SECRET" in key or key == "SECRET_KEY" else value
        if key == "SECRET_KEY":
            value = "a" * MIN_SECRET_KEY_LENGTH
        if key == "DATABASE_URL":
            value = REQUIRED["DATABASE_URL"]
        if key == "ENVIRONMENT":
            value = "development"
        body.append(f"{key}={value}")
    path = tmp_path / "from-example.env"
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    Settings(_env_file=str(path))  # type: ignore[call-arg]


def test_required_fields_are_still_required(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("POSTGRES_DB=dental_clinic\nAPI_BASE_URL=http://x\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings(_env_file=str(path))  # type: ignore[call-arg]


def test_ignoring_extras_did_not_relax_the_production_secret_key_check() -> None:
    # The strictness that matters for security must be untouched by extra="ignore".
    with pytest.raises(ValueError, match="SECRET_KEY must be at least"):
        Settings(
            **{
                "DATABASE_URL": REQUIRED["DATABASE_URL"],
                "SECRET_KEY": "a" * (MIN_SECRET_KEY_LENGTH - 1),
                "ENVIRONMENT": "production",
                "POSTGRES_DB": "dental_clinic",  # an extra, and must be irrelevant
            }
        )


def test_every_compose_only_key_is_actually_absent_from_the_model() -> None:
    # Guards the premise of the test above: if someone later declares one of
    # these as a field, the coexistence test is no longer proving anything.
    fields = set(Settings.model_fields)
    for key in COMPOSE_ONLY:
        assert key not in fields, f"{key} is now a Settings field; revisit extra='ignore'"
