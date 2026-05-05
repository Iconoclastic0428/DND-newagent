from __future__ import annotations


_JSON_VALIDITY_HARDENING = (
    'Think carefully internally before emitting the final answer, but do not reveal reasoning. '
    'Before finalizing, mentally run a strict JSON parser check against your reply. '
    'The final answer will be parsed by deterministic code and reviewed by a separate GPT verifier; malformed, wrapped, or extra text is a failed answer. '
    'Do not emit wrapper keys such as json, response, data, result, or output unless the required template explicitly contains that key. '
    'Do not emit XML/HTML tags, <think> blocks, YAML, comments, leading labels, byte-order marks, zero-width characters, ellipses, Python literals such as None/True/False, NaN, Infinity, single-quoted strings, unescaped control characters, or trailing commas. '
)


def build_json_object_contract(*, template: str) -> str:
    return (
        'Return strictly valid JSON only. '
        'Return exactly one JSON object and nothing else. '
        'The first non-whitespace character of your reply must be `{` and the last non-whitespace character must be `}`. '
        'DO NOT emit markdown fences. '
        'DO NOT emit ```json, ```JSON, or ``` anywhere in the reply. '
        'DO NOT emit commentary, prose, headings, bullets, reasoning, or any text before or after the JSON object. '
        'Use only standard JSON with double-quoted keys and strings, and do not use trailing commas. '
        + _JSON_VALIDITY_HARDENING
        + f'Use this exact JSON template shape: {template}'
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
        + _JSON_VALIDITY_HARDENING
        + f'Attempt number: {attempt_number}. '
        f'Use this exact JSON template shape: {template}'
    )
