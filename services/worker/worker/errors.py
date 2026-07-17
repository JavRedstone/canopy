from httpx import HTTPError
from postgrest.exceptions import APIError

from worker.llm import LLMGatewayError
from worker.sandbox import SandboxError

# Transient infrastructure failures: the job should stay on the queue and be retried
# once its visibility timeout expires, rather than being archived and permanently lost.
RETRYABLE_ERRORS = (HTTPError, APIError, LLMGatewayError, SandboxError)
