#!/usr/bin/env bash
# P10-R1 reproducible verification command.
#
# Verifies rootless Podman, the pinned base image digest, launches real
# FULL Chromium (never chrome-headless-shell) in a hardened non-root
# container (ops/phase10/container_check.py performs the in-container
# checks and prints the real /proc process-tree evidence), runs the focused
# P10-R1 gate tests inside the same hardened container, and confirms the
# containers and their process trees are gone afterward. Fails closed: any
# missing precondition or failed check aborts with a non-zero exit and no
# bypass.
#
# Scope: P10-R1 only. Does not implement or claim OS/container egress
# containment (P10-R2) and does not run the full Layer-2 matrix
# (docs/PHASE_10_GATE_RECOVERY_PLAN.md Sec3) -- only the minimal
# launch/navigation/cleanup smoke check required to validate this
# environment.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

BASE_IMAGE="mcr.microsoft.com/playwright/python"
EXPECTED_DIGEST="sha256:a9731514f24121d1dcd25d58d0a38146646d290a5998fd80d3e533e7b5e21c69"
CONTAINERFILE="ops/phase10/Containerfile.layer2"
IMAGE_TAG="aos-p10r1-layer2:playwright-1.61.0-noble"
CONTAINER_NAME="aos-p10r1-verify-$$"
SECCOMP_PROFILE="$(mktemp -t aos-p10r1-seccomp.XXXXXX.json)"

# The one hardening profile every P10-R1 container run uses. Never
# privileged, never host network/PID, no socket or host-project mount, no
# persistent profile; read-only root fs with narrow tmpfs only; all
# capabilities dropped; no-new-privileges; bounded memory/CPU/PIDs/fds/time.
HARDENED_RUN_FLAGS=(
    --rm
    --user 10001:10001
    --read-only
    --tmpfs /tmp:rw,nosuid,nodev,size=1g
    --tmpfs /run:rw,nosuid,nodev,size=64m
    --tmpfs /home/aos:rw,nosuid,nodev,size=512m
    --network none
    --pids-limit=256
    --cpus=2
    --memory=2g --memory-swap=2g
    --ulimit nofile=1024:1024
    --cap-drop=ALL
    --security-opt no-new-privileges
    --security-opt "seccomp=${SECCOMP_PROFILE}"
    --stop-timeout 30
)

fail() {
    echo "FAIL-CLOSED: $*" >&2
    exit 1
}

cleanup() {
    podman rm -f "${CONTAINER_NAME}" "${CONTAINER_NAME}-pytest" >/dev/null 2>&1 || true
    rm -f "${SECCOMP_PROFILE}"
}
trap cleanup EXIT

command -v podman >/dev/null 2>&1 \
    || fail "podman is not installed -- rootless Podman is a mandatory P10-R1 precondition"
command -v python3 >/dev/null 2>&1 \
    || fail "python3 is not installed -- needed to derive the tailored seccomp profile"

python3 - "${SECCOMP_PROFILE}" <<'PY'
import json
import sys
from pathlib import Path

from ops.phase10.seccomp_profile import SeccompProfileError, transform_chroot_rule

out = Path(sys.argv[1])
for candidate in (Path("/usr/share/containers/seccomp.json"), Path("/etc/containers/seccomp.json")):
    if candidate.exists():
        data = json.loads(candidate.read_text())
        break
else:
    raise SystemExit("FAIL-CLOSED: default Podman seccomp profile not found")

try:
    data = transform_chroot_rule(data)
except SeccompProfileError as exc:
    raise SystemExit(f"FAIL-CLOSED: could not prove safe chroot seccomp transformation: {exc}") from exc

out.write_text(json.dumps(data, sort_keys=True))
print("P10-R1 seccomp profile validated: exactly one unconditional chroot allow; all other rules preserved")
PY

echo "[1/9] Verifying rootless Podman..."
ROOTLESS="$(podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null || true)"
[ "${ROOTLESS}" = "true" ] \
    || fail "podman is not confirmed rootless (Host.Security.Rootless=${ROOTLESS:-unknown})"

echo "[2/9] Verifying pinned base image digest ${EXPECTED_DIGEST}..."
podman pull --quiet "${BASE_IMAGE}@${EXPECTED_DIGEST}" >/dev/null \
    || fail "could not pull the pinned base image digest"
ACTUAL_DIGEST="$(podman image inspect --format '{{.Digest}}' "${BASE_IMAGE}@${EXPECTED_DIGEST}" 2>/dev/null || true)"
[ "${ACTUAL_DIGEST}" = "${EXPECTED_DIGEST}" ] \
    || fail "pulled image digest '${ACTUAL_DIGEST}' does not match pinned '${EXPECTED_DIGEST}'"

echo "[3/9] Building the immutable verification image (source copied, not mounted; headless shell removed)..."
podman build --pull=never -f "${CONTAINERFILE}" -t "${IMAGE_TAG}" "${REPO_ROOT}" \
    || fail "image build failed"

echo "[4/9]-[7/9] Launching real FULL Chromium in the hardened, non-root, read-only, network-less container..."
podman run \
    --name "${CONTAINER_NAME}" \
    "${HARDENED_RUN_FLAGS[@]}" \
    "${IMAGE_TAG}" \
    || fail "container_check.py reported a failure inside the hardened container (see output above)"

echo "[8/9] Running the focused P10-R1 gate tests inside the hardened container..."
podman run \
    --name "${CONTAINER_NAME}-pytest" \
    "${HARDENED_RUN_FLAGS[@]}" \
    --entrypoint "" \
    -e AOS_BROWSER_P10R1_CONTAINER=1 \
    -e AOS_DATA_DIR=/tmp/aos-data \
    "${IMAGE_TAG}" \
    python -m pytest -q tests/test_browser_p10r1_environment.py \
    || fail "in-container P10-R1 gate tests failed"

echo "[9/9] Confirming the containers and any Chromium process tree are gone..."
STILL_PRESENT="$(podman ps -a --filter "name=aos-p10r1-verify-" --format '{{.Names}}' 2>/dev/null || true)"
[ -z "${STILL_PRESENT}" ] \
    || fail "a P10-R1 container is still present after --rm: ${STILL_PRESENT}"
LEFTOVER="$(pgrep -fa "conmon.*aos-p10r1-verify-" 2>/dev/null || true)"
[ -z "${LEFTOVER}" ] \
    || fail "a leftover conmon/container process remains on the host: ${LEFTOVER}"

echo "P10-R1 verification PASSED."
