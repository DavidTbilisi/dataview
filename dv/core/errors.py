"""User-facing error type.

Anything raised as a DvError is rendered by the CLI entry point as a single
friendly line instead of a traceback. Internal bugs stay as ordinary
exceptions so they keep their traceback.
"""


class DvError(Exception):
    """An error caused by user input, not by a bug in dv."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
