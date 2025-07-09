# Release System Documentation

## Overview

The tetra-rp project uses a modern, production-ready release automation system built on **Release Please v4** with comprehensive quality gates, security scanning, and automated PyPI publishing via OIDC trusted publishing.

## Architecture

### Workflow Structure
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Quality Gates │    │  Security Scan  │    │ Release Please  │
│                 │    │                 │    │                 │
│ • Multi-Python  │    │ • CodeQL        │    │ • PR Creation   │
│ • Type Checking │    │ • Bandit SAST   │    │ • Changelog     │
│ • Linting       │    │                 │    │ • Version Bump  │
│ • Testing       │    │                 │    │ • Tag Creation  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐    ┌─────────────────┐
                    │ PyPI Publishing │    │ Post-Release    │
                    │                 │    │   Validation    │
                    │ • OIDC Auth     │    │ • Availability  │
                    │ • Signing       │    │ • Installation  │
                    │ • Verification  │    │ • Notification  │
                    └─────────────────┘    └─────────────────┘
```

### Key Components

1. **Quality Gates** - Multi-version testing with code quality enforcement
2. **Security Scanning** - SAST analysis with Bandit and CodeQL
3. **Release Please** - Automated semantic versioning and changelog generation
4. **PyPI Publishing** - Secure, verified package publication
5. **Post-Release Validation** - Deployment verification and notifications

## Release Process

### Normal Release Flow

1. **Development**: Create feature branches with conventional commits
2. **PR Creation**: Release Please automatically creates release PR when ready
3. **Review**: Team reviews the automated release PR
4. **Merge**: Merging release PR triggers publication pipeline
5. **Validation**: Automated verification of successful deployment

### Conventional Commits

The system uses conventional commits for automated versioning:

```bash
# Feature (minor version bump)
feat: add new GPU resource allocation system

# Bug fix (patch version bump)
fix: resolve memory leak in resource cleanup

# Breaking change (major version bump)
feat!: restructure API for better performance

# Documentation (no version bump)
docs: update API documentation

# Other types: fix, perf, refactor, test, build, ci, chore
```

### Version Bumping Rules

- **Major (1.0.0 → 2.0.0)**: Breaking changes (`feat!:`, `fix!:`, etc.)
- **Minor (1.0.0 → 1.1.0)**: New features (`feat:`)
- **Patch (1.0.0 → 1.0.1)**: Bug fixes (`fix:`)

## Quality Standards

### Code Quality Requirements
- **Linting**: Ruff with strict formatting (blocking)
- **Type Checking**: MyPy analysis (non-blocking, for development feedback)
- **Testing**: Full test suite execution (blocking)

### Security Requirements
- **SAST**: Bandit static analysis (blocking)
- **Code Quality**: CodeQL analysis (non-blocking)

### Build Requirements
- **Python Versions**: 3.9, 3.10, 3.11, 3.12, 3.13
- **Package Verification**: Twine check and Sigstore signing
- **OIDC Publishing**: Trusted publishing without API keys

## Configuration Files

### `.release-please-config.json`
```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "packages": {
    ".": {
      "release-type": "python",
      "extra-files": [
        {
          "type": "toml", 
          "path": "pyproject.toml",
          "jsonpath": "$.project.version"
        }
      ]
    }
  },
  "pull-request-title-pattern": "chore: release ${version}",
  "pull-request-header": "Release Please automated release PR",
  "separate-pull-requests": false,
  "changelog-sections": [
    {
      "type": "feat",
      "section": "Features",
      "hidden": false
    },
    {
      "type": "fix", 
      "section": "Bug Fixes",
      "hidden": false
    }
  ]
}
```

### `.release-please-manifest.json`
```json
{
  ".": "0.5.0"
}
```

## Emergency Procedures

### Manual Release Override
For emergency releases, use workflow dispatch:

```bash
# Force publish without waiting for release PR
gh workflow run release.yml -f force_publish=true

# Skip tests in emergency (not recommended)
gh workflow run release.yml -f skip_tests=true -f force_publish=true
```

### Rollback Procedure
1. **Identify Issue**: Determine problematic version
2. **PyPI Yank**: Remove version from PyPI if necessary
3. **Hotfix**: Create hotfix branch from last known good version
4. **Emergency Release**: Use manual override for quick deployment

## Troubleshooting

### Common Issues

#### Release PR Not Created
**Symptoms**: No automatic release PR after feature merges
**Causes**: 
- No conventional commits since last release
- All changes are hidden types (`chore`, `test`, `build`, `ci`)
- Configuration errors

**Solutions**:
1. Check commit history for conventional commit format
2. Verify `.release-please-config.json` syntax
3. Review `.release-please-manifest.json` for correct version

#### PyPI Publishing Fails
**Symptoms**: Quality gates pass but PyPI publishing fails
**Causes**:
- OIDC configuration issues
- Package build failures
- Network connectivity problems
- Version conflicts

**Solutions**:
1. Check OIDC trusted publishing configuration
2. Verify package build locally: `uv build && uv run twine check dist/*`
3. Check PyPI status and version conflicts
4. Use manual override with `force_publish=true`

#### Test Failures
**Symptoms**: Quality gates fail on test execution
**Causes**:
- Broken functionality
- Environment issues
- Missing dependencies

**Solutions**:
1. Run tests locally: `make check`
2. Review test output in CI artifacts
3. Fix failing tests before proceeding
4. Use `skip_tests=true` for emergency releases only

### Debug Information

The workflow provides extensive debug output:

```yaml
# Check workflow run logs for:
- Release Please outputs and decisions
- Test execution results and failures
- Security scan results (Bandit, CodeQL)
- Build artifact verification
- PyPI publication status
```

## Monitoring and Alerting

### Success Indicators
- ✅ All quality gates pass
- ✅ Security scans complete without blocking issues
- ✅ Package successfully published to PyPI
- ✅ Post-release validation confirms availability

### Failure Notifications
- Quality gate failures (linting, type checking, tests)
- Security vulnerabilities detected (Bandit findings)
- PyPI publishing errors
- Post-release validation failures

## Maintenance

### Regular Tasks
- **Monthly**: Review and update dependency constraints
- **Quarterly**: Update workflow actions to latest versions
- **Annually**: Review and update security scanning tools

### Configuration Updates
- **Quality Thresholds**: Adjust coverage and quality requirements
- **Security Policies**: Update vulnerability scanning rules
- **Workflow Actions**: Keep GitHub Actions up to date

### Performance Optimization
- **Caching**: UV cache is enabled for faster builds
- **Parallelization**: Matrix builds run in parallel
- **Timeouts**: Appropriate timeouts prevent hanging jobs

## Best Practices

### For Developers
1. **Always use conventional commits** for proper version detection
2. **Run `make check` locally** before pushing changes
3. **Review release PRs carefully** before merging
4. **Monitor CI status** and address failures promptly

### For Maintainers
1. **Regular workflow updates** to stay current with best practices
2. **Security monitoring** for emerging threats
3. **Performance optimization** of CI/CD pipeline
4. **Documentation updates** as system evolves

## Security Considerations

### OIDC Trusted Publishing
- No API keys stored in repository
- Automatic token generation for each publish
- Scoped permissions for security

### Signing and Verification
- Packages automatically signed with Sigstore
- Build artifacts verified before publication
- Comprehensive audit trail maintained

### Dependency Management
- Security scanning with Bandit for code vulnerabilities
- Dependency pinning for reproducible builds  
- Regular security updates

## Support

For issues with the release system:
1. Check this documentation first
2. Review workflow run logs for specific errors
3. Consult GitHub Actions documentation
4. Contact maintainers for complex issues

---

*This release system follows modern DevOps best practices and provides a robust foundation for automated software delivery.*