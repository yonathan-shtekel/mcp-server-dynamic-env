# DynamicEnv MCP Server

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)

> A high-performance Kubernetes MCP server for managing `DynamicEnv` custom resources with real-time updates and AI-driven integration.

---

## ✨ Overview

**DynamicEnv MCP Server** provides an AI-friendly API interface over `DynamicEnv` Kubernetes Custom Resources, enabling real-time tracking, intelligent debugging, and simplified cleanup for dynamic environments used in development, testing, and ephemeral workloads.

Built with async-first architecture and designed to integrate seamlessly with Model Context Protocol (MCP), it empowers developers and AI agents alike to manage K8s-based environments safely and efficiently.

---

## 🔍 What is DynamicEnv?

`DynamicEnv` is a Kubernetes Custom Resource (CRD) that encapsulates an entire dynamic environment setup. These environments typically include:

- Multiple interdependent services
- Service-specific configurations (secrets, configs, env vars)
- Routing rules (Ingress, Service Mesh)
- Resource constraints (CPU, memory quotas)

This server enhances observability and control over these resources.

---

## 🚀 Why MCP?

The [Model Context Protocol (MCP)](https://github.com/mcp-org/mcp) enables AI tools to:

- Subscribe to real-time updates
- Manage long-running async operations with progress tracking
- Work safely via validation and structured context
- Improve DevOps workflows using intelligent command suggestions

---

## 📄 Key Features

- ✅ **List & filter** DynamicEnv instances by namespace, state, or deployment status
- ⏳ **Live status monitoring** with async updates and progress reporting
- ❌ **Safe deletion** of environments with dependency checks
- ⚖️ **Secure K8s auth** using in-cluster or kubeconfig credentials
- 🔍 **Pod insights**, deployment health, and optional logs
- ✨ **AI-ready** interface via MCP

---

## 🗓 Quick Start

```bash
# Clone the repository
git clone https://github.com/yonathan-shtekel/mcp-server-dynamic-env.git
cd mcp-server-dynamic-env

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

---

## 📖 Usage

### Local Development

```bash
# Install MCP tools
pip install "mcp[cli]"

# Start the server with development tools
mcp dev server.py

# Or install and run in Claude Desktop
mcp install server.py

# Or simply run
mcp run server.py
```

### Core CLI Tools

| Tool            | Description                                                   |
|-----------------|---------------------------------------------------------------|
| `List`          | View all DynamicEnvs with namespace/state filtering            |
| `Status`        | Inspect deployments, pods, and logs                           |
| `Delete`        | Safely delete a DynamicEnv instance from a namespace          |

---

## 📁 Project Structure

```
src/
  kubernetes_client.py     # Kubernetes API wrapper
  dynamicenv_service.py    # Business logic
  utils.py                 # Helpers
  models/
    dynamicenv.py          # Typed data models
tests/                     # Unit & integration tests
server.py                  # MCP-compatible API server
pyproject.toml             # Project config and dependencies
```

---

## 🔧 Testing

```bash
# Run test suite
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=src
```

---

## 💪 Contributing

We welcome all contributions! Here's how to get started:

1. Fork the repo
2. Create a new branch
   ```bash
   git checkout -b feature/my-awesome-feature
   ```
3. Commit and push your code
   ```bash
   git commit -m "Add awesome feature"
   git push origin feature/my-awesome-feature
   ```
4. Submit a Pull Request

Please include tests and documentation updates if applicable.

---

## 💼 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Yonathan Shtekel**  
GitHub: [@yonathan-shtekel](https://github.com/yonathan-shtekel)

---

## ✨ Show Support

Give this project a ⭐️ if it helped you or your team!

---

> Built with ❤️ and powered by [Model Context Protocol (MCP)](https://github.com/mcp-org/mcp)

# Development

## Linting and Formatting

This project uses `ruff` for linting and formatting. To run the linters:

```bash
# Check for linting issues
ruff check src tests

# Auto-fix linting issues
ruff check --fix src tests

# Format code
ruff format src tests
```

The linting configuration is defined in `pyproject.toml` and includes:
- Code style (PEP 8)
- Import sorting
- Type annotation checks
- Best practices
- Code complexity

### Additional Static Analysis

The project also includes other static analysis tools:

```bash
# Type checking
mypy src tests

# Security checks
bandit -r src
safety check

# Documentation coverage
interrogate src
```

All these checks are run automatically in CI/CD pipelines.
