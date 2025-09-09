"""
Status codes for operations throughout the application.
Using simple numeric constants for language-independent logic.
"""


class Status:
    """Status codes for all operations"""

    SUCCESS = 0
    FAILED = 1
    CANCELLED = 2
    IN_PROGRESS = 3
    NOT_INSTALLED = 4
    NETWORK_ERROR = 5
    TIMEOUT = 6
    PERMISSION_ERROR = 7
    INVALID_DATA = 8
    UNKNOWN = 9

    @classmethod
    def get_name(cls, code: int) -> str:
        """Get status name for debugging"""
        for name, value in cls.__dict__.items():
            if not name.startswith("_") and value == code:
                return name
        return "UNKNOWN"

    @classmethod
    def is_success(cls, code: int) -> bool:
        """Check if status code indicates success"""
        return code == cls.SUCCESS

    @classmethod
    def is_error(cls, code: int) -> bool:
        """Check if status code indicates an error"""
        return code in [
            cls.FAILED,
            cls.NETWORK_ERROR,
            cls.TIMEOUT,
            cls.PERMISSION_ERROR,
            cls.INVALID_DATA,
        ]
