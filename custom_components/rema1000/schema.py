"""Schema library: Home Assistant moved from voluptuous to probatio (same API)."""

try:
    import probatio as vol
except ImportError:  # pragma: no cover - Home Assistant before the move to probatio
    import voluptuous as vol  # type: ignore[no-redef]

__all__ = ["vol"]
