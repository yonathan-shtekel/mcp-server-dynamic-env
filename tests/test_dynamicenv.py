from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from kubernetes.client.rest import ApiException

from src.dynamicenv_service import (
    delete_dynamicenv_instance,
    get_dynamicenv_detailed_status,
    list_all_dynamicenvs,
    process_deployments,
)
from src.kubernetes_client import K8sClients
from src.models.dynamicenv import (
    DeleteResponse,
    DynamicEnvFilter,
    DynamicEnvStatusResponse,
)
from src.utils import (
    apply_dynamicenv_filters,
    create_pod_info,
    extract_service_name,
)


class MockPod:
    def __init__(
        self,
        name,
        namespace,
        labels=None,
        containers=None,
        status_phase="Running",
        container_statuses=None
    ):
        self.metadata = MagicMock()
        self.metadata.name = name
        self.metadata.namespace = namespace
        self.metadata.labels = labels or {}

        self.spec = MagicMock()
        self.spec.containers = []
        for c in containers or []:
            container = MagicMock()
            container.name = c
            self.spec.containers.append(container)

        self.status = MagicMock()
        self.status.phase = status_phase
        self.status.container_statuses = container_statuses or []


class MockContext:
    """Mock Context for testing"""
    info = AsyncMock()
    report_progress = AsyncMock()


class MockK8sClients:
    """Mock Kubernetes clients for testing"""
    def __init__(self):
        self.custom_api = MagicMock()
        self.core_api = MagicMock()


@pytest.fixture
def mock_k8s_clients():
    """Create mock Kubernetes clients"""
    custom_api = MagicMock()
    core_api = MagicMock()
    return K8sClients(custom_api=custom_api, core_api=core_api)


@pytest.fixture
def mock_k8s_context(mock_k8s_clients):
    """Create a mock Kubernetes context manager"""
    @asynccontextmanager
    async def _mock_context():
        yield mock_k8s_clients
    return _mock_context


@pytest.fixture
def mock_dynamicenv():
    """Create a mock DynamicEnv response"""
    return {
        "metadata": {
            "name": "test-env",
            "namespace": "test-ns",
            "creationTimestamp": "2023-01-01T00:00:00Z"
        },
        "spec": {},
        "status": {
            "state": "Ready",
            "totalCount": 3,
            "totalReady": 2,
            "subsetsStatus": {
                "service1": {
                    "deployment": {
                        "name": "service1-deploy",
                        "namespace": "test-ns",
                        "status": "running"
                    }
                },
                "service2": {
                    "deployment": {
                        "name": "service2-deploy",
                        "namespace": "test-ns",
                        "status": "initializing"
                    }
                },
                "service3": {
                    "deployment": {
                        "name": "service3-deploy",
                        "namespace": "test-ns",
                        "status": "running"
                    }
                }
            }
        }
    }


@pytest.mark.asyncio
async def test_process_deployments(mock_dynamicenv):
    """Test processing deployments from a DynamicEnv"""
    ctx = MockContext()

    # Call the function
    deployments = await process_deployments(mock_dynamicenv, "test-env", ctx)

    # Verify results
    assert len(deployments) == 3
    assert deployments[0].name == "service1-deploy"
    assert deployments[0].status == "running"
    assert deployments[1].name == "service2-deploy"
    assert deployments[1].status == "initializing"

    # Verify context calls
    assert ctx.report_progress.call_count >= 2
    assert ctx.info.call_count >= 2


@pytest.mark.asyncio
async def test_get_dynamicenv_status():
    """Test getting detailed status of a DynamicEnv"""
    # Create mock clients
    mock_k8s_clients = MockK8sClients()

    # Set up mock responses
    mock_k8s_clients.custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {
            "name": "test-env",
            "namespace": "test-ns",
            "creationTimestamp": "2024-01-01T00:00:00Z"
        },
        "status": {
            "state": "Ready",
            "totalCount": 2,
            "totalReady": 1,
            "subsetsStatus": {
                "app1": {
                    "deployment": {
                        "name": "app1-deploy",
                        "namespace": "test-ns",
                        "status": "running",
                        "service_name": "app1"
                    }
                },
                "app2": {
                    "deployment": {
                        "name": "app2-deploy",
                        "namespace": "test-ns",
                        "status": "initializing",
                        "service_name": "app2"
                    }
                }
            }
        }
    }

    # Mock pod list response
    mock_k8s_clients.core_api.list_namespaced_pod.return_value = MagicMock(items=[])

    # Call the function
    result = await get_dynamicenv_detailed_status(
        mock_k8s_clients,
        "test-env",
        "test-ns"
    )

    # Verify results
    assert isinstance(result, DynamicEnvStatusResponse)
    assert result.name == "test-env"
    assert result.namespace == "test-ns"
    assert result.state == "Ready"
    assert result.totalCount == 2
    assert result.totalReady == 1
    assert len(result.deployments) == 2
    assert result.deployments[0].name == "app1-deploy"
    assert result.deployments[0].status == "running"
    assert result.deployments[1].name == "app2-deploy"
    assert result.deployments[1].status == "initializing"
    assert result.pods_by_service == {}
    assert result.logs is None


def test_extract_service_name():
    """Test extracting service name from pod"""
    # Test with label
    pod1 = MockPod(
        name="some-pod-name",
        namespace="test",
        labels={"app.kubernetes.io/name": "my-service"}
    )
    assert extract_service_name(pod1) == "my-service"

    # Test with pod name
    pod2 = MockPod(
        name="service-name-pod-123",
        namespace="test"
    )
    assert extract_service_name(pod2) == "service"

    # Test fallback
    pod3 = MockPod(
        name="pod",
        namespace="test"
    )
    assert extract_service_name(pod3) == "unknown"


def test_create_pod_info():
    """Test creating PodInfo from pod"""
    # Create a mock container status
    container_status = MagicMock()
    container_status.ready = True

    pod = MockPod(
        name="test-pod",
        namespace="test-ns",
        containers=["app", "sidecar"],
        container_statuses=[container_status, container_status]
    )

    pod_info = create_pod_info(pod, "test-service")

    assert pod_info.name == "test-pod"
    assert pod_info.status == "Running"
    assert len(pod_info.containers) == 2
    assert "app" in pod_info.containers
    assert "sidecar" in pod_info.containers
    assert pod_info.ready is True
    assert pod_info.service_name == "test-service"


def test_apply_dynamicenv_filters():
    """Test applying filters to DynamicEnv items"""
    items = [
        {
            "metadata": {"name": "env1", "namespace": "ns1"},
            "status": {"state": "Ready"}
        },
        {
            "metadata": {"name": "env2", "namespace": "ns2"},
            "status": {"state": "Failed"}
        },
        {
            "metadata": {"name": "test-env", "namespace": "ns1"},
            "status": {"state": "Processing"}
        }
    ]

    # Test namespace filter
    filter1 = DynamicEnvFilter(namespace="ns1")
    result1 = apply_dynamicenv_filters(items, filter1)
    assert len(result1) == 2
    assert result1[0]["metadata"]["name"] == "env1"
    assert result1[1]["metadata"]["name"] == "test-env"

    # Test state filter
    filter2 = DynamicEnvFilter(state="Failed")
    result2 = apply_dynamicenv_filters(items, filter2)
    assert len(result2) == 1
    assert result2[0]["metadata"]["name"] == "env2"

    # Test name contains filter
    filter3 = DynamicEnvFilter(name_contains="test")
    result3 = apply_dynamicenv_filters(items, filter3)
    assert len(result3) == 1
    assert result3[0]["metadata"]["name"] == "test-env"

    # Test combined filters
    filter4 = DynamicEnvFilter(namespace="ns1", state="Ready")
    result4 = apply_dynamicenv_filters(items, filter4)
    assert len(result4) == 1
    assert result4[0]["metadata"]["name"] == "env1"


@pytest.mark.asyncio
async def test_list_dynamicenvs_success(mock_k8s_clients, mock_k8s_context):
    """Test listing DynamicEnvs successfully"""
    # Setup mock response
    mock_k8s_clients.custom_api.list_cluster_custom_object.return_value = {
        "items": [
            {
                "metadata": {
                    "name": "env1",
                    "namespace": "ns1",
                    "creationTimestamp": "2023-01-01T00:00:00Z"
                },
                "status": {
                    "state": "Ready",
                    "totalCount": 2,
                    "totalReady": 2,
                    "subsetsStatus": {
                        "app1": {"deployment": {"status": "running"}},
                        "app2": {"deployment": {"status": "running"}}
                    }
                }
            }
        ]
    }

    # Test with filter
    filter = DynamicEnvFilter(namespace="ns1", state="Ready")
    result = await list_all_dynamicenvs(mock_k8s_clients, filter)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].name == "env1"
    assert result[0].deployments_total == 2
    assert result[0].deployments_ready == 2


@pytest.mark.asyncio
async def test_list_dynamicenvs_api_error(mock_k8s_clients, mock_k8s_context):
    """Test handling API errors when listing DynamicEnvs"""
    # Setup mock to raise API exception
    mock_k8s_clients.custom_api.list_cluster_custom_object.side_effect = ApiException(
        status=403,
        reason="Forbidden"
    )

    result = await list_all_dynamicenvs(mock_k8s_clients)
    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to list DynamicEnv" in result["error"]


@pytest.mark.asyncio
async def test_delete_dynamicenv_success(mock_k8s_clients, mock_k8s_context):
    """Test successful deletion of DynamicEnv"""
    # Setup mocks
    mock_k8s_clients.custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {"name": "test-env", "namespace": "test-ns"}
    }
    mock_k8s_clients.custom_api.delete_namespaced_custom_object.return_value = {}

    result = await delete_dynamicenv_instance(mock_k8s_clients, "test-env", "test-ns")

    assert isinstance(result, DeleteResponse)
    assert result.success is True
    assert result.name == "test-env"
    assert result.namespace == "test-ns"


@pytest.mark.asyncio
async def test_delete_dynamicenv_not_found(mock_k8s_clients, mock_k8s_context):
    """Test deletion of non-existent DynamicEnv"""
    # Setup mock to raise 404
    mock_k8s_clients.custom_api.get_namespaced_custom_object.side_effect = ApiException(
        status=404,
        reason="Not Found"
    )

    result = await delete_dynamicenv_instance(mock_k8s_clients, "test-env", "test-ns")

    assert isinstance(result, DeleteResponse)
    assert result.success is False
    assert "not found" in result.message.lower()


async def test_create_pod_info_with_no_containers():
    """Test creating PodInfo when pod has no containers"""
    pod = MockPod(
        name="test-pod",
        namespace="test-ns",
        containers=[],
        container_statuses=[]
    )

    pod_info = create_pod_info(pod, "test-service")

    assert pod_info.name == "test-pod"
    assert pod_info.status == "Running"
    assert pod_info.containers == []
    assert pod_info.ready is False  # Should be False when no containers
    assert pod_info.service_name == "test-service"


def test_create_pod_info_with_mixed_container_status():
    """Test creating PodInfo with mixed ready states"""
    ready_status = MagicMock()
    ready_status.ready = True
    not_ready_status = MagicMock()
    not_ready_status.ready = False

    pod = MockPod(
        name="test-pod",
        namespace="test-ns",
        containers=["app", "sidecar"],
        container_statuses=[ready_status, not_ready_status]
    )

    pod_info = create_pod_info(pod, "test-service")
    assert pod_info.ready is False  # Should be False if any container is not ready


@pytest.mark.asyncio
async def test_get_dynamicenv_status_with_errors(mock_k8s_clients, mock_k8s_context):
    """Test error handling in get_dynamicenv_status"""
    # Setup mock to raise exception
    mock_k8s_clients.custom_api.get_namespaced_custom_object.side_effect = ApiException(
        status=500,
        reason="Internal Server Error"
    )

    result = await get_dynamicenv_detailed_status(
        mock_k8s_clients,
        env_id="test-env",
        namespace="test-ns"
    )

    assert isinstance(result, dict)
    assert "error" in result
    assert "Failed to fetch DynamicEnv" in result["error"]


def test_filter_with_multiple_conditions():
    """Test applying multiple filter conditions"""
    items = [
        {
            "metadata": {"name": "env1", "namespace": "ns1"},
            "status": {
                "state": "Ready",
                "subsetsStatus": {
                    "app1": {"deployment": {"status": "running"}},
                    "app2": {"deployment": {"status": "failed"}}
                }
            }
        },
        {
            "metadata": {"name": "test-env", "namespace": "ns1"},
            "status": {
                "state": "Ready",
                "subsetsStatus": {
                    "app1": {"deployment": {"status": "running"}}
                }
            }
        }
    ]

    filter = DynamicEnvFilter(
        namespace="ns1",
        state="Ready",
        name_contains="test",
        deployment_status="running"
    )

    result = apply_dynamicenv_filters(items, filter)
    assert len(result) == 1
    assert result[0]["metadata"]["name"] == "test-env"
