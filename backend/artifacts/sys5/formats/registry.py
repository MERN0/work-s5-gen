from __future__ import annotations

from artifacts.sys5.formats.base import FormatProfile
from artifacts.sys5.formats.default_profile import DEFAULT_FORMAT_PROFILE

_PROFILES: dict[str, FormatProfile] = {
    DEFAULT_FORMAT_PROFILE.name: DEFAULT_FORMAT_PROFILE,
}


def get_format_profile(name: str) -> FormatProfile:
    try:
        return _PROFILES[name]
    except KeyError:
        raise ValueError(
            f"Unknown format_profile '{name}'. Known profiles: {sorted(_PROFILES)}"
        ) from None
