from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse
import os

from rules_engine.env import load_env


class LLMConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    api_key: str = field(repr=False)
    base_url: str
    responses_model: str

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise LLMConfigError('OPENAI_API_KEY is required.')
        if not self.responses_model.strip():
            raise LLMConfigError('OPENAI_RESPONSES_MODEL is required.')
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {'http', 'https'}:
            raise LLMConfigError('OPENAI_BASE_URL must be an http(s) URL.')
        if not parsed.netloc:
            raise LLMConfigError('OPENAI_BASE_URL must include a host.')

    @classmethod
    def from_sources(
        cls,
        *,
        env_path: str | Path = '.env',
        environ: Mapping[str, str] | None = None,
    ) -> 'LLMConfig':
        file_env = load_env(env_path)
        merged = dict(file_env)
        merged.update(os.environ)
        if environ is not None:
            merged.update(environ)
        return cls(
            api_key=merged.get('OPENAI_API_KEY', '').strip(),
            base_url=merged.get('OPENAI_BASE_URL', '').strip(),
            responses_model=merged.get('OPENAI_RESPONSES_MODEL', '').strip(),
        )

    def redacted(self) -> dict[str, str]:
        return {
            'OPENAI_API_KEY': '***',
            'OPENAI_BASE_URL': self.base_url,
            'OPENAI_RESPONSES_MODEL': self.responses_model,
        }


def load_llm_config(*, env_path: str | Path = '.env', environ: Mapping[str, str] | None = None) -> LLMConfig:
    return LLMConfig.from_sources(env_path=env_path, environ=environ)


def validate_llm_example(*, env_example_path: str | Path) -> dict[str, str]:
    values = load_env(env_example_path)
    required = {'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_RESPONSES_MODEL'}
    missing = sorted(required - values.keys())
    if missing:
        raise LLMConfigError(f'.env.example is missing required placeholder keys: {", ".join(missing)}.')
    api_key = values['OPENAI_API_KEY'].strip()
    if not api_key or 'replace' not in api_key.lower() and 'your' not in api_key.lower():
        raise LLMConfigError('OPENAI_API_KEY placeholder must remain a non-secret example value.')
    return values
