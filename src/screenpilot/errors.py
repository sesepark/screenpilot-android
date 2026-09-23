class ScreenPilotError(Exception):
    """Base error shown to CLI users without a traceback."""


class ConfigError(ScreenPilotError):
    """Invalid workflow configuration."""


class AdbError(ScreenPilotError):
    """ADB command or device error."""


class MatchTimeout(ScreenPilotError):
    """A required visual element was not found before its timeout."""
