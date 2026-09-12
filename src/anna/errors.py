class AnnaError(Exception):
    """An actionable error safe to display without a traceback."""


class ChallengeError(AnnaError):
    pass


class ParseError(AnnaError):
    pass
