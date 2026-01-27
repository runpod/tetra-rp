# Flash App Deployment Architecture Specification

## Overview
A deployed Flash App consists of a Mothership coordinator and distributed Child Endpoints, where functions are partitioned across endpoints. The system uses a manifest-driven approach to route requests and coordinate execution across the distributed topology.

## Build and Deploy Flow

```mermaid
graph TD
    A["📦 flash build"] -->|"Analyze App"| B["Scan remote functions"]
    B -->|"Write"| C["flash_manifest.json"]
    B -->|"Archive"| D["archive.tar.gz"]

    D -->|"flash deploy"| E["Push Archive +<br/>Assign Build ID"]

    E -->|"User deploys"| F["🎯 Mothership<br/>Endpoint"]

    F -->|"Load persisted<br/>manifest"| G{"Persisted<br/>Manifest?"}
    G -->|"First Time"| H["Initialize<br/>New Manifest"]
    G -->|"Exists"| I{"Local vs<br/>Persisted<br/>Match?"}
    I -->|"Outdated"| J["Update Local<br/>from State"]
    I -->|"Current"| K["Use Local<br/>Manifest"]

    H --> L["Reconcile<br/>Resources"]
    J --> L
    K --> L

    L --> M["Categorize:<br/>New, Changed,<br/>Removed, Unchanged"]

    M --> N["Deploy NEW<br/>Endpoints"]
    M --> O["Update CHANGED<br/>Endpoints"]
    M --> P["Undeploy REMOVED<br/>Endpoints"]
    M --> Q["Skip UNCHANGED<br/>Endpoints"]

    N -->|"Success/Fail"| R["Update Local Manifest<br/>+ Persist to State"]
    O -->|"Success/Fail"| R
    P -->|"Success/Fail"| R

    R --> S["🚀 Reconciliation<br/>Complete"]

    F -.->|"Parallel:<br/>Serve anytime"| T["GET /manifest<br/>Returns manifest"]

    style A fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style F fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style L fill:#f57c00,stroke:#bf360c,stroke-width:3px,color:#fff
    style N fill:#f57c00,stroke:#bf360c,stroke-width:3px,color:#fff
    style O fill:#f57c00,stroke:#bf360c,stroke-width:3px,color:#fff
    style P fill:#d32f2f,stroke:#b71c1c,stroke-width:3px,color:#fff
    style S fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
    style T fill:#7b1fa2,stroke:#4a148c,stroke-width:3px,color:#fff
```

## Request Routing and Execution

```mermaid
graph TD
    A["Request arrives at<br/>Mothership for funcA"] -->|"Consult manifest"| B{"Function<br/>Location?"}

    B -->|"Local to Mothership"| C["Execute locally"]
    B -->|"On Endpoint1"| D["Route request to<br/>Endpoint1 with payload"]

    D --> E["Endpoint1 receives<br/>Endpoint1>funcA"]
    E --> F["Execute funcA"]

    F -->|"Calls funcB"| G{"funcB<br/>Location?"}
    G -->|"Local: Endpoint1"| H["Execute funcB<br/>locally in Endpoint1"]
    G -->|"Remote: Endpoint2"| I["Remote call to<br/>Endpoint2>funcC"]

    H --> J["Return result<br/>to funcA"]
    I -->|"Same as Live<br/>serverless path"| K["Endpoint2 executes<br/>funcC"]
    K --> L["Return response<br/>to Endpoint1"]

    L --> J
    J --> M["funcA completes<br/>with all results"]
    M --> N["Response back<br/>to Mothership"]
    N --> O["Return to client"]

    style A fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style D fill:#f57c00,stroke:#bf360c,stroke-width:3px,color:#fff
    style I fill:#f57c00,stroke:#bf360c,stroke-width:3px,color:#fff
    style O fill:#388e3c,stroke:#1b5e20,stroke-width:3px,color:#fff
```

## Endpoint Responsibility Model

```mermaid
graph LR
    subgraph Mothership["🎯 Mothership<br/>(Coordinator)"]
        MF["Manifest Store<br/>Function Map"]
    end

    subgraph EP1["🔧 Endpoint1"]
        E1F1["funcA"]
        E1F2["funcB"]
        E1["Endpoint ID"]
    end

    subgraph EP2["🔧 Endpoint2"]
        E2F1["funcC"]
        E2F2["funcD"]
        E2["Endpoint ID"]
    end

    MF -->|"funcA, funcB → EP1"| EP1
    MF -->|"funcC, funcD → EP2"| EP2

    EP1 -.->|"Local execution"| E1F1
    E1F1 -.->|"Local execution"| E1F2
    E1F1 -.->|"Remote call"| E2F1

    style Mothership fill:#1976d2,stroke:#0d47a1,stroke-width:3px,color:#fff
    style EP1 fill:#f57c00,stroke:#bf360c,stroke-width:3px,color:#fff
    style EP2 fill:#f57c00,stroke:#bf360c,stroke-width:3px,color:#fff
    style MF fill:#1565c0,stroke:#0d47a1,stroke-width:2px,color:#fff
```

## Key Characteristics

- **Single Codebase**: All endpoints run identical code, differentiation via manifest assignments
- **Manifest-Driven**: The manifest controls function distribution and routing
- **Smart Routing**: System automatically determines if execution is local (in-process) or remote (inter-endpoint)
- **Deployed Mode**: Unlike Live mode, endpoints are aware they're in distributed deployment with explicit role assignments
- **Transparent Execution**: Functions can call other functions without knowing deployment topology; manifest handles routing
- **State Synchronization**: Mothership maintains single source of truth, synced with GQL State Manager
- **Reconciliation**: On each boot, Mothership reconciles local manifest with persisted state to deploy/update/undeploy resources
- **Parallel Serving**: GET /manifest endpoint serves manifest independently of reconciliation process

## Actual Manifest Structure

### Build-Time Manifest (flash_manifest.json)

Generated by `flash build` command:

```json
{
  "version": "1.0",
  "generated_at": "2026-01-12T10:30:00Z",
  "project_name": "my-flash-app",
  "function_registry": {
    "funcA": "endpoint_1",
    "funcB": "endpoint_1",
    "funcC": "endpoint_2",
    "funcD": "endpoint_2"
  },
  "resources": {
    "endpoint_1": {
      "resource_type": "ServerlessResource",
      "handler_file": "handler_endpoint_1.py",
      "functions": [
        {
          "name": "funcA",
          "module": "app.handlers",
          "is_async": true,
          "is_class": false
        },
        {
          "name": "funcB",
          "module": "app.handlers",
          "is_async": false,
          "is_class": false
        }
      ]
    },
    "endpoint_2": {
      "resource_type": "LoadBalancerSlsResource",
      "handler_file": "handler_endpoint_2.py",
      "functions": [
        {
          "name": "funcC",
          "module": "app.api",
          "is_async": true,
          "is_class": false,
          "http_method": "POST",
          "http_path": "/api/process"
        },
        {
          "name": "funcD",
          "module": "app.api",
          "is_async": true,
          "is_class": false,
          "http_method": "GET",
          "http_path": "/api/status"
        }
      ]
    }
  },
  "routes": {
    "endpoint_2": {
      "POST /api/process": "funcC",
      "GET /api/status": "funcD"
    }
  }
}
```

### Runtime Persisted Manifest (State Manager)

Stored in State Manager with deployment metadata:

```json
{
  "version": "1.0",
  "generated_at": "2026-01-12T10:30:00Z",
  "project_name": "my-flash-app",
  "function_registry": {
    "funcA": "endpoint_1",
    "funcB": "endpoint_1",
    "funcC": "endpoint_2",
    "funcD": "endpoint_2"
  },
  "resources": {
    "endpoint_1": {
      "resource_type": "ServerlessResource",
      "handler_file": "handler_endpoint_1.py",
      "functions": [...],
      "config_hash": "a1b2c3d4e5f6",
      "endpoint_url": "https://ep1-abc123.api.runpod.ai",
      "status": "deployed"
    },
    "endpoint_2": {
      "resource_type": "LoadBalancerSlsResource",
      "handler_file": "handler_endpoint_2.py",
      "functions": [...],
      "config_hash": "f6e5d4c3b2a1",
      "endpoint_url": "https://ep2-def456.api.runpod.ai",
      "status": "deployed"
    }
  },
  "routes": {...}
}
```

### GET /manifest Response

Served by Mothership at `/manifest` endpoint. Returns the complete authoritative manifest fetched from State Manager, allowing Child Endpoints to synchronize their configuration:

```json
{
  "version": "1.0",
  "generated_at": "2026-01-12T10:30:00Z",
  "project_name": "my-flash-app",
  "function_registry": {
    "funcA": "endpoint_1",
    "funcB": "endpoint_1",
    "funcC": "endpoint_2",
    "funcD": "endpoint_2"
  },
  "resources": {
    "endpoint_1": {
      "resource_type": "ServerlessResource",
      "handler_file": "handler_endpoint_1.py",
      "functions": [...],
      "config_hash": "a1b2c3d4e5f6",
      "endpoint_url": "https://ep1-abc123.api.runpod.ai",
      "status": "deployed"
    },
    "endpoint_2": {
      "resource_type": "LoadBalancerSlsResource",
      "handler_file": "handler_endpoint_2.py",
      "functions": [...],
      "config_hash": "f6e5d4c3b2a1",
      "endpoint_url": "https://ep2-def456.api.runpod.ai",
      "status": "deployed"
    }
  },
  "routes": {
    "endpoint_2": {
      "POST /api/process": "funcC",
      "GET /api/status": "funcD"
    }
  }
}
```

## Reconciliation Details

### ManifestDiff Categories

During reconciliation, resources are categorized:

- **new**: Resources in local manifest but not in persisted state → Deploy
- **changed**: Resources with different `config_hash` → Update deployment
- **removed**: Resources in persisted state but not in local manifest → Undeploy
- **unchanged**: Resources with matching `config_hash` → Skip

### State Updates

Each reconciliation action updates State Manager:

- **Deploy success**: `{config_hash, endpoint_url, status: "deployed"}`
- **Update success**: `{config_hash, endpoint_url, status: "updated"}`
- **Deploy/Update failure**: `{status: "failed", error: "error message"}`
- **Undeploy success**: Resource entry removed from State Manager

## Environment Variables

### Mothership
- `FLASH_IS_MOTHERSHIP=true` - Identifies this endpoint as mothership
- `RUNPOD_ENDPOINT_ID` - Used to construct mothership URL
- `RUNPOD_API_KEY` - For State Manager authentication
- `FLASH_MANIFEST_PATH` - Optional explicit path to manifest

### Child Endpoints
- `FLASH_RESOURCE_NAME` - Which resource config this endpoint represents
- `RUNPOD_ENDPOINT_ID` - This child's endpoint ID
