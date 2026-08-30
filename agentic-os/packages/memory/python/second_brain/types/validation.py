"""Validation utilities for Phase 1 domain constraints."""


def validate_confidence(value: float | None, field_name: str = "confidence") -> float | None:
    """Validate a confidence value is in [0, 1]."""
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number, got {type(value).__name__}")
    if value < 0 or value > 1:
        raise ValueError(f"{field_name} must be between 0 and 1, got {value}")
    return value


def validate_importance(value: float | None, field_name: str = "importance") -> float | None:
    """Validate importance is in [0, 1]."""
    return validate_confidence(value, field_name)


def validate_strength(value: float | None, field_name: str = "strength") -> float | None:
    """Validate evidence strength is in [0, 1]."""
    return validate_confidence(value, field_name)


def validate_not_blank(value: str, field_name: str = "value") -> str:
    """Validate a string is non-empty and not only whitespace."""
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-blank string")
    return value


def validate_claim_type(value: str | None) -> str | None:
    """Validate claim_type is a valid MemoryClaimType value or None."""
    if value is None:
        return None
    valid = {
        "fact", "inference", "opinion", "decision", "hypothesis",
    }
    if value not in valid:
        raise ValueError(
            f"claim_type must be one of {sorted(valid)}, got '{value}'"
        )
    return value


def validate_enum_value(value: str, valid_values: set[str], field_name: str) -> str:
    """Validate a value is in the allowed enum set."""
    if value is None:
        return None
    if value not in valid_values:
        raise ValueError(
            f"{field_name} must be one of {sorted(valid_values)}, got '{value}'"
        )
    return value


def normalize_alias(alias: str) -> str:
    """Normalize an alias for future matching: trim, lowercase, collapse whitespace."""
    if not alias or not isinstance(alias, str):
        return ""
    # Trim, lowercase, collapse repeated whitespace
    parts = alias.strip().lower().split()
    return " ".join(parts)


def validate_parent_id(parent_id: int | None, self_id: int | None = None) -> int | None:
    """Validate parent_id: cannot self-reference; cannot be negative."""
    if parent_id is None:
        return None
    if not isinstance(parent_id, int) or parent_id <= 0:
        raise ValueError(f"parent_id must be a positive integer, got {parent_id}")
    if self_id is not None and parent_id == self_id:
        raise ValueError("parent_id cannot reference the area's own id (self-reference)")
    return parent_id
