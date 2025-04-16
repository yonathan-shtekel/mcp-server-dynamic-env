import logging
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from src.config import (
    EXCLUDED_CONTAINERS,
    K8S_GROUP,
    K8S_PLURAL,
    K8S_VERSION,
)
from src.kubernetes_client import (
    GROUP,
    PLURAL,
    VERSION,
    K8sClients,
    fetch_dynamicenv,
    fetch_pod_logs,
)
from src.models.dynamicenv import (
    DeleteResponse,
    DeploymentStatusSummary,
    DynamicEnvFilter,
    DynamicEnvStatusResponse,
    DynamicEnvSummary,
)
from src.utils import (
    apply_dynamicenv_filters,
    create_dynamicenv_summary,
    create_pod_info,
    extract_service_name,
)

logger = logging.getLogger("dynamicenv")


async def list_all_dynamicenvs(
    clients: K8sClients,
    filter: DynamicEnvFilter | None = None
) -> list[DynamicEnvSummary] | dict[str, str]:
    """List all DynamicEnv instances with optional filtering"""
    try:
        result = clients.custom_api.list_cluster_custom_object(
            group=K8S_GROUP,
            version=K8S_VERSION,
            plural=K8S_PLURAL
        )
    except ApiException as e:
        logger.error(f"K8s API error: {e}")
        # Don't expose internal error details
        return {"error": "Failed to list DynamicEnv instances"}
    except Exception:
        logger.exception("Unexpected error")
        return {"error": "Internal server error"}

    items = result.get("items", [])

    # Apply filters if provided
    if filter:
        filtered_items = apply_dynamicenv_filters(items, filter)
    else:
        filtered_items = items

    # Create summaries
    return [create_dynamicenv_summary(item) for item in filtered_items]


async def delete_dynamicenv_instance(
    clients: K8sClients,
    env_id: str,
    namespace: str = "default"
) -> DeleteResponse:
    """Delete a DynamicEnv instance"""
    try:
        # First check if the resource exists
        clients.custom_api.get_namespaced_custom_object(
            GROUP, VERSION, namespace, PLURAL, env_id
        )

        # Delete the resource
        clients.custom_api.delete_namespaced_custom_object(
            group=GROUP,
            version=VERSION,
            namespace=namespace,
            plural=PLURAL,
            name=env_id,
            body=client.V1DeleteOptions()
        )

        return DeleteResponse(
            success=True,
            message=f"Successfully deleted DynamicEnv '{env_id}' in namespace '{namespace}'",
            name=env_id,
            namespace=namespace
        )
    except ApiException as e:
        if e.status == 404:
            return DeleteResponse(
                success=False,
                message=f"DynamicEnv '{env_id}' not found in namespace '{namespace}'",
                name=env_id,
                namespace=namespace
            )
        logger.error(f"K8s API error: {e}")
        return DeleteResponse(
            success=False,
            message=f"Failed to delete DynamicEnv: {e.reason}",
            name=env_id,
            namespace=namespace
        )
    except Exception as e:
        logger.exception("Unexpected error")
        return DeleteResponse(
            success=False,
            message=f"Unexpected error: {str(e)}",
            name=env_id,
            namespace=namespace
        )


async def process_deployments(
    de: dict,
    env_id: str,
    ctx: Any | None = None
) -> list[DeploymentStatusSummary]:
    """Process deployments from a DynamicEnv"""
    if ctx:
        await ctx.report_progress(10, 100)
        await ctx.info("Processing DynamicEnv metadata")

    status = de.get("status", {})
    subsets_status = status.get("subsetsStatus", {})

    if ctx:
        await ctx.info(f"Processing {len(subsets_status)} deployments")
        await ctx.report_progress(20, 100)

    deployments = []
    deployment_count = len(subsets_status)

    for i, (subset_key, subset_data) in enumerate(subsets_status.items()):
        if ctx and deployment_count > 0:
            progress = 20 + (i / deployment_count) * 20
            await ctx.report_progress(int(progress), 100)
            await ctx.info(f"Processing deployment {i+1}/{deployment_count}")

        if "deployment" in subset_data:
            deployment = subset_data["deployment"]
            service_name = subset_key.split('/')[-1] if '/' in subset_key else subset_key

            deployment_info = DeploymentStatusSummary(
                name=deployment.get("name", ""),
                namespace=deployment.get("namespace", ""),
                status=deployment.get("status", "unknown"),
                service_name=service_name,
                parent_dynamicenv=env_id
            )

            deployments.append(deployment_info)

    return deployments


# Split complex function into smaller functions
async def get_pod_logs_for_env(
    clients: K8sClients,
    pods,
    response: DynamicEnvStatusResponse,
    log_lines: int,
    ctx: Any | None = None,
    excluded_containers: list[str] | None = None
) -> None:
    """Process pod logs for a DynamicEnv"""
    total_pods = len(pods.items)
    for i, pod in enumerate(pods.items):
        if ctx:
            progress = 80 + (i / total_pods) * 20
            await ctx.report_progress(int(progress), 100)
            await ctx.info(f"Processing pod {i + 1}/{total_pods}")

        # Get logs if requested
        if response.logs is None:
            response.logs = {}

        pod_logs = await fetch_pod_logs(
            clients,
            pod,
            log_lines,
            ctx,
            progress_base=0.8 + (i / total_pods) * 0.2,
            progress_weight=(1 / total_pods) * 0.2,
            excluded_containers=excluded_containers
        )
        response.logs[pod.metadata.name] = pod_logs


async def get_dynamicenv_detailed_status(
    clients: K8sClients,
    env_id: str,
    namespace: str = "default",
    include_logs: bool = False,
    log_lines: int = 50,
    ctx: Any | None = None
) -> DynamicEnvStatusResponse | dict[str, str]:
    """
    Get detailed status information about a DynamicEnv instance with progress reporting.
    """
    # Step 1: Fetch the DynamicEnv resource
    de = await fetch_dynamicenv(clients, env_id, namespace, ctx)
    if not de:
        return {"error": f"Failed to fetch DynamicEnv {env_id} in namespace {namespace}"}

    # Step 2: Extract basic information
    metadata = de.get("metadata", {})
    status = de.get("status", {})

    # Initialize response object
    response = DynamicEnvStatusResponse(
        name=metadata.get("name"),
        namespace=metadata.get("namespace"),
        creationTimestamp=metadata.get("creationTimestamp"),
        state=status.get("state"),
        totalCount=status.get("totalCount", 0),
        totalReady=status.get("totalReady", 0),
    )

    # Step 3: Process deployments
    response.deployments = await process_deployments(de, env_id, ctx)

    # Step 4: Get pods if needed
    if ctx:
        await ctx.report_progress(40, 100)
        await ctx.info("Fetching pods information")

    try:
        # Get all pods with the DynamicEnv label
        pods = clients.core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app.riskified.com/dynamic-environment-version={namespace}-{env_id}"
        )

        total_pods = len(pods.items)
        if ctx:
            await ctx.info(f"Found {total_pods} pods to process")

        # Process pods
        for i, pod in enumerate(pods.items):
            if ctx:
                progress = 40 + (i / total_pods) * (40 if include_logs else 60)
                await ctx.report_progress(int(progress), 100)
                await ctx.info(f"Processing pod {i + 1}/{total_pods}")

            # Extract service name and create pod info
            service_name = extract_service_name(pod)

            if service_name not in response.pods_by_service:
                response.pods_by_service[service_name] = []

            pod_info = create_pod_info(pod, service_name)
            response.pods_by_service[service_name].append(pod_info)

            # Step 5: Get logs if requested
            if include_logs:
                await get_pod_logs_for_env(
                    clients,
                    pods,
                    response,
                    log_lines,
                    ctx,
                    EXCLUDED_CONTAINERS
                )

    except ApiException as e:
        logger.error(f"Error listing pods: {e}")
        return {"error": f"Failed to list pods: {e.reason}"}

    # Final progress update
    if ctx:
        await ctx.report_progress(100, 100)
        await ctx.info("Completed gathering DynamicEnv status")

    return response
