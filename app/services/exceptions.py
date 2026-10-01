"""Domain exceptions (spec §14.11).

Views and APIs map these to HTTP status codes in one place.
"""


class PlmError(Exception):
    """Base class for all domain errors.

    ``field`` optionally names the form/model field the error belongs to so
    views can attach it to the relevant input (spec §14.11 field-level detail).
    """

    def __init__(self, message: str = "", field: str = None):
        super().__init__(message)
        self.field = field


class NotFoundError(PlmError):
    """A referenced entity does not exist."""


class ValidationError(PlmError):
    """A business rule or field validation failed."""


class ConflictError(PlmError):
    """A uniqueness or duplicate-edge conflict."""


class InvalidLifecycleTransitionError(PlmError):
    """The requested lifecycle transition is not allowed."""


class ReleasedVersionImmutableError(PlmError):
    """A released/baselined version cannot be modified."""


class BaselineFrozenError(PlmError):
    """A frozen baseline cannot be modified."""


class BaselineValidationError(PlmError):
    """A baseline member is invalid (e.g. not releasable)."""


class RelationshipCycleError(PlmError):
    """The relationship would create a cycle in a structural graph."""


class AuthorizationError(PlmError):
    """The actor is not permitted to perform the operation."""
