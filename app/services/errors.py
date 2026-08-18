class WorkflowError(Exception):
    """Base class for workflow-level business failures."""


class EntityNotFoundError(WorkflowError):
    """A required business entity does not exist."""


class PermissionDeniedError(WorkflowError):
    """The actor is not permitted to perform the requested operation."""


class InvalidStateTransitionError(WorkflowError):
    """The aggregate is not in a state accepted by the operation."""


class TaskVersionConflictError(WorkflowError):
    """The command was based on an obsolete task version."""


class BusinessValidationError(WorkflowError):
    """Business facts supplied to an operation are invalid."""


class DependencyNotSatisfiedError(WorkflowError):
    """A task node cannot start because a predecessor is incomplete."""


class DependencyCycleError(WorkflowError):
    """The task node dependency graph contains a directed cycle."""
