# Platform UI pipeline v2

Build the image. Run unit tests. Run Playwright E2E tests.
Extraction and test steps run as `1000:1000`, without privilege escalation.

## Migration Guide

V1 is deprecated. All consumers must move to v2. V1 keeps its legacy behavior;
security changes live in v2.

1. Update **both PR and push** pipeline references to v2.
2. Make setup scripts work without root. Bake system packages into the test image.
   Setup now runs inside `run-unit-tests`, using `unit-test-image`; move any
   overrides from the old `workspace-setup` task there. Check script quoting:
   v2 executes `workspace-setup-script` through `bash -c`.
3. Set workspace group and storage as shown below.
4. Check secret names and set `e2e-hcc-env-url` explicitly if needed.
5. Set `run-app-command` and `run-app-args` to start the application. V2 runs
   the executable directly, so shell-less images work. The old `run-app-script`
   parameter remains for manifest compatibility but is ignored. Serve the app
   on `e2e-app-port` (default **8000**) and supply a routes ConfigMap with a
   nonempty `routes` key. There is no chrome-dev sidecar; remove old chrome
   routes using the [sidecar migration guide](./MIGRATION.md).
6. Run both triggers. Check extraction, dependency installation, and all tests.

### Pipeline reference

After merge, use the upstream repository. Pin a merged commit for reproducible runs:

```yaml
spec:
  pipelineRef:
    resolver: git
    params:
      - name: url
        value: https://github.com/RedHatInsights/konflux-pipelines.git
      - name: revision
        value: main # Or a pinned upstream commit containing the v2 fixes.
      - name: pathInRepo
        value: pipelines/platform-ui/docker-build-run-all-tests-v2.yaml
```

For annotation references, update the file URL and use Pipeline name
`docker-build-v2`. Bundle users must select a bundle containing v2 through the
[bundles resolver](https://tekton.dev/docs/pipelines/bundle-resolver/).

### Application startup

For example, start Caddy directly in a shell-less application image:

```yaml
params:
  - name: run-app-command
    value: caddy
  - name: run-app-args
    value:
      - run
      - --config
      - /etc/caddy/Caddyfile
      - --adapter
      - caddyfile
```

To run a shell script, invoke the shell explicitly, for example with command
`/bin/bash` and args `[-c, "npm run start"]`.

### Workspace

Match `fsGroup` to your workspace's writable group, permitted by cluster policy.
**Do not assume it is 1000.** Storage must support the volume permissions.
Merge these settings into the existing PipelineRun:

```yaml
spec:
  taskRunSpecs:
    - pipelineTaskName: run-unit-tests
      podTemplate:
        securityContext:
          fsGroup: 1005770000 # Replace with your workspace group.
    - pipelineTaskName: run-e2e-tests
      podTemplate:
        securityContext:
          fsGroup: 1005770000 # Same workspace group.
  workspaces:
    - name: workspace
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources:
            requests:
              storage: 5Gi # Size for your app.
```

Astro passed with this group and capacity on commit `6dd7133` during development.
Validate your own run when adopting the merged pipeline.
Keep existing workspace bindings; resizing a claim template does not resize an
existing PVC.

Tests run in `/var/workdir`. For a subdirectory, `cd` in your scripts;
`path-context` only controls the build. Extraction, setup, and unit tests also
use `/var/workdir` as `HOME`, so npm caches consume workspace storage.
The E2E task needs write access to both the workspace and `/config`.

### Secrets

Set `e2e-credentials-secret` to an existing Secret. Its keys become environment
variables in the E2E and proxy containers. **Names stay unchanged.** Use keys
like `CHROMATIC_TOKEN`, not `chromatic-token`.

V2 explicitly maps these legacy keys:

| Secret key | Variable |
| --- | --- |
| `e2e-user` | `E2E_USER` |
| `e2e-password` | `E2E_PASSWORD` |
| `e2e-stage-actual-hostname` | `STAGE_ACTUAL_HOSTNAME` |

`HCC_ENV_URL` comes from the **`e2e-hcc-env-url` parameter**, not the Secret.
Its default is `https://console.stage.redhat.com`. Keep secret values out of logs.

## Build-target selection

The optional `target-stage` parameter forwards `--target` to the Buildah task,
selecting a named stage in your Dockerfile. Default is empty, which preserves
the Dockerfile's last stage (backward-compatible).

```yaml
spec:
  params:
    - name: target-stage
      value: deploy   # Select the "deploy" stage from Dockerfile.hermetic
```

**Key rules:**
- Target selection is independent of hermetic mode. Setting `target-stage` does
  not enable or disable build isolation.
- `hermetic` remains `"false"` by default. Only explicit `hermetic: "true"`
  enables network isolation.
- `prefetch-input` alone does not enable hermetic execution.
- Empty target preserves the Dockerfile default; the sast-coverity-check task
  also receives the target to scan the correct stage.

### Examples

| Scenario | `hermetic` | `prefetch-input` | `target-stage` | Result |
| --- | --- | --- | --- | --- |
| Existing non-hermetic consumer | `"false"` (default) | `""` (default) | `""` (default) | Default Dockerfile output, unchanged |
| Explicit target without hermetic | `"false"` | `""` | `deploy` | Builds deploy stage, network available |
| Hermetic deploy image with npm prefetch | `"true"` | `npm` | `deploy` | Hermetic build of deploy stage |
| Hermetic artifact image (SC components) | `"true"` | `npm` | `""` | Default stage (artifact in Dockerfile.hermetic) |

## Immutable E2E image reference

The E2E task now receives the built image as `IMAGE_URL@IMAGE_DIGEST` rather
than just `IMAGE_URL`. This ensures E2E tests run against the exact built image
by digest, not a mutable tag. The `IMAGE_DIGEST` and `APPLICATION_IMAGE`
environment variables are available inside the test runner for diagnostics and
assertions.

## Browser and readiness configuration

### Playwright base URL

Set `e2e-base-url` to forward `PLAYWRIGHT_BASE_URL` to the test runner:

```yaml
spec:
  params:
    - name: e2e-base-url
      value: "http://localhost:1337"
```

When omitted (default), existing consumer behavior is preserved. The parameter
is carried through an internal variable (`_E2E_BASE_URL`) and only exported as
`PLAYWRIGHT_BASE_URL` when non-empty. This prevents an empty explicit env entry
from overriding `PLAYWRIGHT_BASE_URL` values supplied by `envFrom` or the runner
image.

### Readiness checks

The proxy sidecar waits for the application to become ready before starting.
Configure the check with:

| Parameter | Default | Description |
| --- | --- | --- |
| `e2e-app-port` | `8000` | Port the application serves on |
| `e2e-readiness-path` | `""` | Path appended to the app URL for readiness (e.g. `/api/v1/health`) |
| `e2e-readiness-timeout` | `120` | Maximum seconds to wait before failing |
| `e2e-proxy-readiness-url` | `""` | Browser-facing URL to probe for proxy readiness (e.g. `https://stage.foo.redhat.com:1337/`) |

The readiness check now uses the configured port instead of the previously
hardcoded port 8000. Startup failures propagate to a failing check.

#### Proxy readiness

When `e2e-proxy-readiness-url` is set, the E2E test step waits for the proxy to
respond at that URL before running the consumer script. The URL must use the
actual hostname the proxy serves (e.g. `https://stage.foo.redhat.com:1337/`)
so that TLS SNI and HTTP Host match. If the proxy does not respond within
`e2e-readiness-timeout` seconds, the task **fails** and the timeout propagates
through diagnostics and exit-code handling.

When omitted (default), the proxy readiness check is skipped entirely, preserving
existing consumer behavior.

**Hostname resolution**: The hostname in the URL must resolve to `127.0.0.1`
inside the pod (all containers share a network namespace). Add a `hostAliases`
entry to the PipelineRun:

```yaml
spec:
  taskRunSpecs:
    - pipelineTaskName: run-e2e-tests
      podTemplate:
        hostAliases:
          - ip: "127.0.0.1"
            hostnames:
              - "stage.foo.redhat.com"
```

#### Proxy readiness scenarios

| Configuration | Behavior |
| --- | --- |
| `e2e-proxy-readiness-url` omitted | No proxy check. Consumer script runs immediately after image diagnostics. |
| URL set, proxy healthy | Probe succeeds within timeout. Consumer script runs. |
| URL set, proxy unavailable | Probe times out. Task fails with exit code 1 and diagnostics showing the timeout. |

## Diagnostic and artifact retention

Test diagnostics (exit code, image reference, test-results and playwright-report
directory sizes) are logged after every E2E run, including failures.

### OCI artifact upload

After each E2E run the pipeline archives Playwright reports, traces, and
screenshots (excluding credentials and authentication-state files) and uploads
them as an OCI trusted artifact. The upload URI is derived from the build
`output-image` with an `.e2e-results` suffix.

The uploaded artifact URI is exposed as the `E2E_ARTIFACTS_URI` task result.

### Retrieving artifacts

The `E2E_ARTIFACTS_URI` result contains a trusted-artifact URI
(`oci:<repository>@sha256:<digest>`). This is an OCI blob reference, not a
directly pullable manifest. Retrieve artifacts using one of these methods:

```bash
# Method 1 — trusted-artifacts CLI (recommended)
# The `use` command extracts the archive to the destination directory.
build-trusted-artifacts use <E2E_ARTIFACTS_URI>=/tmp/e2e-output

# Method 2 — oras blob fetch (manual)
# Strip the "oci:" prefix, then fetch and extract the blob.
URI="<E2E_ARTIFACTS_URI>"
REF="${URI#oci:}"
oras blob fetch "${REF}" --output - | tar -xzf - -C /tmp/e2e-output

# The archive contains:
#   metadata.json          — exit code and timestamp
#   playwright-report/     — HTML report (if generated)
#   test-results/          — traces and screenshots (if generated)
```

Credentials and authentication-state files (`storageState*`, `.auth/`,
`credentials*`, `auth.json`) are excluded automatically.

The upload step uses `onError: continue` — if artifact upload fails, it does
not mask the original test outcome. The `propagate-exit-code` step always
reports the real test exit code.

### Consumer script isolation

The consumer's `e2e-tests-script` runs in a separate shell process. This ensures
that `set -e` or explicit `exit` in the consumer script does not bypass
diagnostic collection or artifact upload. The original exit code is preserved and
propagated after post-test steps complete.

## Troubleshooting

- **Permission denied:** Compare `id` groups with
  `stat -c '%u:%g %a %n' /var/workdir`. Set the matching permitted `fsGroup`.
- **Cannot utime / change mode on `.`:** Use a revision with the archive-root
  exclusion fix (`TAR_OPTIONS=--no-recursion --anchored --exclude=.`).
- **ENOSPC:** Check `df -h` and `df -i` on `/var/workdir`. Increase capacity if
  needed; dependencies and caches share this volume.
- **Missing secret variable:** Check the exact key name. No automatic renaming.

If extraction fails, setup and tests are skipped. Collect any filesystem
diagnostics before extraction, using its identity.

See the [pipeline YAML](./docker-build-run-all-tests-v2.yaml) for all parameters
and defaults. The readiness check uses `e2e-app-port`; keep it aligned with the
application listener and the target port in the proxy routes ConfigMap.

## Learning Resources adoption

[RHCLOUD-52264](https://redhat.atlassian.net/browse/RHCLOUD-52264) /
[PR #377](https://github.com/RedHatInsights/learning-resources/pull/377) can
consume this pipeline revision to test hermetic builds with the deploy target:

```yaml
spec:
  params:
    - name: hermetic
      value: "true"
    - name: prefetch-input
      value: npm
    - name: target-stage
      value: deploy
    - name: dockerfile
      value: build-tools/Dockerfile.hermetic
```

This requires [RHCLOUD-52307](https://redhat.atlassian.net/browse/RHCLOUD-52307)
/ [PR #451](https://github.com/RedHatInsights/insights-frontend-builder-common/pull/451)
to be merged first, providing the `deploy` target in `Dockerfile.hermetic`.

Consumer-specific Playwright coverage, candidate-asset assertions, and hermetic
provenance verification are coordinated through RHCLOUD-52264.
