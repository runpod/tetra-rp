# PRODUCT REQUIREMENTS DOCUMENT (PRD)

## Cross-Endpoint Function Routing for Flash Deployments

**Author:** Dean Quinanola + Claude  
**Date:** 2026-01-21  
**Status:** Planning  

---

## 1. Overview

### Problem Statement
Flash-deployed applications need to route function calls across multiple endpoints based on resource requirements (CPU vs GPU). Currently, worker-tetra has static routing logic that doesn't handle provisioning-time endpoint ID assignment. We need a dynamic, resilient routing system that works with RunPod's deployment lifecycle.

### Solution
Implement peer-to-peer cross-endpoint routing using:
- ServiceRegistry (from tetra-rp) for endpoint discovery
- StateManagerClient (from tetra-rp) for manifest queries
- Direct State Manager access from all endpoints (no hub-and-spoke)

### Goals
1. **Dynamic Routing:** Route function calls to correct endpoints based on manifest
2. **Peer-to-Peer:** All endpoints query State Manager directly (no single point of failure)
3. **Simplicity:** Remove unused hub-and-spoke infrastructure
4. **Consistency:** Use existing, tested tetra-rp components

---

## 2. User Stories

### US-1: Cross-Endpoint Function Call
**As a** Flash app developer  
**I want** to call GPU functions from CPU endpoints  
**So that** I can build efficient multi-resource applications

**Acceptance Criteria:**
- CPU endpoint can route function calls to GPU endpoint
- Routing is transparent (developer doesn't manage endpoints)
- Function execution succeeds with correct results
- Logs show routing decision (local vs remote)

### US-2: Local Function Execution
**As a** Flash app developer  
**I want** functions to execute locally when possible  
**So that** I avoid unnecessary network overhead

**Acceptance Criteria:**
- Functions on the same endpoint execute locally
- No HTTP routing for local calls
- Logs indicate local execution

### US-3: Graceful Degradation
**As a** system operator  
**I want** the system to degrade gracefully when State Manager is unavailable  
**So that** local functions continue working

**Acceptance Criteria:**
- Local functions work even if State Manager is down
- Clear error messages when remote routing fails
- Fallback to local execution when routing fails

### US-4: Deployment Workflow
**As a** Flash app developer  
**I want** endpoints to discover each other automatically  
**So that** I don't manually configure routing

**Acceptance Criteria:**
- `flash deploy` provisions all endpoints
- State Manager stores complete manifest
- All endpoints query State Manager for routing info
- Manifest updates propagate within cache TTL (300s)

---

## 3. Functional Requirements

### FR-1: ServiceRegistry Integration
- worker-tetra MUST import ServiceRegistry from tetra-rp
- ServiceRegistry MUST use StateManagerClient for manifest queries
- ServiceRegistry MUST cache manifest for 300 seconds (configurable)
- ServiceRegistry MUST return None for local functions, URL for remote

### FR-2: Routing Logic
- RemoteExecutor MUST detect Flash vs Live Serverless mode
- Flash mode (no function_code) MUST query ServiceRegistry
- ServiceRegistry MUST compare function's resource with current endpoint
- Local functions MUST execute via `_execute_flash_function()`
- Remote functions MUST route via `_route_to_endpoint()` with HTTP

### FR-3: State Manager Queries
- StateManagerClient MUST query RunPod GraphQL API
- Queries MUST fetch manifest via environment_id → build_id → manifest
- Queries MUST extract `resources_endpoints` mapping
- Queries MUST retry on failure with exponential backoff (3 attempts)
- Queries MUST use RUNPOD_API_KEY for authentication

### FR-4: Manifest Structure
- Manifest MUST contain `function_registry` (function_name → resource_name)
- Manifest MUST contain `resources_endpoints` (resource_name → endpoint_url)
- Endpoints MUST identify themselves via FLASH_RESOURCE_NAME or RUNPOD_ENDPOINT_ID

### FR-5: Error Handling
- Function not in manifest → fallback to local execution
- State Manager unavailable → fallback to local execution
- Remote endpoint returns error → return FunctionResponse with error
- All errors MUST be logged with context

### FR-6: HTTP Routing
- Remote calls MUST use RunPod API format (POST with `{"input": {request}}`)
- Remote calls MUST include Authorization header if RUNPOD_API_KEY set
- Remote calls MUST timeout after 300 seconds (DEFAULT_ENDPOINT_TIMEOUT)
- Response format MUST parse `output` field for wrapped responses

---

## 4. Non-Functional Requirements

### NFR-1: Performance
- Manifest caching MUST reduce State Manager queries to 1 per 300s per endpoint
- Local function calls MUST NOT query State Manager
- Remote routing overhead MUST be < 100ms (HTTP call excluded)

### NFR-2: Reliability
- System MUST handle State Manager downtime gracefully
- System MUST work with partial manifest (missing endpoints)
- System MUST retry failed State Manager queries (3 attempts)

### NFR-3: Observability
- All routing decisions MUST be logged at DEBUG level
- State Manager queries MUST be logged at DEBUG level
- Errors MUST be logged at WARNING/ERROR level with context
- Remote HTTP calls MUST be logged with endpoint URL

### NFR-4: Maintainability
- Code MUST pass `make quality-check` (format, lint, type)
- Code coverage MUST remain above 35%
- All public methods MUST have docstrings
- No circular dependencies between tetra-rp and worker-tetra

### NFR-5: Security
- API keys MUST come from environment variables
- API keys MUST NOT be logged
- HTTP calls MUST use HTTPS
- No secrets in manifest or logs

---

## 5. Success Criteria

### Phase 1: Implementation Complete
- ✅ ServiceRegistry updated to use StateManagerClient directly (tetra-rp)
- ✅ ManifestClient deleted (tetra-rp)
- ✅ ProductionWrapper deleted (tetra-rp)
- ✅ Mothership `/manifest` endpoint removed (tetra-rp)
- ✅ RemoteExecutor imports ServiceRegistry from tetra-rp (worker-tetra)
- ✅ Old routing methods deleted (worker-tetra)
- ✅ All tests pass (220+ tests)
- ✅ `make quality-check` passes

### Phase 2: Integration Testing
- ✅ Mock State Manager returns manifest
- ✅ ServiceRegistry routes to correct endpoints
- ✅ Local functions execute without HTTP calls
- ✅ Remote functions route correctly
- ✅ Cache behavior works (queries only after TTL)

### Phase 3: Manual Validation
- ✅ Deploy Flash app with CPU and GPU resources
- ✅ Verify State Manager contains complete manifest
- ✅ Call GPU function from CPU endpoint (success)
- ✅ Call CPU function from CPU endpoint (local execution)
- ✅ Check logs show correct routing decisions
- ✅ Verify State Manager queries minimal (300s cache)

---

## 6. Out of Scope

### Not Included in This PR
- ❌ Deployment logic changes (`flash deploy` upfront provisioning) - separate tetra-rp PR
- ❌ State Manager manifest updates during deployment - separate tetra-rp PR
- ❌ Circuit breaker for failed remote endpoints
- ❌ Load balancing across multiple endpoints of same resource
- ❌ Retry logic for failed remote function calls
- ❌ Metrics/monitoring for cross-endpoint routing
- ❌ Authentication between endpoints (uses RunPod API auth)

---

## 7. Dependencies and Assumptions

### Dependencies
- RunPod GraphQL API availability
- State Manager stores complete manifest (resources_endpoints)
- All endpoints have RUNPOD_API_KEY
- All endpoints have RUNPOD_ENDPOINT_ID
- Flash manifest includes complete function_registry

### Assumptions
- Endpoints trust RunPod API responses
- Manifest updates happen before first function call
- Cache TTL (300s) is acceptable latency for manifest updates
- All endpoints have network access to State Manager
- Function names are unique across all resources

---

## 8. Technical Constraints

### tetra-rp Constraints
- ServiceRegistry must remain backward compatible
- StateManagerClient API cannot change (used by deployment)
- Cannot break existing tetra-rp SDK users

### worker-tetra Constraints
- Must maintain 35%+ code coverage
- Cannot break existing Live Serverless execution
- Must pass all quality checks (ruff format, ruff check, mypy)
- Cannot introduce new runtime dependencies beyond tetra-rp

---

## 9. Risk Assessment

### High Risk
- **State Manager downtime:** Mitigated by fallback to local execution + caching
- **Manifest inconsistency:** Mitigated by 300s cache + clear error messages

### Medium Risk
- **Breaking tetra-rp changes:** Mitigated by comprehensive tests + backward compatibility
- **Import cycle:** Mitigated by clear dependency direction (worker-tetra → tetra-rp)

### Low Risk
- **Performance regression:** Caching limits State Manager queries
- **Code coverage drop:** New tests offset deleted code

---

## 10. Acceptance Testing

### Test Scenario 1: Local Function Execution
1. Deploy Flash app with single CPU resource
2. Call function via API
3. Verify: Function executes locally (no HTTP routing)
4. Verify: Logs show "Executing 'func_name' locally"

### Test Scenario 2: Cross-Endpoint Routing
1. Deploy Flash app with CPU + GPU resources
2. From CPU endpoint, call GPU function
3. Verify: Function routes to GPU endpoint
4. Verify: Function executes successfully
5. Verify: Logs show "Routing 'func_name' to https://..."

### Test Scenario 3: State Manager Unavailable
1. Mock State Manager to return 500 error
2. Call function
3. Verify: Fallback to local execution
4. Verify: Warning logged: "State Manager unavailable"

### Test Scenario 4: Function Not in Manifest
1. Call unknown function
2. Verify: Fallback to local execution
3. Verify: Warning logged: "Function lookup failed"

### Test Scenario 5: Cache Behavior
1. Deploy Flash app, make function call
2. Verify: State Manager queried (cache miss)
3. Make second call within 300s
4. Verify: State Manager NOT queried (cache hit)
5. Wait 301s, make third call
6. Verify: State Manager queried again (cache expired)

---

## 11. Rollout Plan

### Phase 1: tetra-rp Updates
1. Update ServiceRegistry to use StateManagerClient
2. Delete ManifestClient, ProductionWrapper
3. Remove Mothership `/manifest` endpoint
4. Run tetra-rp tests
5. Commit to tetra-rp main branch

### Phase 2: worker-tetra Updates
1. Update pyproject.toml to include tetra-rp runtime
2. Update RemoteExecutor to import ServiceRegistry
3. Delete old routing methods
4. Update tests
5. Run all quality checks
6. Commit to worker-tetra branch

### Phase 3: Integration Testing
1. Build Docker image with updated code
2. Deploy test Flash app to RunPod
3. Run acceptance test scenarios
4. Verify logs and behavior

### Phase 4: Production Deployment
1. Merge worker-tetra PR
2. Release new worker-tetra version
3. Update Flash deployment Docker image
4. Monitor production deployments

---

## 12. Success Metrics

### Code Quality Metrics
- All tests pass (220+ tests)
- Code coverage ≥ 35%
- Zero linting errors (ruff)
- Zero type errors (mypy)

### Functional Metrics
- Cross-endpoint function calls succeed
- Local functions execute without HTTP calls
- State Manager queries ≤ 1 per 300s per endpoint

### Operational Metrics
- Zero breaking changes to existing deployments
- Zero regressions in Live Serverless execution
- Clear error messages for all failure modes

