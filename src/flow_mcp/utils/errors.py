"""Custom exception hierarchy for flow-mcp."""

class FlowMCPError(Exception):
    """Base exception for all flow-mcp errors."""
    pass

class ResourceNotFoundError(FlowMCPError):
    """Raised when a requested resource (job, project, worker, asset) does not exist."""
    pass

class InsufficientCreditsError(FlowMCPError):
    """Raised when an account or cluster has insufficient credits for a task."""
    pass

class WorkerNotFoundError(FlowMCPError):
    """Raised when a specific worker is not found in the pool."""
    pass

class WorkerUnavailableError(FlowMCPError):
    """Raised when no worker is currently available to accept tasks."""
    pass

class JobExecutionError(FlowMCPError):
    """Raised when a job fails during execution."""
    pass

class AssetNotFoundError(ResourceNotFoundError):
    """Raised when a referenced asset file does not exist in AssetHub."""
    pass

class ProjectNotFoundError(ResourceNotFoundError):
    """Raised when a project alias cannot be resolved."""
    pass

class BrowserOperationError(FlowMCPError):
    """Raised when browser automation encounters an unrecoverable error."""
    pass

class BrowserInitError(BrowserOperationError):
    """Raised when browser fails to launch or initialize."""
    pass

class ElementNotFoundError(BrowserOperationError):
    """Raised when a web element is not found within timeout."""
    pass

class PageTimeoutError(BrowserOperationError):
    """Raised when a page navigation or wait operation times out."""
    pass
