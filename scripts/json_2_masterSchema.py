#!/usr/bin/env python3
"""
json_2_masterSchema.py

Merges a list of sample JSON responses from an API into a single unified
Master JSON Schema (Draft-07 compatible) with sample value annotations
to help LLMs accurately understand API response structures.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _merge_types(t1: str | list[str] | None, t2: str | list[str] | None) -> str | list[str]:
    set1 = set(t1) if isinstance(t1, list) else ({t1} if t1 else set())
    set2 = set(t2) if isinstance(t2, list) else ({t2} if t2 else set())
    combined = set1 | set2
    if "number" in combined and "integer" in combined:
        combined.discard("integer")
    ordered = sorted(combined)
    return ordered[0] if len(ordered) == 1 else ordered


def _collect_examples(existing: list[Any], value: Any, max_examples: int = 3) -> list[Any]:
    if value is None or isinstance(value, (dict, list)):
        return existing
    if value not in existing and len(existing) < max_examples:
        return [*existing, value]
    return existing


def infer_schema(value: Any) -> dict[str, Any]:
    jtype = _json_type(value)

    if jtype == "object":
        properties: dict[str, Any] = {}
        for k, v in value.items():
            properties[k] = infer_schema(v)
        return {
            "type": "object",
            "properties": properties,
            "required": sorted(value.keys()),
            "_sample_count": 1,
        }

    if jtype == "array":
        if not value:
            return {"type": "array", "items": {}}
        item_schema = infer_schema(value[0])
        for item in value[1:]:
            item_schema = merge_schemas(item_schema, infer_schema(item))
        return {"type": "array", "items": item_schema}

    schema: dict[str, Any] = {"type": jtype}
    if value is not None:
        schema["examples"] = [value]
    return schema


def merge_schemas(s1: dict[str, Any], s2: dict[str, Any]) -> dict[str, Any]:
    if not s1:
        return dict(s2)
    if not s2:
        return dict(s1)

    t1 = s1.get("type")
    t2 = s2.get("type")
    merged_type = _merge_types(t1, t2)

    # Handle nullable / mixed object or array schemas
    if t1 == "object" and t2 == "null":
        out = dict(s1)
        out["type"] = merged_type
        return out
    if t2 == "object" and t1 == "null":
        out = dict(s2)
        out["type"] = merged_type
        return out
    if t1 == "array" and t2 == "null":
        out = dict(s1)
        out["type"] = merged_type
        return out
    if t2 == "array" and t1 == "null":
        out = dict(s2)
        out["type"] = merged_type
        return out

    if merged_type == "object":
        props1 = s1.get("properties", {})
        props2 = s2.get("properties", {})
        all_keys = sorted(set(props1.keys()) | set(props2.keys()))

        merged_props: dict[str, Any] = {}
        for k in all_keys:
            if k in props1 and k in props2:
                merged_props[k] = merge_schemas(props1[k], props2[k])
            elif k in props1:
                merged_props[k] = dict(props1[k])
            else:
                merged_props[k] = dict(props2[k])

        req1 = set(s1.get("required", []))
        req2 = set(s2.get("required", []))
        merged_req = sorted(req1 & req2)

        return {
            "type": "object",
            "properties": merged_props,
            "required": merged_req,
            "_sample_count": s1.get("_sample_count", 1) + s2.get("_sample_count", 1),
        }

    if merged_type == "array":
        items1 = s1.get("items", {})
        items2 = s2.get("items", {})
        return {
            "type": "array",
            "items": merge_schemas(items1, items2),
        }

    merged: dict[str, Any] = {"type": merged_type}
    examples = list(s1.get("examples", []))
    for ex in s2.get("examples", []):
        examples = _collect_examples(examples, ex)
    if examples:
        merged["examples"] = examples
    return merged


def _strip_internal_keys(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: _strip_internal_keys(v)
            for k, v in node.items()
            if not k.startswith("_")
        }
    if isinstance(node, list):
        return [_strip_internal_keys(item) for item in node]
    return node


def build_master_schema(
    samples: list[Any],
    title: str = "API Response Master Schema",
    description: str = "Auto-generated master JSON schema from sample API responses.",
) -> dict[str, Any]:
    if not isinstance(samples, list) or not samples:
        raise ValueError("Input must be a non-empty list of JSON response objects.")

    master = infer_schema(samples[0])
    for sample in samples[1:]:
        master = merge_schemas(master, infer_schema(sample))

    cleaned = _strip_internal_keys(master)
    return {
        "$schema": "http://json-schema.org",
        "title": title,
        "description": description,
        "sample_count": len(samples),
        **cleaned,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a master JSON Schema from a JSON array of API responses."
    )
    parser.add_argument(
        "input_file",
        help="Path to a JSON file containing a list [...] of API response objects.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output path for the master schema JSON (defaults to stdout).",
    )
    parser.add_argument(
        "--title",
        default="API Response Master Schema",
        help="Schema title metadata.",
    )
    args = parser.parse_args()

    in_path = Path(args.input_file)
    if not in_path.is_file():
        print(f"Error: Input file '{in_path}' not found.", file=sys.stderr)
        sys.exit(1)

    raw_data = json.loads(in_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raw_data = [raw_data]

    schema = build_master_schema(raw_data, title=args.title)
    formatted = json.dumps(schema, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(formatted + "\n", encoding="utf-8")
        print(f"Master schema written to {args.output}")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
