from pydantic import BaseModel, ConfigDict, Field


class StringMatch(BaseModel):
    exact: str | None = None
    prefix: str | None = None
    regex: str | None = None


class IstioMatch(BaseModel):
    headers: dict[str, StringMatch] | None = None
    sourceLabels: dict[str, str] | None = None


class EnvVar(BaseModel):
    name: str
    value: str


class ContainerOverrides(BaseModel):
    containerName: str
    image: str | None = None
    command: list[str] | None = None
    env: list[EnvVar] | None = None


class SubsetSpec(BaseModel):
    name: str
    namespace: str
    podLabels: dict[str, str] | None = None
    replicas: int | None = None
    containers: list[ContainerOverrides] | None = None
    initContainers: list[ContainerOverrides] | None = None
    defaultVersion: str | None = None


class ResourceStatus(BaseModel):
    name: str
    namespace: str
    status: str


class SubsetStatus(BaseModel):
    deployment: ResourceStatus | None = None
    destinationRules: list[ResourceStatus] | None = None
    virtualServices: list[ResourceStatus] | None = None
    hash: int | None = None


class ConsumerStatus(BaseModel):
    name: str
    namespace: str
    status: str
    hash: int | None = None


class DynamicEnvResponse(BaseModel):
    name: str
    namespace: str
    creationTimestamp: str | None = None
    state: str | None = None
    totalCount: int | None = None
    totalReady: int | None = None
    subsetsStatus: dict[str, SubsetStatus] | None = None
    consumersStatus: dict[str, ConsumerStatus] | None = None
    istioMatches: list[IstioMatch] | None = None
    subsets: list[SubsetSpec] | None = None
    consumers: list[SubsetSpec] | None = None

    class Config:
        extra = "allow"  # Allow extra fields that might be in the response


class DynamicEnvSummary(BaseModel):
    name: str
    namespace: str
    state: str | None = None
    totalCount: int | None = None
    totalReady: int | None = None
    creationTimestamp: str | None = None

    # Add deployment status summary
    deployments_ready: int | None = None
    deployments_total: int | None = None

    model_config = ConfigDict(
        extra='allow',
        frozen=True
    )

    @classmethod
    def from_full_response(cls, response: DynamicEnvResponse) -> "DynamicEnvSummary":
        """Create a summary from a full response"""
        deployments_ready = 0
        deployments_total = 0

        if response.subsetsStatus:
            deployments_total = len(response.subsetsStatus)
            for subset_status in response.subsetsStatus.values():
                if subset_status.deployment and subset_status.deployment.status == "running":
                    deployments_ready += 1

        return cls(
            name=response.name,
            namespace=response.namespace,
            state=response.state,
            totalCount=response.totalCount,
            totalReady=response.totalReady,
            creationTimestamp=response.creationTimestamp,
            deployments_ready=deployments_ready,
            deployments_total=deployments_total
        )


class DynamicEnvFilter(BaseModel):
    state: str | None = Field(
        None,
        description=(
            "Filter by state (e.g., 'Ready', 'Failed', 'processing')"
        )
    )
    namespace: str | None = Field(None, description="Filter by namespace")
    name_contains: str | None = Field(
        None,
        description="Filter by name containing this string"
    )
    deployment_status: str | None = Field(
        None,
        description=(
            "Filter by deployment status (e.g., 'running', 'initializing')"
        )
    )

    model_config = ConfigDict(
        extra='allow',
        populate_by_name=True
    )


class DeleteResponse(BaseModel):
    success: bool
    message: str
    name: str | None = None
    namespace: str | None = None


class DeploymentStatusSummary(BaseModel):
    name: str
    namespace: str
    status: str
    service_name: str
    parent_dynamicenv: str


class PodInfo(BaseModel):
    name: str
    status: str
    containers: list[str]
    ready: bool
    service_name: str | None = None


class PodStatusInfo(BaseModel):
    name: str
    status: str
    containers: list[str]
    ready: bool
    service_name: str | None = None


class DynamicEnvStatusResponse(BaseModel):
    name: str
    namespace: str
    creationTimestamp: str | None = None
    state: str | None = None
    totalCount: int | None = None
    totalReady: int | None = None
    deployments: list[DeploymentStatusSummary] = Field(default_factory=list)
    pods_by_service: dict[str, list[PodInfo]] = Field(default_factory=dict)
    logs: dict[str, dict[str, str]] | None = None

    model_config = ConfigDict(
        extra='allow',
        validate_assignment=True
    )
