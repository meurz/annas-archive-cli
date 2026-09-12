class AnnaError(Exception):
    """An actionable error safe to display without a traceback."""

    code = "operation_failed"


class ChallengeError(AnnaError):
    code = "browser_verification_required"


class ParseError(AnnaError):
    code = "unrecognized_page"


class InvalidInputError(AnnaError):
    code = "invalid_input"


class IntegrityError(AnnaError):
    code = "integrity_error"


class FileExistsError(AnnaError):
    code = "file_exists"


class RateLimitError(AnnaError):
    code = "rate_limited"


class HTTPStatusError(AnnaError):
    code = "http_error"
