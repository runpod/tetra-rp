#!/usr/bin/env python3
"""
Quick verification script for Docker image constant configuration fix.

This script validates that:
1. Constants are properly defined in constants.py
2. Manifest builder uses constants instead of hardcoded values
3. Environment variables override constants correctly
4. LiveServerless classes use the correct image constants

Run with: uv run python3 scripts/test-image-constants.py
"""

import sys
import os
import subprocess
import json
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
END = '\033[0m'

test_count = 0
passed_count = 0


def test(name, condition, details=""):
    """Print test result"""
    global test_count, passed_count
    test_count += 1

    if condition:
        print(f"{GREEN}✓{END} {name}")
        passed_count += 1
    else:
        print(f"{RED}✗{END} {name}")
        if details:
            print(f"  {details}")


def test_constants_exist():
    """Test that all constants are defined"""
    print(f"\n{BLUE}Test Suite 1: Constants Definition{END}")

    from tetra_rp.core.resources.constants import (
        TETRA_IMAGE_TAG,
        TETRA_GPU_IMAGE,
        TETRA_CPU_IMAGE,
        TETRA_LB_IMAGE,
        TETRA_CPU_LB_IMAGE,
        DEFAULT_WORKERS_MIN,
        DEFAULT_WORKERS_MAX,
    )

    test("TETRA_IMAGE_TAG defined", TETRA_IMAGE_TAG is not None)
    test("TETRA_GPU_IMAGE defined", TETRA_GPU_IMAGE is not None)
    test("TETRA_CPU_IMAGE defined", TETRA_CPU_IMAGE is not None)
    test("TETRA_LB_IMAGE defined", TETRA_LB_IMAGE is not None)
    test("TETRA_CPU_LB_IMAGE defined", TETRA_CPU_LB_IMAGE is not None)
    test("DEFAULT_WORKERS_MIN is 1", DEFAULT_WORKERS_MIN == 1)
    test("DEFAULT_WORKERS_MAX is 3", DEFAULT_WORKERS_MAX == 3)

    print(f"  Constants values (with TETRA_IMAGE_TAG={TETRA_IMAGE_TAG}):")
    print(f"    TETRA_GPU_IMAGE: {TETRA_GPU_IMAGE}")
    print(f"    TETRA_CPU_IMAGE: {TETRA_CPU_IMAGE}")
    print(f"    TETRA_LB_IMAGE: {TETRA_LB_IMAGE}")
    print(f"    TETRA_CPU_LB_IMAGE: {TETRA_CPU_LB_IMAGE}")


def test_manifest_builder():
    """Test that manifest builder uses constants"""
    print(f"\n{BLUE}Test Suite 2: Manifest Builder Integration{END}")

    from tetra_rp.cli.commands.build_utils.manifest import ManifestBuilder
    from tetra_rp.core.resources.constants import (
        TETRA_CPU_LB_IMAGE,
        DEFAULT_WORKERS_MIN,
        DEFAULT_WORKERS_MAX,
    )

    builder = ManifestBuilder(project_name="test", remote_functions=[])

    # Test _create_mothership_resource
    mothership = builder._create_mothership_resource({
        "file_path": Path("main.py"),
        "app_variable": "app"
    })

    test(
        "Mothership uses TETRA_CPU_LB_IMAGE",
        mothership["imageName"] == TETRA_CPU_LB_IMAGE,
        f"Got {mothership['imageName']}"
    )
    test(
        "Mothership uses DEFAULT_WORKERS_MIN",
        mothership["workersMin"] == DEFAULT_WORKERS_MIN,
        f"Got {mothership['workersMin']}"
    )
    test(
        "Mothership uses DEFAULT_WORKERS_MAX",
        mothership["workersMax"] == DEFAULT_WORKERS_MAX,
        f"Got {mothership['workersMax']}"
    )

    print(f"  Mothership config:")
    print(f"    imageName: {mothership['imageName']}")
    print(f"    workersMin: {mothership['workersMin']}")
    print(f"    workersMax: {mothership['workersMax']}")


def test_live_serverless():
    """Test that LiveServerless uses constants"""
    print(f"\n{BLUE}Test Suite 3: LiveServerless Integration{END}")

    from tetra_rp import LiveServerless, CpuLiveLoadBalancer, LiveLoadBalancer
    from tetra_rp.core.resources.constants import (
        TETRA_GPU_IMAGE,
        TETRA_LB_IMAGE,
        TETRA_CPU_LB_IMAGE,
    )

    gpu_ls = LiveServerless(name="test-gpu")
    gpu_lb = LiveLoadBalancer(name="test-gpu-lb")
    cpu_lb = CpuLiveLoadBalancer(name="test-cpu-lb")

    test(
        "LiveServerless uses TETRA_GPU_IMAGE",
        gpu_ls.imageName == TETRA_GPU_IMAGE,
        f"Got {gpu_ls.imageName}"
    )
    test(
        "LiveLoadBalancer uses TETRA_LB_IMAGE",
        gpu_lb.imageName == TETRA_LB_IMAGE,
        f"Got {gpu_lb.imageName}"
    )
    test(
        "CpuLiveLoadBalancer uses TETRA_CPU_LB_IMAGE",
        cpu_lb.imageName == TETRA_CPU_LB_IMAGE,
        f"Got {cpu_lb.imageName}"
    )

    print(f"  Resource images:")
    print(f"    LiveServerless: {gpu_ls.imageName}")
    print(f"    LiveLoadBalancer: {gpu_lb.imageName}")
    print(f"    CpuLiveLoadBalancer: {cpu_lb.imageName}")


def test_env_var_override():
    """Test environment variable override in subprocess"""
    print(f"\n{BLUE}Test Suite 4: Environment Variable Override{END}")

    # Test with TETRA_IMAGE_TAG=dev in subprocess
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
import os
sys.path.insert(0, 'src')

from tetra_rp.core.resources.constants import (
    TETRA_IMAGE_TAG,
    TETRA_CPU_LB_IMAGE,
)

assert TETRA_IMAGE_TAG == "dev", f"Expected dev, got {TETRA_IMAGE_TAG}"
assert TETRA_CPU_LB_IMAGE == "runpod/tetra-rp-lb-cpu:dev", f"Got {TETRA_CPU_LB_IMAGE}"
print(f"OK:{TETRA_CPU_LB_IMAGE}")
"""],
        env={**dict(os.environ), "TETRA_IMAGE_TAG": "dev"},
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    success = result.returncode == 0 and "OK:" in result.stdout
    test(
        "TETRA_IMAGE_TAG=dev override works",
        success,
        result.stderr if not success else ""
    )

    if success:
        image = result.stdout.split("OK:")[1].strip()
        print(f"  With TETRA_IMAGE_TAG=dev:")
        print(f"    TETRA_CPU_LB_IMAGE: {image}")


def test_no_hardcoded_values():
    """Verify no hardcoded image names in manifest.py"""
    print(f"\n{BLUE}Test Suite 5: Code Quality Check{END}")

    manifest_file = Path(__file__).parent.parent / "src/tetra_rp/cli/commands/build_utils/manifest.py"
    content = manifest_file.read_text()

    hardcoded_patterns = [
        'runpod/tetra-rp-lb-cpu:latest',
        'runpod/tetra-rp-lb:latest',
        'imageName": "runpod/',
    ]

    for pattern in hardcoded_patterns:
        if pattern in content:
            test(f"No hardcoded '{pattern}' in manifest.py", False)
        else:
            test(f"No hardcoded '{pattern}' in manifest.py", True)

    # Check that manifest.py imports the constants
    test(
        "Manifest imports TETRA_CPU_LB_IMAGE",
        "TETRA_CPU_LB_IMAGE" in content,
    )
    test(
        "Manifest imports TETRA_LB_IMAGE",
        "TETRA_LB_IMAGE" in content,
    )
    test(
        "Manifest imports DEFAULT_WORKERS_MIN",
        "DEFAULT_WORKERS_MIN" in content,
    )


def main():
    print(f"\n{BLUE}{'='*60}{END}")
    print(f"{BLUE}Docker Image Constants Verification{END}")
    print(f"{BLUE}{'='*60}{END}")

    test_constants_exist()
    test_manifest_builder()
    test_live_serverless()
    test_env_var_override()
    test_no_hardcoded_values()

    print(f"\n{BLUE}{'='*60}{END}")
    print(f"Results: {GREEN}{passed_count}/{test_count} tests passed{END}")
    print(f"{BLUE}{'='*60}{END}")

    if passed_count == test_count:
        print(f"\n{GREEN}✓ ALL TESTS PASSED{END}")
        print("\nThe Docker image configuration fix is working correctly:")
        print("  ✓ Constants are properly centralized")
        print("  ✓ Manifest builder uses constants")
        print("  ✓ LiveServerless classes use constants")
        print("  ✓ Environment variables override constants")
        print("  ✓ No hardcoded values remain")
        return 0
    else:
        print(f"\n{RED}✗ {test_count - passed_count} TESTS FAILED{END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
