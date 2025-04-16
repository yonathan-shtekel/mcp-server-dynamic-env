import logging
from logging.config import dictConfig

from mcp.server.fastmcp import Context, FastMCP

from src.dynamicenv_service import (
    delete_dynamicenv_instance,
    get_dynamicenv_detailed_status,
    list_all_dynamicenvs,
)
from src.kubernetes_client import get_k8s_context
from src.models.dynamicenv import (
    DeleteResponse,
    DynamicEnvFilter,
    DynamicEnvStatusResponse,
    DynamicEnvSummary,
)

# Create an MCP server
mcp = FastMCP("DynamicEnv Manager", dependencies=["kubernetes", "pydantic"])

# Configure logging
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {"handlers": ["default"], "level": "INFO"},
}

dictConfig(logging_config)
logger = logging.getLogger("dynamicenv")


@mcp.tool(
    name="list_dynamicenvs",
    description="List all DynamicEnv instances with optional filtering"
)
async def list_dynamicenvs(
        filter: DynamicEnvFilter | None = None
) -> list[DynamicEnvSummary] | dict[str, str]:
    """List all DynamicEnv instances with optional filtering"""
    async with get_k8s_context() as clients:
        return await list_all_dynamicenvs(clients, filter)


@mcp.tool(name="delete_dynamicenv", description="Delete a DynamicEnv instance")
async def delete_dynamicenv(env_id: str, namespace: str = "default") -> DeleteResponse:
    """Delete a DynamicEnv instance"""
    async with get_k8s_context() as clients:
        return await delete_dynamicenv_instance(clients, env_id, namespace)


@mcp.tool(
    name="get_dynamicenv_status",
    description="Get comprehensive status of a DynamicEnv with progress reporting"
)
async def get_dynamicenv_status(
        env_id: str,
        namespace: str = "default",
        include_logs: bool = False,
        log_lines: int = 50,
        ctx: Context = None) -> DynamicEnvStatusResponse | dict[str, str]:
    """
    Get detailed status information about a DynamicEnv instance with progress reporting.
    This tool provides a comprehensive overview of a DynamicEnv's status, including:
    - Basic DynamicEnv information
    - Deployment statuses
    - Pod statuses
    - Optional logs from pods
    """
    async with get_k8s_context() as clients:
        return await get_dynamicenv_detailed_status(
            clients, env_id, namespace, include_logs, log_lines, ctx
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")