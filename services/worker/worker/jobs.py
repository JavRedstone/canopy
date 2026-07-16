from dataclasses import dataclass
from typing import Literal


JobKind = Literal["ingestion", "generation", "evaluation", "package_provisioning"]


@dataclass(frozen=True)
class Job:
    kind: JobKind
    payload: dict[str, object]


def handle(job: Job) -> None:
    """Dispatch point for PGMQ consumers; implementations land with their adapters."""
    print(f"worker scaffold received {job.kind}: {job.payload}")
