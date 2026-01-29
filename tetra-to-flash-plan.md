# Implementation Plan: Rename tetra → flash

**Objective**: Complete renaming of "tetra" to "flash" throughout the codebase (AE-1522)

**Branch**: `deanq/ae-1522-rename-tetra-to-flash`

## Naming Conventions

| Component | Current | New |
|-----------|---------|-----|
| Python package | `tetra_rp` | `runpod_flash` |
| PyPI package | `tetra-rp` | `runpod-flash` |
| CLI entry point | `flash` | `flash` (no change) |
| Config directory | `.tetra/` | `.flash/` |
| Docker images | `runpod/tetra-rp*` | `runpod/flash*` |
| Environment variables | `TETRA_*` | `FLASH_*` |
| Class names | `TetraPaths` | `FlashPaths` |
| Protobuf package | `package tetra;` | `package flash;` |
| Metrics namespace | `tetra.metrics` | `flash.metrics` |
| Resource tracking file | `.tetra_resources.pkl` | `.flash_resources.pkl` |

**Strategy**: Clean break, no backward compatibility. Environment variable override for Docker images.

## Implementation Phases

### Phase 1: Package Structure Rename

**Most disruptive change - must be done atomically in single commit.**

#### 1.1 Rename package directory
```bash
git mv src/tetra_rp src/runpod_flash
```

#### 1.2 Update pyproject.toml
File: `/pyproject.toml`
- Line 2: `name = "tetra_rp"` → `name = "runpod_flash"`
- Line 47: `flash = "tetra_rp.cli.main:app"` → `flash = "runpod_flash.cli.main:app"`
- Lines 57-60: `tetra_rp = [...]` → `runpod_flash = [...]`
- Line 70: `source = ["tetra_rp"]` → `source = ["runpod_flash"]`
- Line 125: `"src/tetra_rp"` → `"src/runpod_flash"`
- Line 149-150: All coverage paths with `tetra_rp` → `runpod_flash`
- All `--cov=tetra_rp` → `--cov=runpod_flash`

#### 1.3 Update all import statements (90+ files)

**Pattern replacements:**
- `from tetra_rp` → `from runpod_flash`
- `import tetra_rp` → `import runpod_flash`
- `"tetra_rp"` → `"runpod_flash"` (in string literals)
- `metadata.version("tetra_rp")` → `metadata.version("runpod_flash")`

**Files affected** (90+ files):
- All files in `src/runpod_flash/` (after rename)
- All files in `tests/`
- Skeleton templates in `src/runpod_flash/cli/utils/skeleton_template/`

**Use IDE find/replace across entire project.**

#### 1.4 Update wheel validation script

File: `scripts/validate-wheel.sh`
- All `tetra_rp-*.whl` → `runpod_flash-*.whl`
- All path patterns `tetra_rp/` → `runpod_flash/`

#### 1.5 Verification
```bash
make quality-check  # All 474+ tests must pass
```

**Commit**: `refactor: rename package from tetra_rp to runpod_flash`

---

### Phase 2: Internal Code Naming

#### 2.1 Class names

File: `src/runpod_flash/config.py`
- Line 7: `class TetraPaths` → `class FlashPaths`
- Update all references to this class

#### 2.2 Function names

File: `src/runpod_flash/config.py`
- `ensure_tetra_dir()` → `ensure_flash_dir()`

File: `src/runpod_flash/cli/commands/build.py`
- `_find_local_tetra_rp()` → `_find_local_runpod_flash()`
- `_bundle_local_tetra_rp()` → `_bundle_local_runpod_flash()`
- `_extract_tetra_rp_dependencies()` → `_extract_runpod_flash_dependencies()`
- `_remove_tetra_from_requirements()` → `_remove_runpod_flash_from_requirements()`

#### 2.3 Variable names

Throughout codebase:
- `tetra_dir` → `flash_dir`
- `tetra_pkg` → `flash_pkg`
- `tetra_deps` → `flash_deps`
- `tetra_task` → `flash_task`
- `tetra_pkg_dir` → `flash_pkg_dir`

#### 2.4 Configuration paths

File: `src/runpod_flash/config.py`
- `.tetra` directory → `.flash` directory (all references)
- `.tetra_resources.pkl` → `.flash_resources.pkl`

Files: `.gitignore`, `src/runpod_flash/cli/utils/skeleton_template/.gitignore`
- Update patterns: `.tetra_resources.pkl` → `.flash_resources.pkl`

#### 2.5 Comments and docstrings

Update all comments and docstrings mentioning "tetra" to "flash":
- `config.py` - Module and function docstrings
- `build.py` - Comments about bundling and dependencies
- `live_serverless.py` - Comments about load balancer images

#### 2.6 Verification
```bash
make quality-check
```

**Commit**: `refactor: rename internal tetra references to flash`

---

### Phase 3: Environment Variables & Constants

#### 3.1 Docker image constants

File: `src/runpod_flash/core/resources/live_serverless.py` (lines 13-23)

```python
# Current → New
TETRA_IMAGE_TAG → FLASH_IMAGE_TAG
TETRA_GPU_IMAGE → FLASH_GPU_IMAGE  # "runpod/flash:{FLASH_IMAGE_TAG}"
TETRA_CPU_IMAGE → FLASH_CPU_IMAGE  # "runpod/flash-cpu:{FLASH_IMAGE_TAG}"
TETRA_LB_IMAGE → FLASH_LB_IMAGE    # "runpod/flash-lb:{FLASH_IMAGE_TAG}"
TETRA_CPU_LB_IMAGE → FLASH_CPU_LB_IMAGE  # "runpod/flash-lb-cpu:{FLASH_IMAGE_TAG}"
```

**Also update image name strings**:
- `runpod/tetra-rp` → `runpod/flash`
- `runpod/tetra-rp-cpu` → `runpod/flash-cpu`
- `runpod/tetra-rp-lb` → `runpod/flash-lb`
- `runpod/tetra-rp-lb-cpu` → `runpod/flash-lb-cpu`

#### 3.2 Reliability configuration environment variables

File: `src/runpod_flash/runtime/reliability_config.py` (lines 75-84, 90-115)

```python
# Current → New
TETRA_CIRCUIT_BREAKER_ENABLED → FLASH_CIRCUIT_BREAKER_ENABLED
TETRA_CB_FAILURE_THRESHOLD → FLASH_CB_FAILURE_THRESHOLD
TETRA_CB_SUCCESS_THRESHOLD → FLASH_CB_SUCCESS_THRESHOLD
TETRA_CB_TIMEOUT_SECONDS → FLASH_CB_TIMEOUT_SECONDS
TETRA_LOAD_BALANCER_ENABLED → FLASH_LOAD_BALANCER_ENABLED
TETRA_LB_STRATEGY → FLASH_LB_STRATEGY
TETRA_RETRY_ENABLED → FLASH_RETRY_ENABLED
TETRA_RETRY_MAX_ATTEMPTS → FLASH_RETRY_MAX_ATTEMPTS
TETRA_RETRY_BASE_DELAY → FLASH_RETRY_BASE_DELAY
TETRA_METRICS_ENABLED → FLASH_METRICS_ENABLED
```

Update both the environment variable names and all `os.getenv()` calls.

#### 3.3 Metrics namespace

File: `src/runpod_flash/runtime/metrics.py` and `reliability_config.py`
- Default namespace: `"tetra.metrics"` → `"flash.metrics"`

#### 3.4 Update test mocks

Files in `tests/` that mock environment variables:
- Update all `TETRA_*` → `FLASH_*` in test setup
- Update assertion strings checking for "tetra" in image names

#### 3.5 Verification
```bash
make quality-check
grep -r "TETRA_" src/  # Should find no results
```

**Commit**: `refactor: rename environment variables from TETRA_* to FLASH_*`

---

### Phase 4: Protobuf Package

#### 4.1 Update proto file

File: `src/runpod_flash/protos/remote_execution.proto`
- Line 3: `package tetra;` → `package flash;`

#### 4.2 Regenerate Python protobuf files

```bash
cd src/runpod_flash/protos
protoc --python_out=. remote_execution.proto
```

Verify generated file references `package flash`.

#### 4.3 Update imports if needed

Check all files importing from `protos.remote_execution` and verify they still work.

#### 4.4 Verification
```bash
make quality-check
```

**Commit**: `refactor: rename protobuf package from tetra to flash`

---

### Phase 5: Documentation

#### 5.1 Main documentation files

- `README.md` - Verify/update remaining "tetra" references
- `CHANGELOG.md` - Update recent entries, keep historical context
- `CONTRIBUTING.md` - Update repository references
- `TESTING.md` - Update coverage commands
- `RELEASE_SYSTEM.md` - Update project name

**Pattern replacements**:
- `pip install tetra_rp` → `pip install runpod-flash`
- `from tetra_rp import` → `from runpod_flash import`
- `tetra-rp` (package name) → `runpod-flash`
- Repository URLs: `runpod/tetra-rp` → `runpod/flash` (if applicable)

#### 5.2 Technical documentation (`docs/` directory)

Update all 13+ markdown files:
- `Flash_SDK_Reference.md` - Update import examples, remove "Import from tetra_rp, not flash" note
- `Flash_Deploy_Guide.md` - Update all code examples
- `Using_Remote_With_LoadBalancer.md` - Update imports
- `LoadBalancer_Runtime_Architecture.md` - Update technical references
- `Runtime_Generic_Handler.md` - Update import paths
- All other docs/*.md files

#### 5.3 CLI documentation

Files in `src/runpod_flash/cli/docs/`:
- `flash-build.md` - Update worker image references
- `flash-init.md`, `flash-run.md`, `flash-undeploy.md` - Update examples

#### 5.4 Skeleton template documentation

File: `src/runpod_flash/cli/utils/skeleton_template/README.md`
- Update all example code and import statements
- Update dependency references

#### 5.5 Migration guide

Create new file: `MIGRATION.md`

```markdown
# Migration Guide: tetra-rp → runpod-flash v0.23.0

## Breaking Changes

### Package Name
- **Before**: `pip install tetra_rp`
- **After**: `pip install runpod-flash`

### Import Statements
- **Before**: `from tetra_rp import remote, LiveServerless`
- **After**: `from runpod_flash import remote, LiveServerless`

### Environment Variables
All `TETRA_*` variables renamed to `FLASH_*`:
- `TETRA_CIRCUIT_BREAKER_ENABLED` → `FLASH_CIRCUIT_BREAKER_ENABLED`
- `TETRA_CB_*` → `FLASH_CB_*`
- `TETRA_LB_*` → `FLASH_LB_*`
- `TETRA_RETRY_*` → `FLASH_RETRY_*`
- `TETRA_METRICS_ENABLED` → `FLASH_METRICS_ENABLED`
- `TETRA_IMAGE_TAG` → `FLASH_IMAGE_TAG`

### Configuration Directory
- **Before**: `.tetra/`
- **After**: `.flash/`

### Docker Images
- **Before**: `runpod/tetra-rp*`
- **After**: `runpod/flash*`

Override with environment variables if needed:
- `FLASH_GPU_IMAGE`, `FLASH_CPU_IMAGE`
- `FLASH_LB_IMAGE`, `FLASH_CPU_LB_IMAGE`

## Migration Steps
1. Update `requirements.txt` or `pyproject.toml`
2. Find/replace imports: `from tetra_rp` → `from runpod_flash`
3. Update environment variables: `TETRA_*` → `FLASH_*`
4. Rename config directory: `mv .tetra .flash`
5. Run tests
```

#### 5.6 Verification
```bash
grep -r "tetra_rp" docs/  # Should be minimal/none
grep -r "from tetra_rp" .  # Should be none except in CHANGELOG
```

**Commit**: `docs: update all references from tetra to flash`

---

### Phase 6: Configuration Files

#### 6.1 Release configuration

File: `release-please-config.json`
- Line 5: `"package-name": "tetra-rp"` → `"package-name": "runpod-flash"`

#### 6.2 GitHub workflows

File: `.github/workflows/release-please.yml`
- Line 79: `url: https://pypi.org/project/tetra-rp/` → `url: https://pypi.org/project/runpod-flash/`

#### 6.3 Makefile

File: `Makefile`
- Update any hardcoded references to `tetra_rp` in coverage commands (should be covered by earlier changes)

#### 6.4 Skeleton template dependencies

File: `src/runpod_flash/cli/utils/skeleton_template/pyproject.toml`
- Line 12: `"tetra-rp"` → `"runpod-flash"`

#### 6.5 Verification
```bash
make quality-check
```

**Commit**: `chore: update release configuration for runpod-flash`

---

## Critical Files Reference

**Priority 1 (Must change for package to work):**
1. `src/tetra_rp/` → `src/runpod_flash/` (directory rename)
2. `pyproject.toml` - Package metadata and build config
3. All Python files with imports (90+ files)

**Priority 2 (Important for functionality):**
4. `src/runpod_flash/config.py` - Class names, paths, directory references
5. `src/runpod_flash/core/resources/live_serverless.py` - Docker images, constants
6. `src/runpod_flash/runtime/reliability_config.py` - Environment variables
7. `src/runpod_flash/cli/commands/build.py` - Function names, variables

**Priority 3 (Important for release):**
8. `release-please-config.json` - PyPI package name
9. `MIGRATION.md` - User migration guide
10. All documentation files

## Verification Strategy

### After Each Phase
```bash
make quality-check  # Must pass all 474+ tests
```

### Before Final Commit
```bash
# 1. Full test suite
make quality-check

# 2. Build package
make build

# 3. Validate wheel
scripts/validate-wheel.sh

# 4. Test CLI in clean environment
python -m venv test_env
source test_env/bin/activate
pip install dist/runpod_flash-*.whl
flash --version
flash init test-project
cd test-project
python mothership.py  # Should work with new imports

# 5. Verify no tetra_rp references in active code
grep -r "from tetra_rp" src/ tests/  # Should be empty
grep -r "import tetra_rp" src/ tests/  # Should be empty
grep -r "tetra_rp" pyproject.toml  # Should be empty
grep -r "TETRA_" src/ --include="*.py"  # Should be empty

# 6. Verify new names present
grep -r "from runpod_flash" src/ tests/  # Should have many results
grep -r "FLASH_" src/ --include="*.py"  # Should have many results
```

## Docker Image Strategy

**Approach**: Use environment variable override initially, coordinate image builds later.

### Implementation
1. Update default image names in code to `runpod/flash*`
2. Document environment variable overrides in README/docs
3. Users can set custom image names via environment variables if needed
4. Coordinate with infrastructure team for new image builds (non-blocking)

### Environment Variables for Override
```bash
FLASH_GPU_IMAGE="runpod/flash:latest"
FLASH_CPU_IMAGE="runpod/flash-cpu:latest"
FLASH_LB_IMAGE="runpod/flash-lb:latest"
FLASH_CPU_LB_IMAGE="runpod/flash-lb-cpu:latest"
```

## Success Criteria

**Must pass before merge:**
- [ ] All 474+ tests pass (`make quality-check`)
- [ ] Package builds successfully as `runpod-flash`
- [ ] No `tetra_rp` imports in src/ or tests/
- [ ] No `TETRA_*` env vars in src/ code
- [ ] CLI `flash init` creates working projects with correct imports
- [ ] Documentation updated with new package name
- [ ] MIGRATION.md created

**Should verify:**
- [ ] Wheel validation passes
- [ ] Fresh install test in clean venv works
- [ ] All markdown docs use `runpod_flash` imports
- [ ] GitHub workflows reference correct PyPI package

## Risk Mitigation

**High Risk**: Package structure rename (Phase 1)
- **Mitigation**: Do in single atomic commit, test immediately
- **Rollback**: `git revert <commit-hash>`

**Medium Risk**: Environment variables (Phase 3)
- **Mitigation**: Comprehensive test suite catches issues
- **Rollback**: Revert commit, republish if needed

**Low Risk**: Documentation (Phase 5)
- **Mitigation**: Review before merge
- **Rollback**: Fix in follow-up commit

## Estimated Timeline

**Development**: 12-16 hours (single developer)
**Testing**: 2-4 hours
**Total**: 1-2 days

**Recommended approach**: Complete all phases in sequence, test thoroughly after each phase.
