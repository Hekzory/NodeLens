#!/usr/bin/env python3
"""Compact test report wrapper around pytest + coverage for NodeLens.

Runs pytest with coverage, then prints a diploma-friendly summary block.
"""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
JUNIT_XML = BACKEND / ".test-report.xml"
COV_JSON = BACKEND / ".coverage.json"

BLUE = "\033[94m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def run_pytest() -> int:
    """Run pytest with coverage and JUnit XML output, return exit code."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        f"--junitxml={JUNIT_XML}",
        "--cov=nodelens",
        f"--cov-report=json:{COV_JSON}",
        "--cov-report=",
        "--tb=short",
        "-q",
        *sys.argv[1:],
    ]
    result = subprocess.run(cmd, cwd=BACKEND, check=True)
    return result.returncode


def parse_junit(path: Path) -> dict:
    """Extract test counts from JUnit XML."""
    tree = ET.parse(path)
    root = tree.getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    return {
        "tests": int(suite.get("tests", 0)),
        "failures": int(suite.get("failures", 0)),
        "errors": int(suite.get("errors", 0)),
        "skipped": int(suite.get("skipped", 0)),
        "time": float(suite.get("time", 0)),
    }


def parse_coverage(path: Path) -> dict:
    """Extract coverage stats from JSON report."""
    data = json.loads(path.read_text())
    totals = data["totals"]
    files = data["files"]

    per_module = {}
    for fpath, info in files.items():
        parts = fpath.replace("\\", "/").split("/")
        if len(parts) >= 2:
            module = parts[1] if parts[0] == "nodelens" else parts[0]
        else:
            module = parts[0]
        if module not in per_module:
            per_module[module] = {"stmts": 0, "miss": 0}
        per_module[module]["stmts"] += info["summary"]["num_statements"]
        per_module[module]["miss"] += info["summary"]["missing_lines"]

    modules = {}
    for mod, counts in sorted(per_module.items()):
        pct = ((counts["stmts"] - counts["miss"]) / counts["stmts"] * 100) if counts["stmts"] else 0
        modules[mod] = {"stmts": counts["stmts"], "miss": counts["miss"], "pct": pct}

    return {
        "total_stmts": totals["num_statements"],
        "total_miss": totals["missing_lines"],
        "total_pct": totals["percent_covered"],
        "modules": modules,
    }


def print_report(junit: dict, cov: dict):
    """Print compact diploma-friendly report."""
    passed = junit["tests"] - junit["failures"] - junit["errors"] - junit["skipped"]
    all_passed = junit["failures"] == 0 and junit["errors"] == 0

    w = 58
    print(f"{BOLD}{'=' * w}")
    print("  NodeLens  Unit Test Report")
    print(f"{'=' * w}{RESET}")

    # Test results row
    status = f"{GREEN}ALL PASSED{RESET}" if all_passed else f"{RED}FAILURES DETECTED{RESET}"
    print(f"  {BOLD}Tests:{RESET}  {passed} passed", end="")
    if junit["failures"]:
        print(f", {RED}{junit['failures']} failed{RESET}", end="")
    if junit["errors"]:
        print(f", {RED}{junit['errors']} errors{RESET}", end="")
    if junit["skipped"]:
        print(f", {YELLOW}{junit['skipped']} skipped{RESET}", end="")
    print(f"  |  {BOLD}Total:{RESET} {junit['tests']}  |  {status}")
    print(f"  {BOLD}Time:{RESET}   {junit['time']:.2f}s")

    # Coverage summary
    pct = cov["total_pct"]
    color = GREEN if pct >= 70 else YELLOW if pct >= 50 else RED
    print(f"  {BOLD}Coverage:{RESET} {color}{pct:.1f}%{RESET}  ({cov['total_stmts'] - cov['total_miss']}/{cov['total_stmts']} statements)")

    # Per-module coverage table
    print(f"\n  {DIM}{'Module':<22} Stmts   Miss    Cover{RESET}")
    print(f"  {DIM}{'-' * 48}{RESET}")
    for mod, info in cov["modules"].items():
        mc = GREEN if info["pct"] >= 70 else YELLOW if info["pct"] >= 50 else RED
        print(f"  {mod:<22} {info['stmts']:>5}  {info['miss']:>5}   {mc}{info['pct']:>5.1f}%{RESET}")
    print(f"  {DIM}{'-' * 48}{RESET}")
    print(f"  {BOLD}{'TOTAL':<22} {cov['total_stmts']:>5}  {cov['total_miss']:>5}   {color}{pct:>5.1f}%{RESET}")

    print(f"{BOLD}{'=' * w}{RESET}")

    # Final verdict
    if all_passed:
        print(f"  {GREEN}{BOLD}Result: PASS{RESET}")
    else:
        print(f"  {RED}{BOLD}Result: FAIL{RESET}")


def cleanup():
    JUNIT_XML.unlink(missing_ok=True)
    COV_JSON.unlink(missing_ok=True)


def main():
    exit_code = run_pytest()
    try:
        junit = parse_junit(JUNIT_XML)
        cov = parse_coverage(COV_JSON)
        print_report(junit, cov)
    except Exception as e:  # noqa: BLE001
        print(f"\n{RED}Could not generate report: {e}{RESET}", file=sys.stderr)
    finally:
        cleanup()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
