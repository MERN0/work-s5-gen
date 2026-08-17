"""Typed exceptions for the swe6 pipeline. See the plan's error-handling table:
config/LLM-client construction failures and a missing/corrupt requirements file
are meant to fail loudly and immediately; everything else degrades gracefully
and is only ever logged.
"""


class Swe6Error(Exception):
    """Base class for all swe6 pipeline errors."""


class Swe6ConfigError(Swe6Error):
    """The raw config dict passed to generate() could not be turned into a valid Swe6Config."""


class RequirementsFileError(Swe6Error):
    """The SWE.1 software requirements file or the requested sheet could not be read."""


class LlmClientError(Swe6Error):
    """The LLM client could not be constructed (bad key/base_url/model)."""
