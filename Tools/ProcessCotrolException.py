import datetime


class ProcessControlException(Exception):
    """Base process exception."""
    def __init__(self, message: str, item=None):
        super().__init__(message)
        self.timestamp = datetime.datetime.now()
        self.item = item


# --------------------------------------------------------------------------------

class ProcessSkip(ProcessControlException):
    """Skip process. Commonly continue a loop."""
    def __init__(self, reason: str, item=None):
        super().__init__(f"SKIPPED: {reason}", item)
        self.reason = reason


class ProcessRetry(ProcessControlException):
    """Retry operation. Commonly continue and increase retry count."""
    def __init__(self, reason: str, max_attempts=3, item=None):
        super().__init__(f"RETRY REQUIRED: {reason}", item)
        self.reason = reason
        self.max_attempts = max_attempts


class ProcessPause(ProcessControlException):
    """Pause process. Skip except timeout exceed."""
    def __init__(self, reason: str, resume_after: datetime.timedelta, item=None):
        super().__init__(f"PAUSED: {reason}", item)
        self.resume_time = datetime.datetime.now() + resume_after


class ProcessIgnore(ProcessControlException):
    """Ignore. Just do nothing."""
    def __init__(self, reason: str, item=None):
        super().__init__(f"IGNORED: {reason}", item)
        self.reason = reason


class ProcessTerminate(ProcessControlException):
    """Have to stop process. Commonly break a loop."""
    def __init__(self, reason: str, exit_code=0, item=None):
        super().__init__(f"TERMINATED: {reason}", item)
        self.exit_code = exit_code


# --------------------------------------------------------------------------------

class ProcessProblem(ProcessControlException):
    """Use for processing a little problem. Switch problem a do thing for each problem case."""
    def __init__(self, problem: str, item=None):
        super().__init__(f"PROBLEM: {problem}", item)
        self.problem = problem

class ProcessWarning(ProcessControlException):
    """Can use for continue and log warning."""
    def __init__(self, message: str, item=None):
        super().__init__(f"WARNING: {message}", item)


class ProcessError(ProcessControlException):
    """Can use for break and log an error."""
    def __init__(self, error_text: str, item=None):
        super().__init__(f"ERROR: {error_text}", item)


class ProcessCritical(ProcessControlException):
    """Can use for quit and log an critical message."""
    def __init__(self, error_text: str, item=None):
        super().__init__(f"CRITICAL: {error_text}", item)


# --------------------------------------------------------------------------------

class ValidationException(ProcessControlException):
    def __init__(self, field: str, message: str, item=None):
        super().__init__(f"VALIDATION FAILURE: {field} - {message}", item)
        self.field = field


class MissingFieldError(ValidationException):
    def __init__(self, field: str, item=None):
        super().__init__(field, "Required field missing", item)


class InvalidTypeError(ValidationException):
    def __init__(self, field: str, expected_type: str, item=None):
        super().__init__(field, f"Expected type {expected_type}", item)
