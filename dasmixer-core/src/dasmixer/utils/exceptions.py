"""DASMixer custom exceptions.

All project-specific exceptions inherit from :class:`DasmixerException`.
Subclass it (or raise it directly) instead of ``Exception`` so that callers
can catch DASMixer-specific errors without catching unrelated exceptions
(Ruff ``TRY002``).
"""


class DasmixerException(Exception):
    """Base exception for all DASMixer-specific errors."""