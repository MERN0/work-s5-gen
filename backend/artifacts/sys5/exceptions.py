"""Typed exceptions for the sys5 pipeline. See the plan's error-handling table:
config/LLM-client construction failures and a missing/corrupt requirements file
are meant to fail loudly and immediately; everything else degrades gracefully
and is only ever logged.
"""


class Sys5Error(Exception):
    """Base class for all sys5 pipeline errors."""


class Sys5ConfigError(Sys5Error):
    """The raw config dict passed to generate() could not be turned into a valid Sys5Config."""


class RequirementsFileError(Sys5Error):
    """The SYS2 requirements file or the requested sheet could not be read."""


class LlmClientError(Sys5Error):
    """The LLM client could not be constructed (bad key/base_url/model)."""
