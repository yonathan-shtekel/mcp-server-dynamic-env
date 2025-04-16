"""Configuration constants for the DynamicEnv MCP server"""

# Kubernetes CRD identifiers
K8S_GROUP = "riskified.com"
K8S_VERSION = "v1alpha1"
K8S_PLURAL = "dynamicenvs"

# Container names to exclude from log collection
EXCLUDED_CONTAINERS = [
    "copy-vault-env",
    "istio-init",
    "istio-proxy"
]

# Kubernetes label selectors
DYNAMICENV_LABEL = "app.riskified.com/dynamic-environment-version"
