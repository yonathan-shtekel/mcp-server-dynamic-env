from src.models.dynamicenv import DynamicEnvFilter, DynamicEnvSummary, PodInfo


def apply_dynamicenv_filters(items: list[dict], filter: DynamicEnvFilter) -> list[dict]:
    """Apply filters to DynamicEnv items"""
    filtered_items = items

    if filter.namespace:
        filtered_items = [item for item in filtered_items
                          if item["metadata"]["namespace"] == filter.namespace]

    if filter.state:
        filtered_items = [item for item in filtered_items
                          if item.get("status", {}).get("state") == filter.state]

    if filter.name_contains:
        filtered_items = [item for item in filtered_items
                          if filter.name_contains.lower() in item["metadata"]["name"].lower()]

    if filter.deployment_status:
        # This requires checking each deployment in subsetsStatus
        temp_items = []
        for item in filtered_items:
            subsets_status = item.get("status", {}).get("subsetsStatus", {})
            for subset_data in subsets_status.values():
                if subset_data.get("deployment", {}).get("status") == filter.deployment_status:
                    temp_items.append(item)
                    break
        filtered_items = temp_items

    return filtered_items


def create_dynamicenv_summary(item: dict) -> DynamicEnvSummary:
    """Create a DynamicEnvSummary from a raw item"""
    metadata = item.get("metadata", {})
    status = item.get("status", {})
    subsets_status = status.get("subsetsStatus", {})

    deployments_total = len(subsets_status)
    deployments_ready = sum(1 for subset in subsets_status.values()
                            if subset.get("deployment", {}).get("status") == "running")

    return DynamicEnvSummary(
        name=metadata.get("name"),
        namespace=metadata.get("namespace"),
        creationTimestamp=metadata.get("creationTimestamp"),
        state=status.get("state"),
        totalCount=status.get("totalCount"),
        totalReady=status.get("totalReady"),
        deployments_ready=deployments_ready,
        deployments_total=deployments_total
    )


def extract_service_name(pod) -> str:
    """Extract service name from pod labels or name"""
    if pod.metadata.labels and "app.kubernetes.io/name" in pod.metadata.labels:
        return pod.metadata.labels["app.kubernetes.io/name"]

    # Try to extract from pod name
    parts = pod.metadata.name.split("-")
    if len(parts) > 2:
        return parts[0]

    return "unknown"


def create_pod_info(pod, service_name: str) -> PodInfo:
    """Create PodInfo from a pod"""
    container_statuses = pod.status.container_statuses or []
    is_ready = all(cs.ready for cs in container_statuses)

    return PodInfo(
        name=pod.metadata.name,
        status=pod.status.phase,
        containers=[c.name for c in pod.spec.containers],
        ready=is_ready,
        service_name=service_name
    )
