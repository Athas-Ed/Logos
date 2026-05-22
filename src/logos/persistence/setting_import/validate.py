"""JSON Schema 校验（``schema.json``）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator


class PipelineValidationError(ValueError):
    """导入批次 JSON 未通过 schema。"""


def validate_import_batch(batch: dict[str, Any], schema_path: Path) -> None:
    if not schema_path.is_file():
        msg = f"schema not found: {schema_path}"
        raise FileNotFoundError(msg)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(batch), key=lambda e: e.path)
    if not errors:
        return
    first = errors[0]
    path = "/".join(str(p) for p in first.absolute_path) or "(root)"
    raise PipelineValidationError(f"{path}: {first.message}")
