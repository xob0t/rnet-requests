"""
wrequests.impersonate
~~~~~~~~~~~~~~~~~~~~~~~~~

Browser impersonation (emulation) types and utilities, compatible with curl_cffi.

This module adapts wreq's Profile, Platform, and Emulation types to the
curl_cffi-compatible names exposed by wrequests.
"""

import re
from enum import StrEnum
from typing import Literal

from wreq import Emulation as WreqEmulation
from wreq import Platform as WreqPlatform
from wreq import Profile as WreqProfile

# Re-export wreq's classes under the names used by earlier rnet releases.
Emulation = WreqEmulation
EmulationOS = WreqPlatform
EmulationOption = WreqEmulation

# Aliases for backward compatibility with rnet v2 naming
Impersonate = WreqEmulation
ImpersonateOS = WreqPlatform
ImpersonateOption = WreqEmulation


def _get_latest_versions() -> dict[str, tuple[str, WreqProfile]]:
    """
    Dynamically determine the latest version for each browser family
    by inspecting wreq's Profile enum.

    Returns a dict mapping browser family name to (enum_name, Emulation value).
    """
    # Get all enum member names
    all_names = [name for name in dir(WreqProfile) if not name.startswith("_")]

    # Browser family patterns - match family name and extract version number
    families = {
        "chrome": re.compile(r"^Chrome(\d+)$"),
        "firefox": re.compile(r"^Firefox(\d+)$"),
        "safari": re.compile(r"^Safari(\d+(?:_\d+(?:_\d+)?)?)$"),
        "edge": re.compile(r"^Edge(\d+)$"),
        "opera": re.compile(r"^Opera(\d+)$"),
        "okhttp": re.compile(r"^OkHttp(\d+(?:_\d+)?)$"),
    }

    latest: dict[str, tuple[str, str, WreqProfile]] = {}

    for name in all_names:
        for family, pattern in families.items():
            match = pattern.match(name)
            if match:
                version_str = match.group(1)
                # Convert version string to comparable tuple (e.g., "18_5" -> (18, 5))
                version_parts = tuple(int(p) for p in version_str.split("_"))

                if family not in latest:
                    latest[family] = (version_str, name, getattr(WreqProfile, name))
                else:
                    # Compare versions
                    existing_version = tuple(
                        int(p) for p in latest[family][0].split("_")
                    )
                    if version_parts > existing_version:
                        latest[family] = (
                            version_str,
                            name,
                            getattr(WreqProfile, name),
                        )
                break

    return {family: (name, imp) for family, (_, name, imp) in latest.items()}


def _build_emulation_map() -> dict[str, WreqProfile]:
    """
    Build a mapping from string names to Emulation enum values.

    This includes:
    - All specific versions (e.g., "chrome137", "firefox139")
    - Generic family names pointing to latest (e.g., "chrome" -> Chrome137)
    """
    result: dict[str, WreqProfile] = {}

    # Get latest versions for generic names
    latest_versions = _get_latest_versions()

    # Add generic family names pointing to latest
    for family, (_, imp) in latest_versions.items():
        result[family] = imp

    # Add all specific versions from the enum
    all_names = [name for name in dir(WreqProfile) if not name.startswith("_")]

    for name in all_names:
        # Convert CamelCase to lowercase (e.g., "Chrome137" -> "chrome137")
        key = name.lower()
        # Handle underscores in Safari versions (e.g., "Safari18_5" -> "safari18_5")
        result[key] = getattr(WreqProfile, name)

    return result


# Build the emulation map dynamically
EMULATION_MAP: dict[str, WreqProfile] = _build_emulation_map()

# Alias for backward compatibility
IMPERSONATE_MAP = EMULATION_MAP

# Get latest versions for defaults (returns dict of family -> (name, Emulation))
_LATEST_VERSIONS = _get_latest_versions()

# Default browser versions (dynamically determined)
DEFAULT_CHROME = _LATEST_VERSIONS.get("chrome", (None, None))[1]
DEFAULT_FIREFOX = _LATEST_VERSIONS.get("firefox", (None, None))[1]
DEFAULT_SAFARI = _LATEST_VERSIONS.get("safari", (None, None))[1]
DEFAULT_EDGE = _LATEST_VERSIONS.get("edge", (None, None))[1]
DEFAULT_OPERA = _LATEST_VERSIONS.get("opera", (None, None))[1]
DEFAULT_OKHTTP = _LATEST_VERSIONS.get("okhttp", (None, None))[1]


# OS type literals for type hints
OSTypeLiteral = Literal[
    "windows",
    "macos",
    "linux",
    "android",
    "ios",
]

# Map from string to EmulationOS
OS_MAP: dict[str, WreqPlatform] = {
    "windows": WreqPlatform.Windows,
    "win": WreqPlatform.Windows,
    "macos": WreqPlatform.MacOS,
    "mac": WreqPlatform.MacOS,
    "osx": WreqPlatform.MacOS,
    "linux": WreqPlatform.Linux,
    "android": WreqPlatform.Android,
    "ios": WreqPlatform.IOS,
    "iphone": WreqPlatform.IOS,
    "ipad": WreqPlatform.IOS,
}


# Browser type literals for type hints (matching curl_cffi)
# Note: This is a static type hint, actual values are dynamic
BrowserTypeLiteral = Literal[
    # Generic (latest)
    "chrome",
    "firefox",
    "safari",
    "edge",
    "opera",
    "okhttp",
    # Specific versions (examples - actual list is dynamic)
    "chrome100",
    "chrome137",
    "firefox135",
    "firefox139",
    "safari18",
    "safari18_5",
    "edge134",
    "opera119",
    "okhttp5",
]


class BrowserType(StrEnum):
    """Browser type enum for impersonation/emulation.

    This enum provides a curl_cffi-compatible interface for browser impersonation.
    Use generic names like 'chrome' or 'firefox' to get the latest version.
    """

    # Generic (latest version)
    chrome = "chrome"
    firefox = "firefox"
    safari = "safari"
    edge = "edge"
    opera = "opera"
    okhttp = "okhttp"


class OSType(StrEnum):
    """OS type enum for impersonation/emulation."""

    windows = "windows"
    macos = "macos"
    linux = "linux"
    android = "android"
    ios = "ios"


# Real target map (aliases to actual versions) - built dynamically
REAL_TARGET_MAP: dict[str, str] = {
    family: name.lower() for family, (name, _) in _LATEST_VERSIONS.items()
}


def normalize_browser_type(item: str) -> str:
    """Normalize browser type string to canonical form."""
    item_lower = item.lower().replace("-", "").replace("_", "")
    return REAL_TARGET_MAP.get(item_lower, item_lower)


def resolve_os(
    os: str | OSType | WreqPlatform | None,
) -> WreqPlatform | None:
    """Resolve an OS value to wreq's Platform enum.

    Args:
        os: OS to emulate. Can be a string like 'windows', 'macos', 'linux',
            'android', 'ios', an OSType enum, or a wreq Platform value.

    Returns:
        The resolved EmulationOS value, or None if os is None.

    Raises:
        ValueError: If the OS value is not recognized.
    """
    if os is None:
        return None

    if isinstance(os, WreqPlatform):
        return os

    if isinstance(os, OSType):
        key = os.value.lower()
    elif isinstance(os, str):
        key = os.lower().replace("-", "").replace("_", "")
    else:
        raise ValueError(f"Invalid OS type: {type(os)}")

    if key in OS_MAP:
        return OS_MAP[key]

    valid_options = list(OS_MAP.keys())
    raise ValueError(f"Unknown OS value: {os}. Valid options: {valid_options}")


def resolve_emulation(
    emulation: str | BrowserType | WreqProfile | WreqEmulation | None,
) -> WreqProfile | WreqEmulation | None:
    """Resolve an emulation value to a wreq Profile or Emulation.

    Args:
        emulation: Browser to emulate. Can be a string like 'chrome',
            a BrowserType enum, or a wreq Profile or Emulation value.

    Returns:
        The resolved Emulation value, or None if emulation is None.

    Raises:
        ValueError: If the emulation value is not recognized.
    """
    if emulation is None:
        return None

    if isinstance(emulation, (WreqProfile, WreqEmulation)):
        return emulation

    if isinstance(emulation, BrowserType):
        key = emulation.value.lower()
    elif isinstance(emulation, str):
        # Normalize: lowercase, convert dashes to underscores (preserve underscores)
        key = emulation.lower().replace("-", "_")
    else:
        raise ValueError(f"Invalid emulation type: {type(emulation)}")

    # Try exact match first
    if key in EMULATION_MAP:
        return EMULATION_MAP[key]

    # Try without underscores (for inputs like "chrome130" matching "chrome130")
    key_no_underscore = key.replace("_", "")
    if key_no_underscore in EMULATION_MAP:
        return EMULATION_MAP[key_no_underscore]

    # Try partial match
    for name, imp in EMULATION_MAP.items():
        if key in name or name in key:
            return imp
        # Also try without underscores
        if key_no_underscore in name or name in key_no_underscore:
            return imp

    valid_options = list(EMULATION_MAP.keys())
    raise ValueError(
        f"Unknown emulation value: {emulation}. Valid options: {valid_options}"
    )


# Alias for backward compatibility
resolve_impersonate = resolve_emulation


def create_emulation_option(
    emulation: str | BrowserType | WreqProfile | WreqEmulation | None = None,
    os: str | OSType | WreqPlatform | None = None,
    skip_http2: bool | None = None,
    skip_headers: bool | None = None,
) -> WreqEmulation | WreqProfile | None:
    """Create an EmulationOption with browser and OS settings.

    Args:
        emulation: Browser to emulate (e.g., 'chrome', 'firefox').
        os: OS to emulate (e.g., 'windows', 'macos', 'linux').
        skip_http2: Skip HTTP/2 settings emulation.
        skip_headers: Skip header order emulation.

    Returns:
        An EmulationOption if OS or other options are specified,
        just the Emulation enum if only browser is specified,
        or None if nothing is specified.
    """
    resolved_emulation = resolve_emulation(emulation)

    if resolved_emulation is None:
        return None

    resolved_os = resolve_os(os)

    # A complete wreq Emulation already contains its platform and feature flags.
    if isinstance(resolved_emulation, WreqEmulation):
        return resolved_emulation

    # If we have additional options, create EmulationOption
    if resolved_os is not None or skip_http2 is not None or skip_headers is not None:
        return WreqEmulation(
            profile=resolved_emulation,
            platform=resolved_os or WreqPlatform.MacOS,
            http2=not bool(skip_http2),
            headers=not bool(skip_headers),
        )

    # Otherwise just return the emulation enum
    return resolved_emulation
