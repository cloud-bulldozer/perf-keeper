from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStage(str, Enum):
    CLUSTER_INSTALL = "cluster_install"
    DAY2_OPS = "day2_ops"
    WORKLOAD = "workload"
    TEARDOWN = "teardown"


class JobStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ABORTED = "aborted"
    UNKNOWN = "unknown"


class ProwJob(BaseModel):
    """Represents a single prow job run."""
    job_name: str
    build_id: str
    url: str = ""
    status: JobStatus = JobStatus.UNKNOWN
    failed_stage: JobStage | None = None
    ocp_version: str = ""
    payload: str = ""
    duration_minutes: float = 0.0
    artifacts_url: str = ""


class PayloadDiff(BaseModel):
    """Diff between two OCP payloads from Sippy."""
    from_payload: str
    to_payload: str
    ocp_version: str
    pull_requests: list[PullRequestInfo] = Field(default_factory=list)
    component_changes: list[ComponentChange] = Field(default_factory=list)


class PullRequestInfo(BaseModel):
    """A PR included in a payload diff."""
    repo: str
    number: int
    title: str
    author: str = ""
    url: str = ""
    merged_at: str = ""
    files_changed: list[str] = Field(default_factory=list)
    description: str = ""


class ComponentChange(BaseModel):
    """A component that changed between payloads."""
    name: str
    from_image: str = ""
    to_image: str = ""
    pull_requests: list[PullRequestInfo] = Field(default_factory=list)


class MetricSample(BaseModel):
    """A performance metric sample from kube-burner or similar."""
    metric_name: str
    value: float
    unit: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp: str = ""


class JobMetrics(BaseModel):
    """Aggregated metrics from a prow job run."""
    job: ProwJob
    metrics: list[MetricSample] = Field(default_factory=list)
    alerts_fired: list[str] = Field(default_factory=list)


class DiagnosisResult(BaseModel):
    """Final diagnosis output from the agent."""
    summary: str
    root_cause: str
    confidence: str = "low"  # low, medium, high
    evidence: list[str] = Field(default_factory=list)
    suspect_prs: list[PullRequestInfo] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    regression_type: str = ""  # performance, functional, infrastructure
    affected_metrics: list[MetricSample] = Field(default_factory=list)
