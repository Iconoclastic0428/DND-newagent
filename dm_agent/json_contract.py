from __future__ import annotations


def build_json_object_contract(*, template: str) -> str:
    return (
        'Return strictly valid JSON only. '
        'Return exactly one JSON object and nothing else. '
        'The first non-whitespace character of your reply must be `{` and the last non-whitespace character must be `}`. '
        'DO NOT emit markdown fences. '
        'DO NOT emit ```json, ```JSON, or ``` anywhere in the reply. '
        'DO NOT emit commentary, prose, headings, bullets, reasoning, or any text before or after the JSON object. '
        'Use only standard JSON with double-quoted keys and strings, and do not use trailing commas. '
        f'Use this exact JSON template shape: {template}'
    )


def build_json_retry_contract(*, template: str, attempt_number: int) -> str:
    return (
        'Your previous reply failed deterministic validation. '
        'Fix the exact error below and retry now. '
        'Re-emit exactly one valid JSON object that matches the required schema exactly. '
        'The first non-whitespace character of your reply must be `{` and the last non-whitespace character must be `}`. '
        'Do not emit markdown fences. '
        'Do not emit ```json, ```JSON, or ``` anywhere in the reply. '
        'Do not emit commentary, prose, headings, bullets, reasoning, or any text before or after the JSON object. '
        'Use only standard JSON with double-quoted keys and strings, and do not use trailing commas. '
        f'Attempt number: {attempt_number}. '
        f'Use this exact JSON template shape: {template}'
    )
