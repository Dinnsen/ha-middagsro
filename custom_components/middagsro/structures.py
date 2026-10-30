"""The shape of what the AI answers, for AI Task's structured output.

Home Assistant turns a schema into the model's response schema, so the
answer is JSON with these keys and types rather than a best effort. Home
Assistant moved from voluptuous to probatio for this during 2026, and the
two share an API; the library AI Task itself uses is the one the schema
must be built with.
"""

from __future__ import annotations

import inspect
from typing import Any

PLAN_TYPES = ["normal", "vegetar", "rester", "fast"]


def schema_library() -> Any:
    """The schema library Home Assistant's AI Task takes its structure in."""
    try:
        from homeassistant.components.ai_task import task as task_module  # noqa: PLC0415

        annotation = str(
            inspect.signature(task_module.async_generate_data).parameters["structure"].annotation
        )
    except (ImportError, AttributeError, KeyError, ValueError):
        annotation = ""
    if "probatio" in annotation:
        try:
            import probatio  # noqa: PLC0415
        except ImportError:  # pragma: no cover - the library AI Task names is installed
            pass
        else:
            return probatio
    import voluptuous  # noqa: PLC0415

    return voluptuous


def plan_structure(lib: Any) -> Any:
    """A meal plan's overview: the days and the shopping list."""
    day = {
        lib.Required("date"): str,
        lib.Required("dish"): str,
        lib.Required("type"): lib.In(PLAN_TYPES),
        lib.Optional("favorite_id"): lib.Any(str, None),
        lib.Optional("uses_leftovers_from"): lib.Any(str, None),
        lib.Required("makes_leftovers"): bool,
        lib.Required("servings"): int,
        lib.Required("active_minutes"): int,
        lib.Required("total_minutes"): int,
        lib.Required("uses"): [str],
        lib.Optional("mealie"): lib.Any(str, None),
        lib.Optional("recipe_id"): lib.Any(str, None),
    }
    line = {
        lib.Required("name"): str,
        lib.Required("amount"): lib.Any(int, float),
        lib.Required("unit"): str,
        lib.Required("search"): str,
        lib.Required("category"): str,
        lib.Optional("offer"): lib.Any(str, None),
        # The catalogue entry the AI says the item is (ingredients.py), or None.
        lib.Optional("key"): lib.Any(str, None),
    }
    return lib.Schema(
        {
            lib.Required("title"): str,
            lib.Required("summary"): str,
            lib.Required("days"): [day],
            lib.Required("shopping"): [line],
            lib.Optional("checklist"): [
                {lib.Required("requirement"): str, lib.Required("ok"): bool}
            ],
            lib.Optional("deviations"): str,
        }
    )


def recipe_structure(lib: Any) -> Any:
    """One dinner's recipe."""
    return lib.Schema(
        {
            lib.Required("ingredients"): [{lib.Required("name"): str, lib.Required("amount"): str}],
            lib.Required("steps"): [{lib.Required("text"): str, lib.Required("minutes"): int}],
            lib.Optional("tip"): str,
            lib.Optional("active_minutes"): int,
            lib.Optional("total_minutes"): int,
            lib.Optional("nutrition"): {
                lib.Optional("kcal"): lib.Any(int, float),
                lib.Optional("protein_g"): lib.Any(int, float),
                lib.Optional("carbs_g"): lib.Any(int, float),
                lib.Optional("fat_g"): lib.Any(int, float),
                lib.Optional("fiber_g"): lib.Any(int, float),
            },
        }
    )


def choices_structure(lib: Any) -> Any:
    """Which product each uncertain line gets (or none): line id -> product id."""
    return lib.Schema(
        {
            lib.Required("choices"): [
                {lib.Required("line"): str, lib.Required("product"): lib.Any(int, None)}
            ]
        }
    )
