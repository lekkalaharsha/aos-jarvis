# Phase 10 Gate Recovery Plan

Date: 2026-07-11
Author: Codex (recovery planner)
Status: Planning only. No implementation started.

Phase 10 is not passed. Phase 11 remains blocked. This plan does not modify
the approved Phase 10 contract and does not request an environmental exception.

Current verified facts:
- Focused suite: 177 passed, 5 skipped.
- Full suite: 741 passed, 5 skipped.
- Layer 2 opt-in: 2 passed, 5 errors (`TargetClosedError`).
- Layer-2 matrix is materially incomplete.
- No environmental exception has been approved.

## 1. Chromium-Capable Verification Environment

### Evaluation

| Option | Assessment | Use |
|---|---|---|
| Rootless Podman | Best fit on native Linux. Supports non-root containers, cgroup limits, read-only filesystems, internal networks, and CI parity without Docker socket exposure. Needs host user namespaces/subuid/subgid configured. | Recommended final-gate environment. |
| Rootless Docker | Viable fallback. Similar non-root host posture, but rootless networking behavior varies more by distro/CI runner and Docker Desktop introduces a VM abstraction. | Acceptable only if Podman is unavailable and network isolation is proven by tests. |
| Prebuilt Playwright Linux image | Required base image strategy. Use a pinned Playwright/Python image with Chromium system libraries already present; pin by digest for final gate. | Use as base for either Podman or Docker. |
| WSL2 | Useful developer reproduction path if Podman works inside the WSL2 distro. Kernel/process behavior is close enough for preflight, but not ideal as the final independent gate because host integration and filesystem/network behavior vary. | Developer smoke only, not the authoritative gate. |
| Native Linux | Best host target. Gives the most direct `/proc`, user namespace, seccomp, cgroup, and rootless container behavior. | Required for authoritative final gate. |
| Windows/macOS native | Not suitable for final Phase 10 gate. Chromium sandbox, `/proc` process inspection, network namespace behavior, and cgroup enforcement do not match the Linux contract. Docker Desktop on these hosts can be used only as a developer approximation. | Not final-gate authoritative. |

### Recommended Environment

Use native Linux CI or a native Linux workstation with rootless Podman and a
pinned Playwright image. The final gate should run inside a purpose-built
container image based on `mcr.microsoft.com/playwright/python:v1.61.0-noble`
or an equivalent pinned-by-digest image containing the Playwright 1.61.0
Chromium browser and system dependencies.

Host prerequisites:
- Linux kernel with user namespaces enabled.
- cgroup v2 enabled.
- Rootless Podman with `netavark`/`aardvark-dns` or equivalent rootless
  networking support.
- `/etc/subuid` and `/etc/subgid` entries for the runner user.
- Seccomp enabled.
- No need for privileged containers, host networking, host PID namespace,
  Docker socket, or host root mounts.

Non-root execution model:
- Container image creates user `aos` with fixed UID/GID, for example
  `10001:10001`.
- `pip install -e .[dev,browser]` runs at image build time.
- Tests run as `aos`, never as container root.
- `AOS_DATA_DIR` points to an isolated writable temp directory.
- Browser profile directories are task-temp only and deleted after tests.

Resource limits:
- CPU: `--cpus=2`.
- Memory: `--memory=4g --memory-swap=4g`.
- PIDs: `--pids-limit=512`.
- Disk/tmpfs: `/tmp` 2 GB, `/run` 128 MB, browser data 2 GB.
- Test timeout: outer CI timeout 20 minutes for Layer 2; per-task timeout
  remains the contract value unless a test deliberately uses a shorter value.
- File descriptors: set with container runtime `--ulimit nofile=1024:1024`.

Filesystem:
- `--read-only`.
- Writable paths only:
  - `/tmp`
  - `/run`
  - `/work/.tmp`
  - `/home/aos/.cache/ms-playwright` if the image does not already bake
    browser binaries; final gate should bake them and avoid this write.
- No host home mount.
- No host project mounts in final CI; source is copied into the image or a
  read-only checked-out workspace is mounted with only `.tmp` writable.
- No persistent browser profile.

Forbidden runtime flags:
- No `--privileged`.
- No `--network=host`.
- No `--pid=host`.
- No Docker/Podman socket mount.
- No broad host mounts.
- No persistent profile volume.

### Proposed Containerfile

This is a plan for a future file, not implemented here.

```Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin aos
WORKDIR /work
COPY pyproject.toml ./
COPY aos ./aos
COPY tests ./tests
COPY docs ./docs
RUN python -m pip install --upgrade pip \
    && python -m pip install -e '.[dev,browser]' \
    && python -m playwright install chromium
USER 10001:10001
ENV PYTHONUNBUFFERED=1
ENV AOS_DATA_DIR=/work/.tmp/aos-data
CMD [".venv/bin/python", "-m", "pytest", "-q", "-rs", "tests/test_browser_integration_real.py"]
```

If the image uses system Python rather than `.venv`, use `python -m pytest`
consistently. The final implemented image should pin the base image by digest.

### Build/Run Commands

Rootless Podman build:

```bash
podman build \
  --pull=never \
  -f ops/phase10/Containerfile.layer2 \
  -t aos-p10-layer2:playwright-1.61.0 .
```

Rootless network topology for final gate:

```bash
podman network create --internal aos-p10-browser-net
podman network create --internal aos-p10-fixture-net
podman network create aos-p10-egress-net
```

Run static/focused/default verification in the image:

```bash
podman run --rm \
  --user 10001:10001 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --tmpfs /run:rw,nosuid,nodev,size=128m \
  --pids-limit=512 \
  --cpus=2 \
  --memory=4g --memory-swap=4g \
  --ulimit nofile=1024:1024 \
  --cap-drop=ALL \
  --security-opt no-new-privileges \
  -e AOS_DATA_DIR=/tmp/aos-data \
  aos-p10-layer2:playwright-1.61.0 \
  python -m pytest -q -rs
```

Run required Layer 2:

```bash
podman run --rm \
  --user 10001:10001 \
  --network aos-p10-browser-net \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --tmpfs /run:rw,nosuid,nodev,size=128m \
  --pids-limit=512 \
  --cpus=2 \
  --memory=4g --memory-swap=4g \
  --ulimit nofile=1024:1024 \
  --cap-drop=ALL \
  --security-opt no-new-privileges \
  -e AOS_BROWSER_RUN_REAL_TESTS=1 \
  -e AOS_DATA_DIR=/tmp/aos-data \
  aos-p10-layer2:playwright-1.61.0 \
  python -m pytest -q -rs tests/test_browser_integration_real.py
```

CI reproduction:
- Build the pinned image once per commit.
- Run default full suite in the image.
- Run Layer 2 in the network-isolated topology.
- Archive pytest output, `aos audit verify` output, Chromium launch logs, and
  process/orphan inspection evidence.
- Treat any Layer-2 skip/error as gate failure.

## 2. Real Egress Enforcement

The current AOS validating proxy is necessary but not sufficient by itself.

Explicit distinction:
- Proxy policy enforcement: AOS proxy validates requested destinations
  against exact approved `(host, port)` policy, resolves DNS, blocks private
  and metadata IPs, blocks disallowed redirects, and denies by default.
- Chromium proxy configuration: Chromium receives `--proxy-server=<proxy>`.
  This routes compliant browser requests through the proxy but is not an
  OS-level guarantee if Chromium or a renderer is compromised.
- OS/container-level network enforcement: the browser process/container must
  have no route to anything except the proxy listener. This is the control
  that proves app-check bypasses and unhandled browser network surfaces do not
  become direct egress.
- If application checks are bypassed: OS/container policy still permits only
  proxy connections; proxy policy denies non-approved destinations.
- If renderer/browser is compromised: Chromium sandbox plus container network
  isolation limit the compromise. A renderer escape remains a residual risk;
  the plan does not claim proxy configuration alone stops a process with raw
  OS network access.

### Default-Deny Model

Required topology:

```text
browser test container
  network: browser-net only
  can connect only to: validating proxy on browser-net

AOS validating proxy container/process
  network: browser-net + fixture-net/egress-net
  policy: default deny, exact approved targets only

fixture containers
  network: fixture-net only
```

Direct browser egress is blocked by container networking, not by trusting
Chromium. The browser container is attached only to `browser-net`. Approved
fixture/target services are not attached to `browser-net`; they are reachable
only from the proxy on `fixture-net` or from the proxy's controlled egress
network.

Proxy validation rules:
- Accept only `CONNECT host:port` or HTTP requests whose canonical host/port
  match the current task allowlist.
- Resolve DNS inside the proxy, not the browser, and reject any resolved IP
  that is loopback, private, link-local, multicast, metadata-shaped,
  unspecified, reserved, or otherwise non-global unless the test explicitly
  models an allowed local fixture through a special fixture-only policy.
- Re-resolve and revalidate on redirects.
- Enforce redirect depth.
- Deny WebSocket/EventSource upgrade targets unless approved by the same
  host/port policy.
- Log only opaque target IDs/hashes and typed denial reasons, not raw secrets.

Real Chromium tests must prove:
- Browser configured with proxy can reach an approved fixture through proxy.
- Browser cannot reach the approved fixture directly by IP/host because there
  is no route.
- Browser cannot reach a disallowed fixture through proxy; proxy returns deny.
- A page script, iframe, worker, service worker attempt, WebSocket,
  EventSource, WebRTC, prefetch, and popup all fail closed when targeting a
  non-approved service.

## 3. Layer-2 Completion Matrix

| Test ID | Threat/control proved | Local fixture design | Required environment | Pass condition |
|---|---|---|---|---|
| L2-DOM-01 | Engine-derived password denial | HTML form with `<input type=password>` and accessible label | Chromium-capable rootless Linux container | Fill denied before approval prompt; no value written. |
| L2-DOM-02 | OTP/token denial | Inputs with `autocomplete=one-time-code`, token labels, and recovery/security labels | Same | Denied before approval; audit contains no raw value. |
| L2-SSRF-01 | Loopback/private-IP app denial | Task attempts `127.0.0.1`, RFC1918, metadata IP URLs | Same | Denied before navigation; fixture sees no request. |
| L2-EGRESS-01 | Proxy policy allow path | Approved fixture reachable only via proxy | Browser-net/proxy/fixture-net topology | Chromium loads approved page through proxy. |
| L2-EGRESS-02 | Direct-egress bypass blocked | Test harness bypasses app URL validator and asks Chromium for fixture IP directly | Same | Connection fails at container network layer; fixture sees no direct request. |
| L2-EGRESS-03 | Proxy deny path | Disallowed fixture target through proxy | Same | Proxy returns deny; Chromium navigation fails; denial audited. |
| L2-REDIR-01 | Same-domain redirect | Fixture redirects `/a` to same host `/b` | Same | Followed without extra cross-domain approval; depth accounted. |
| L2-REDIR-02 | Cross-enrolled-domain redirect approval | Fixture redirects from approved A to separately enrolled B | Same | Denied without fresh redirect approval; succeeds with exact redirect approval. |
| L2-REBIND-01 | DNS rebinding containment | Test DNS/proxy fixture returns public IP first, private IP second | Same with controlled DNS/proxy resolver | Proxy/app revalidation denies private second answer; no private connection. |
| L2-FRAME-01 | Iframe network coverage | Page embeds iframe to disallowed fixture | Same | Iframe request denied by proxy/app guard; fixture sees no success. |
| L2-POPUP-01 | Popup/new page coverage | Page opens popup to disallowed fixture | Same | Popup closed/denied; tab cap and audit verified. |
| L2-WORKER-01 | Dedicated/shared worker fetch coverage | Worker script fetches disallowed target | Same | Request denied; worker cannot exfiltrate. |
| L2-SW-01 | Service worker disabled/blocked | Page registers service worker that fetches target | Same | Registration or fetch blocked; no successful service-worker request. |
| L2-WS-01 | WebSocket coverage | Page opens `ws://`/`wss://` to disallowed fixture | Same | Connection denied; server records no accepted app connection. |
| L2-SSE-01 | EventSource coverage | Page opens EventSource to disallowed fixture | Same | Connection denied. |
| L2-WRTC-01 | WebRTC disabled | Page attempts ICE gathering/data channel | Same | No non-proxied UDP/ICE candidate to external target; launch config verified. |
| L2-PREFETCH-01 | Prefetch/prerender disabled | Page contains prefetch/prerender links to disallowed target | Same | No speculative request reaches fixture. |
| L2-DL-01 | Download cap behavior | Fixture serves over-limit file with and without Content-Length | Same | Task denies; partial data absent or deleted; limitation noted if Playwright buffers first. |
| L2-TIMEOUT-01 | Task timeout cleanup | Fixture hangs navigation past short test timeout | Same | Task timed out; browser/proxy/process tree gone. |
| L2-CRASH-01 | Browser crash cleanup | Test kills Chromium child mid-navigation | Same with `/proc` access inside container | Failure audited; no orphan Chromium/proxy remains. |
| L2-CANCEL-01 | Cancellation cleanup | Test sends Ctrl+C/SIGINT-equivalent during navigation | Same | Task cancelled; exactly one terminal task event; no orphan. |
| L2-CLEAN-01 | Normal cleanup | Successful task with proxy and fixture | Same | Profile directory deleted; no Chromium/proxy process remains. |
| L2-SANDBOX-01 | Post-launch sandbox verification | Inspect real Chromium process tree and `/proc/*/status` | Native Linux container with `/proc` for own namespace | No forbidden flags; expected sandbox/seccomp state detected; launch fails if check cannot verify. |

## 4. Remaining Known Design Gaps

| Item | Classification | Plan |
|---|---|---|
| Download cap occurs after full `save_as` | Requires Human Owner contract decision unless a different download primitive is adopted | Do not describe current behavior as mid-stream enforcement. Either implement a streaming download path outside Playwright download API, or amend contract to accept post-download deletion with residual disk/bandwidth risk. |
| Upload path reopen / remaining TOCTOU | Requires Human Owner contract decision or architecture change | Private snapshot staging narrows, not eliminates, path reopen. Same-fd upload likely requires a different browser/upload primitive or contract acceptance of the residual. |
| Post-launch sandbox/process inspection | Technically fixable now, but proof requires Chromium-capable Layer 2 | Keep `/proc` tracker, add real Chromium process-tree assertions in Layer 2. |
| Process-tree cleanup proof | Technically fixable now, proof requires Layer 2 | Add timeout/crash/cancel real-process tests and assert no matching Chromium/proxy processes remain. |
| Scope of browser compromise protection | Requires architecture clarity, not contract weakening | Proxy config protects compliant Chromium; OS/container network isolation protects app-check bypass; Chromium sandbox/container containment are the renderer-compromise controls. Do not claim protection against host-level compromise. |
| Cross-platform support expectations | Requires Human Owner contract decision | Recommend Linux-only authoritative Phase 10 gate. WSL2 may be developer preflight; Windows/macOS native are unsupported for final gate. |

## 5. Human Owner Decisions

| Decision | Options | Security consequence | Recommendation |
|---|---|---|---|
| Authoritative Layer-2 environment | A. Native Linux rootless Podman CI/workstation. B. Rootless Docker. C. WSL2/Docker Desktop. | A gives strongest match to contract. B can work if network proof passes. C is weaker and should not be authoritative. | Choose A. |
| Network enforcement architecture | A. Browser network can reach only AOS validating proxy; proxy reaches fixtures/approved targets. B. Proxy config only. | A proves app-check-bypass and most unhandled surfaces. B leaves direct egress if Chromium is compromised or proxy config is bypassed. | Choose A. |
| Download cap residual | A. Implement streaming/alternate primitive. B. Amend contract to accept post-download deletion residual. | A meets current contract. B accepts disk/bandwidth exposure. | Choose A if feasible; otherwise explicit contract amendment required. |
| Upload TOCTOU residual | A. Different primitive that avoids path reopen. B. Accept private snapshot staging residual. | A stronger. B leaves a small Playwright path-open residual. | Decide explicitly; do not call B elimination. |
| Final-gate platform support | A. Linux-only authoritative final gate. B. Cross-platform final gate. | A matches sandbox/network/process contract. B likely weakens or fragments the gate. | Choose A. |

No option recommends weakening the Layer-2 gate because this sandbox lacks
dependencies.

## 6. Execution Plan

### P10-R1: Environment Image and Reproducible Launch

Scope:
- Add the future container image definition and CI job.
- Use pinned Playwright/Chromium dependencies.
- Run as non-root with read-only filesystem and bounded writable tmpfs paths.

Acceptance criteria:
- `python -m pytest -q -rs` reproduces the default suite inside the image.
- `AOS_BROWSER_RUN_REAL_TESTS=1 python -m pytest -q -rs tests/test_browser_integration_real.py`
  launches Chromium instead of failing with `TargetClosedError`.
- No privileged mode, host networking, host PID, Docker socket, broad host
  mounts, or persistent profile.

Stop conditions:
- Chromium still cannot launch.
- Container requires privileged mode or host namespace access.
- Tests need live public internet.

### P10-R2: OS/Container Egress Enforcement

Scope:
- Implement the browser-net/proxy/fixture-net topology.
- Ensure browser process can connect only to AOS proxy.
- Ensure proxy validates exact approved host/port and DNS/IP results.

Acceptance criteria:
- Real Chromium reaches approved fixture through proxy.
- Direct Chromium connection to fixture IP/host fails at network layer.
- Disallowed proxy target receives a proxy deny.
- App-check-bypass test still cannot connect directly.

Stop conditions:
- Browser has any direct route to fixture/egress network.
- Proxy policy cannot inspect DNS/IP/redirect targets.
- Verification depends only on Chromium `--proxy-server`.

### P10-R3: Layer-2 Matrix Implementation

Scope:
- Implement all matrix tests in Section 3.
- Use only local fixture containers/services.
- Keep Layer 1 deterministic and DNS-free.

Acceptance criteria:
- Every required Layer-2 row passes with real Chromium.
- No required skip remains in the final-gate environment.
- Audit and process cleanup assertions pass.

Stop conditions:
- A required browser surface cannot be observed or asserted.
- A test needs external internet.
- A limitation maps to a contract decision rather than implementation.

### P10-R4: Real Verification and Fresh Codex Gate

Scope:
- Run full default suite, focused browser suite, complete Layer 2, compileall,
  Ruff, `git diff --check`, audit verify, CLI smoke, and static scans in the
  reproducible environment.
- Request fresh independent Codex final gate only after all required runs pass.

Acceptance criteria:
- Full suite passes.
- Layer 2 passes with zero required skips/errors.
- Evidence artifacts are archived.
- B010 can be reviewed for closure by an independent gate.

Stop conditions:
- Any required Layer-2 test skips/errors.
- Any containment proof relies on assertion instead of real Chromium behavior.
- Human Owner has not decided required residual-risk items.

## Final Recovery Recommendation

Recommended architecture: native Linux rootless Podman final-gate environment
using a pinned Playwright image, a non-root read-only runner, and a
default-deny browser network where Chromium can reach only an AOS-controlled
validating proxy. The proxy is the policy layer; the container network is the
direct-egress enforcement layer.

Exact next implementation phase: P10-R1, build the reproducible Chromium-capable
verification image and prove real Chromium launches under the final-gate
runtime constraints.

Unresolved Human Owner decisions: authoritative Linux/rootless environment,
network-enforcement topology, download-cap residual, upload-TOCTOU residual,
and final-gate platform support.

Phase 10 is not passed. Phase 11 remains blocked.

## 7. P10-R1 Implementation (2026-07-12, Claude Sonnet)

Human Owner approved P10-R1 only (2026-07-12 instruction): rootless
Podman, fixed non-root UID/GID, the pinned `mcr.microsoft.com/playwright/
python:v1.61.0-noble` image pinned by immutable digest, Linux as the
initial gate platform (WSL2 acceptable if it provides equivalent Linux/
Podman behavior), non-root Chromium/AOS. This section records what was
built. It does not authorize P10-R2, any contract amendment, or Phase 11.

### What was built

- `ops/phase10/Containerfile.layer2` -- pins the base image by resolved
  digest `sha256:a9731514f24121d1dcd25d58d0a38146646d290a5998fd80d3e533e7b5e21c69`
  (resolved 2026-07-12 from the registry's `v1.61.0-noble` manifest list;
  the tag itself is mutable, the digest is not). Creates a fixed
  `aos:10001:10001` user, `COPY`s `pyproject.toml`, `aos/`, and
  `ops/phase10/{container_check.py,fixtures}` into the image (no `VOLUME`,
  no host repo bind mount at runtime), installs only the thin
  `.[browser]` Python extra (Chromium itself is already baked into the
  pinned base image at the matching Playwright version -- no
  `playwright install` re-download), and switches to the non-root user
  before `ENTRYPOINT`.
- `ops/phase10/container_check.py` -- the in-container reproducible check.
  Reuses the existing production `aos.browser.engine.{PlaywrightEngineFactory,
  BrowserProcessTracker, build_launch_args}` and `aos.browser.sandbox.
  verify_sandbox` unchanged (no browser production code was modified for
  P10-R1) to: confirm the verification process itself is non-root, confirm
  the real kernel sandbox preconditions, launch real Chromium with the
  existing fixed launch-argument list (no `--no-sandbox` or any forbidden
  flag -- enforced by the existing `assert_launch_args_safe` choke point),
  read the launched Chromium process's own `/proc/<pid>/status` `Uid:`
  line to confirm it is not root, confirm `BrowserProcessTracker.
  sandbox_verified()` (no forbidden flag in `/proc/<pid>/cmdline`, Seccomp
  active) and `handle.verify_post_launch_sandbox()`, navigate one static
  local `file://` fixture (`ops/phase10/fixtures/nav_fixture.html` -- no
  network involved, matching "no host network" trivially and deferring all
  egress work to P10-R2), read back its title, close Chromium through the
  existing bounded-cleanup `close()` path, and confirm
  `BrowserProcessTracker.pids()` is empty afterward. Every check fails
  closed (`FailClosed`, a `SystemExit` subclass, non-zero exit, no bypass
  flag) rather than degrading to a warning.
- `ops/phase10/verify_p10r1.sh` -- the host-side reproducible command.
  Fails closed if `podman` is not installed, if Podman does not report
  `Host.Security.Rootless=true`, or if the pulled base image's digest does
  not match the pinned digest. Builds the image, then runs it with
  `--user 10001:10001 --read-only`, narrow `tmpfs` at `/tmp` (1g),
  `/run` (64m), and `/home/aos` (512m) only, `--network none`, no
  `--privileged`, no `--pid=host`, no Docker/Podman socket mount, no host
  project mount, `--cap-drop=ALL`, `--security-opt no-new-privileges`,
  `--pids-limit=256`, `--cpus=2`, `--memory=2g --memory-swap=2g`,
  `--ulimit nofile=1024:1024`, and `--stop-timeout 30`. After the
  container exits it confirms via `podman ps -a` that the container is
  gone and via `pgrep` that no leftover `conmon` process for it remains
  on the host.
- `tests/test_browser_p10r1_environment.py` -- 8 deterministic tests (no
  Podman/Chromium required, run in the normal suite everywhere) asserting
  the digest pin, non-root `USER`, no host-repo `VOLUME`, and every
  required/forbidden flag in `verify_p10r1.sh`, plus unit coverage of
  `container_check.py`'s `read_uid()` helper. One additional test,
  `test_container_check_passes_inside_hardened_container`, is skipped
  unless `AOS_BROWSER_P10R1_CONTAINER=1` -- it is meant to run only inside
  the built container and calls `container_check.main()` directly.

Explicitly not done in this pass (out of P10-R1 scope per the Human
Owner's instruction): no OS/container egress enforcement or validating-
proxy network topology (P10-R2), no completion of the Layer-2 matrix in
Sec3 above (P10-R3) beyond the minimal launch/navigation/cleanup smoke
check above, no `PHASE_CONTRACT.md` amendment, no commit.

### Verification performed

- `python -m compileall -q ops/phase10 aos tests` -- clean.
- `ruff check ops/phase10/container_check.py tests/test_browser_p10r1_environment.py` -- all checks passed.
- `pytest -q tests/test_browser_p10r1_environment.py` -- **8 passed, 1 skipped** (the in-container-only test, correctly skipped outside the container).
- Full suite: `pytest -q -rs` -- **749 passed, 6 skipped** (was 741 passed, 5 skipped before this change; +8 new passing P10-R1 tests, +1 new correctly-skipped in-container-only test; every prior test still passes).
- `git diff --check` -- clean.
- `./ops/phase10/verify_p10r1.sh` was run in this implementation sandbox and correctly failed closed at step 1 with `FAIL-CLOSED: podman is not installed -- rootless Podman is a mandatory P10-R1 precondition`, exit code 1. This is disclosed as the exact environmental blocker below, not weakened or bypassed.

### Disclosed environmental blocker

This implementation sandbox (WSL2, Ubuntu 26.04 "Resolute Raccoon",
kernel `6.18.33.1-microsoft-standard-WSL2`, systemd running as PID 1,
cgroup v2 controllers present, `/etc/subuid`/`/etc/subgid` already
configured for the invoking user) does **not** have `podman` installed.
`apt-cache policy podman` shows it is installable (candidate
`5.7.0+ds2-3build1` from the `resolute/universe` repository) but
installing it requires `sudo`, and this session has no passwordless sudo
(`sudo -n true` fails with "interactive authentication is required"). No
attempt was made to prompt for or otherwise obtain a sudo password. The
pinned base image digest was independently resolved and confirmed reachable
over the network (`curl` against the MCR registry's v2 manifest API, HTTP
200, `Docker-Content-Digest: sha256:a9731514f24121d1dcd25d58d0a38146646d290a5998fd80d3e533e7b5e21c69`),
so the digest pinned into `Containerfile.layer2` is confirmed correct and
current, even though the image could not be pulled or built here.

This is a narrower, more concretely bounded blocker than the "real
Chromium cannot launch in this sandbox at all" constraint that blocked
every prior Phase 10 remediation round: it is specifically "Podman is not
yet installed in this session," not a missing-shared-library or kernel
incompatibility. The host's own kernel/cgroup/subuid posture appears
consistent with what rootless Podman needs. Closing this blocker only
requires installing `podman` (e.g. `sudo apt-get install -y podman`) in an
environment where that command can run, then executing
`./ops/phase10/verify_p10r1.sh` from the repository root.

### Final status

**P10-R1 IMPLEMENTED — AWAITING INDEPENDENT ENVIRONMENT VERIFICATION.**

Phase 10 is not COMPLETE. P10-R2, the remaining Layer-2 matrix (P10-R3),
and Phase 11 remain not started and not authorized by this pass. Next
worker: an operator or reviewer with `sudo`-capable access to a Linux (or
equivalent-Podman-behavior WSL2) host should install `podman` and run
`./ops/phase10/verify_p10r1.sh` to independently confirm the reproducible
environment actually launches real, sandboxed, non-root Chromium and
cleans up completely, then report the result back into `HANDOFF.md`.
