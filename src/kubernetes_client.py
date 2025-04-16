import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from kubernetes import client, config
from kubernetes.client.models.v1_delete_options import V1DeleteOptions
from kubernetes.client.models.v1_pod_list import V1PodList
from kubernetes.client.rest import ApiException
from kubernetes.config import ConfigException

logger = logging.getLogger("dynamicenv")

# Constants
GROUP = "riskified.com"
VERSION = "v1alpha1"
PLURAL = "dynamicenvs"

# Add validation pattern
VALID_K8S_NAME = re.compile(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$')

# Define protocols for dependency injection and testing
class KubernetesCustomApi(Protocol):
    def get_namespaced_custom_object(
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str
    ) -> dict:
        ...

    def list_cluster_custom_object(
        self,
        group: str,
        version: str,
        plural: str
    ) -> dict:
        ...

    def delete_namespaced_custom_object(
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        body: V1DeleteOptions,
        **kwargs
    ) -> dict:
        ...


class KubernetesCoreApi(Protocol):
    def list_namespaced_pod(self, namespace: str, label_selector: str) -> V1PodList:
        ...

    def read_namespaced_pod_log(
        self,
        name: str,
        namespace: str,
        container: str = None,
        tail_lines: int | None = None,
        **kwargs
    ) -> str:
        ...


@dataclass
class K8sClients:
    """Container for Kubernetes API clients"""
    custom_api: KubernetesCustomApi | client.CustomObjectsApi
    core_api: KubernetesCoreApi | client.CoreV1Api


def load_k8s_config():
    """Load Kubernetes configuration from local or in-cluster config"""
    try:
        config.load_kube_config()
        logger.info("Loaded kube config (local)")
    except Exception:
        config.load_incluster_config()
        logger.info("Loaded in-cluster config")


def get_k8s_clients() -> K8sClients:
    """Get Kubernetes API clients"""
    load_k8s_config()

    # Optionally set the context
    contexts, active_context = config.list_kube_config_contexts()
    if not contexts:
        raise ValueError("No Kubernetes contexts found")

    context_name = active_context['name']
    logger.info(f"Using Kubernetes context: {context_name}")

    return K8sClients(
        custom_api=client.CustomObjectsApi(),
        core_api=client.CoreV1Api()
    )


@asynccontextmanager
async def get_k8s_context() -> AsyncIterator[K8sClients]:
    """Get authenticated Kubernetes client"""
    try:
        # Try in-cluster config first
        try:
            config.load_incluster_config()
            logger.info("Using in-cluster configuration")
        except ConfigException:
            # Fall back to kubeconfig
            config.load_kube_config()
            logger.info("Using local kubeconfig")

        # Get clients first
        clients = get_k8s_clients()

        # Simple test to check access - just list namespaces
        try:
            core_api = client.CoreV1Api()
            core_api.list_namespace(_request_timeout=2)
            logger.info("Successfully validated Kubernetes access")
        except ApiException as e:
            logger.error(f"Failed to validate Kubernetes access: {e}")
            if e.status == 401:
                raise PermissionError(
                    "Kubernetes authentication failed - please check your credentials"
                ) from e
            raise PermissionError(f"Kubernetes access error: {e.reason}") from e

        try:
            yield clients
        finally:
            # Any cleanup if needed
            pass

    except Exception as e:
        logger.exception("Error setting up Kubernetes client")
        raise RuntimeError(f"Failed to initialize Kubernetes client: {str(e)}") from e


async def fetch_dynamicenv(clients: K8sClients, env_id: str, namespace: str,
                          ctx: Any | None = None) -> dict | None:
    """Fetch a DynamicEnv resource"""
    if ctx:
        await ctx.info(f"Fetching DynamicEnv {env_id} in namespace {namespace}")
        await ctx.report_progress(5, 100)

    try:
        return clients.custom_api.get_namespaced_custom_object(
            GROUP, VERSION, namespace, PLURAL, env_id
        )
    except ApiException as e:
        logger.error(f"K8s API error: {e}")
        return None
    except Exception:
        logger.exception("Unexpected error")
        return None


def validate_k8s_name(name: str, field: str) -> None:
    """Validate Kubernetes resource names"""
    if not VALID_K8S_NAME.match(name):
        raise ValueError(f"Invalid {field} name: {name}")


async def fetch_pod_logs(
    clients: K8sClients,
    pod,
    log_lines: int,
    ctx: Any | None = None,
    progress_base: float = 0,
    progress_weight: float = 1,
    excluded_containers: list[str] | None = None
) -> dict[str, str]:
    """Fetch logs from pod containers"""
    # Validate inputs
    validate_k8s_name(pod.metadata.namespace, "namespace")
    validate_k8s_name(pod.metadata.name, "pod")

    if excluded_containers is None:
        excluded_containers = ["copy-vault-env", "istio-init", "istio-proxy"]

    pod_name = pod.metadata.name
    logs = {}

    container_count = len([c for c in pod.spec.containers if c.name not in excluded_containers])
    container_idx = 0

    for container in pod.spec.containers:
        container_name = container.name

        # Skip specific containers
        if container_name in excluded_containers:
            continue

        if ctx and container_count > 0:
            sub_progress = progress_base + (container_idx / container_count) * progress_weight
            await ctx.report_progress(int(sub_progress * 100), 100)
            await ctx.info(f"Getting logs for {pod_name}/{container_name}")
            container_idx += 1

        try:
            pod_logs = clients.core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=pod.metadata.namespace,
                container=container_name,
                tail_lines=log_lines
            )
            logs[container_name] = pod_logs
        except ApiException as e:
            logs[container_name] = f"Error fetching logs: {e.reason}"

    return logs
