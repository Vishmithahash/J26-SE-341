"""Strict recursive validator for structured JSON against response_schema.

Ensures LLM output adheres to declared types, properties, enums, required fields,
and bounds without accepting booleans as numbers or omitting required fields.
"""

from typing import Any


def validate_structured_schema(
    data: Any,
    schema: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    """Recursively validate python data structure against a JSON schema.

    Returns (True, None) if valid, or (False, error_description) if invalid.
    """
    if schema is None or not isinstance(schema, dict):
        return True, None

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(data, dict):
            return False, f"Expected object, got {type(data).__name__}"
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                return False, f"Missing required property '{field}'"
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name in data:
                valid, err = validate_structured_schema(data[prop_name], prop_schema)
                if not valid:
                    return False, f"Property '{prop_name}': {err}"
    elif expected_type == "array":
        if not isinstance(data, list):
            return False, f"Expected array, got {type(data).__name__}"
        item_schema = schema.get("items")
        if item_schema and isinstance(item_schema, dict):
            for idx, item in enumerate(data):
                valid, err = validate_structured_schema(item, item_schema)
                if not valid:
                    return False, f"Item [{idx}]: {err}"
    elif expected_type == "string":
        if not isinstance(data, str):
            return False, f"Expected string, got {type(data).__name__}"
        enum_vals = schema.get("enum")
        if enum_vals is not None and data not in enum_vals:
            return False, f"Value '{data}' is not in allowed enum {enum_vals}"
    elif expected_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            return False, f"Expected integer, got {type(data).__name__}"
        if "minimum" in schema and data < schema["minimum"]:
            return False, f"Value {data} is less than minimum {schema['minimum']}"
        if "maximum" in schema and data > schema["maximum"]:
            return False, f"Value {data} is greater than maximum {schema['maximum']}"
    elif expected_type == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            return False, f"Expected number, got {type(data).__name__}"
        if "minimum" in schema and data < schema["minimum"]:
            return False, f"Value {data} is less than minimum {schema['minimum']}"
        if "maximum" in schema and data > schema["maximum"]:
            return False, f"Value {data} is greater than maximum {schema['maximum']}"
    elif expected_type == "boolean":
        if not isinstance(data, bool):
            return False, f"Expected boolean, got {type(data).__name__}"

    if "enum" in schema and expected_type != "string" and data not in schema["enum"]:
        return False, f"Value '{data}' is not in allowed enum {schema['enum']}"

    return True, None
