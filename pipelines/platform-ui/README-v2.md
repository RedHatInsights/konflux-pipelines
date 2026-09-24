# Platform UI E2E Testing Pipeline v2

V2 (`docker-build-run-all-tests-v2.yaml`, Pipeline name `docker-build-v2`)
provides non-root source extraction and test execution, workspace diagnostics,
and flexible E2E secret loading. It builds the application image and runs unit
and Playwright E2E tests.

Before implementing `run-app-script`, read
[E2E-SIDECAR-BEST-PRACTICES.md](./E2E-SIDECAR-BEST-PRACTICES.md).
The script must include the documented nop image guard.

## Migration Guide

### Required migration from v1

V1 (`docker-build-run-all-tests.yaml`) is deprecated. All consuming repositories
must migrate to v2, including both pull-request and push PipelineRuns. New
consumers must use v2. V1 retains its legacy execution behavior for migration
compatibility; the non-root security changes are maintained in v2 only.

### Migration steps

1. **Update both pipeline references.** Use the v2 file and a revision containing
   the security and extraction fixes. For a Git resolver, the following
   `spec.pipelineRef` uses a revision on the fork containing those fixes:

   ```yaml
   spec:
     pipelineRef:
       resolver: git
       params:
         - name: url
           value: https://github.com/catastrophe-brandon/konflux-pipelines.git
         - name: revision
           value: 3f42408a0202be36ce41e4c11c4ca049bf97d415
         - name: pathInRepo
           value: pipelines/platform-ui/docker-build-run-all-tests-v2.yaml
   ```

   After the changes are merged upstream, use an upstream revision that contains
   them. Do not assume a commit from the fork exists in the upstream repository.
   For Pipelines as Code annotation references, update the remote URL to the v2
   file at the chosen repository/revision and set `spec.pipelineRef.name` to
   `docker-build-v2`. For bundle consumers, publish/select a bundle containing
   this v2 Pipeline and use the
   [Tekton bundles resolver](https://tekton.dev/docs/pipelines/bundle-resolver/);
   this guide does not establish a published v2 bundle location.
   See the [Git resolver documentation](https://tekton.dev/docs/pipelines/git-resolver/).

2. **Adapt workspace setup to non-root execution.** In v1, `workspace-setup` is a
   separate task using a fixed Node image. In v2, setup is a step inside
   `run-unit-tests`, uses `unit-test-image`, and runs as UID/GID `1000:1000`.
   Move relevant task-level configuration from the old `workspace-setup` task
   to `run-unit-tests`; remove overrides targeting the old task name. Include
   required system packages in the image instead of installing them as root.
   Check shell quoting: v2 runs `workspace-setup-script` through `bash -c`.

3. **Configure workspace access and capacity.** Follow
   [Consumer PipelineRun configuration](#consumer-pipelinerun-configuration)
   for both triggers. The test processes must belong to the workspace's writable
   group. Neither setting `HOME` nor setting `runAsUser` grants volume access.

4. **Review credentials and environment URLs.** Set `e2e-credentials-secret` to
   an existing Secret and use the exact key names described in
   [Secret management](#secret-management). V2 sets `HCC_ENV_URL` from the
   `e2e-hcc-env-url` parameter, not from the legacy `e2e-hcc-env-url` Secret key.
   Set that parameter explicitly if the application previously relied on the
   Secret value. New custom keys must match the environment variable names used
   by the scripts; `envFrom` does not rename them.

5. **Review routes and validate both triggers.** Supply a
   `frontend-proxy-routes-configmap` with a nonempty `routes` key and a
   `run-app-script` serving the application on port 8000. If migrating from an
   older pipeline with a chrome-dev sidecar, follow the
   [chrome sidecar migration](./MIGRATION.md). Run both PR and push pipelines:
   `diagnose-workspace` must pass, dependencies must install, and unit and E2E
   tests must complete successfully.

### Validated consumer

The maintainer reported a successful `astro-virtual-assistant-frontend` run with
shared pipeline commit `6dd7133550df659d37720ace226b2282c88b5cb3`, a 5Gi workspace,
and `fsGroup: 1005770000` on both test tasks. That group matched its workspace's
ownership. This is a working migration example, not validation of every
consumer or both trigger definitions. Select the workspace group and capacity
for each environment rather than copying those values unchanged.

The Git reference example uses `3f42408a0202be36ce41e4c11c4ca049bf97d415`, which
rebases the same security and diagnostic changes onto updated Konflux task
references. Astro's reported success was on the earlier revision; rerun consumer
validation when adopting the updated references.

## Non-root setup and tests

The diagnostic, extraction, workspace setup, unit-test, proxy-route setup, and
Playwright steps run as UID/GID `1000:1000`, require non-root execution, and
prevent privilege escalation. These settings apply to those steps; the
application and proxy sidecars retain their own image/runtime identities.

The workspace and extracted files must be readable and writable by the test
identity, including dependencies, caches, and artifacts. The proxy-route setup
step also needs write access to the `/config` volume. The pipeline does not
repair permissions with root-run steps. Custom test images must support
UID/GID `1000:1000`; in the pinned Playwright image, this is `ubuntu`, while
`pwuser` is `1001:1001`.

Diagnostics, extraction, setup, and unit tests use `/var/workdir` as `HOME`.
The Playwright step does not override `HOME`. Setup and tests run from
`/var/workdir`; scripts for a repository subdirectory must change directory
explicitly. The build's `path-context` does not change the test working directory.

### Consumer PipelineRun configuration

Pod-level volume permissions belong in the consuming PipelineRun or cluster
configuration. Merge these settings with existing `spec.taskRunSpecs` and
`spec.workspaces`; preserve other settings and workspace bindings.

The example below uses **astro's environment-specific group and capacity**.
Replace both group values with the permitted writable workspace group for your
environment. Do not default to `1000` simply because the steps run as UID 1000.

```yaml
spec:
  taskRunSpecs:
    - pipelineTaskName: run-unit-tests
      podTemplate:
        securityContext:
          fsGroup: 1005770000 # Replace for your environment.
    - pipelineTaskName: run-e2e-tests
      podTemplate:
        securityContext:
          fsGroup: 1005770000 # Use the same workspace group.
  workspaces:
    - name: workspace
      volumeClaimTemplate:
        spec:
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 5Gi # Size for source, dependencies, caches, and artifacts.
```

`fsGroup` adds group membership to the pod's processes and, where supported,
configures volume group access. It must be permitted by cluster policy and
supported by the storage configuration. Other tasks sharing the PVC must use
compatible volume permissions. See
[Tekton pod templates](https://tekton.dev/docs/pipelines/podtemplates/) and
[Kubernetes security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/).

A template-size change applies to newly created claims. If the PipelineRun
binds an existing PVC, preserve that binding and arrange supported PVC expansion
instead of replacing it with a claim template.

## Secret management

`e2e-credentials-secret` is required in practice: the E2E test and frontend proxy
containers use a non-optional `envFrom.secretRef`. Secret keys are imported under
**their original names**, without uppercasing or replacing hyphens. For portable
shell access, name new keys with uppercase letters, digits, and underscores.
See [Kubernetes secret environment variables](https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/#configure-all-key-value-pairs-in-a-secret-as-container-environment-variables).

V2 explicitly maps these legacy keys in both containers:

| Secret key | Environment variable |
| --- | --- |
| `e2e-user` | `E2E_USER` |
| `e2e-password` | `E2E_PASSWORD` |
| `e2e-stage-actual-hostname` | `STAGE_ACTUAL_HOSTNAME` |

Those explicit mappings are optional, but scripts still need the credentials
required by their tests. `HCC_ENV_URL` is explicitly set from the pipeline
parameter `e2e-hcc-env-url` (default `https://console.stage.redhat.com`); a Secret
key of either `HCC_ENV_URL` or `e2e-hcc-env-url` does not override it. The
application sidecar also receives this parameter as `HCC_ENV_URL`.

For example, an ExternalSecret can expose a custom token as follows (merge into
its existing `spec.data`, retaining the resource's other required settings):

```yaml
spec:
  data:
    - secretKey: CHROMATIC_TOKEN
      remoteRef:
        key: my-app/chromatic/token
    - secretKey: CURRENTS_RECORD_KEY
      remoteRef:
        key: my-app/currents/record-key
```

The resulting Secret's keys are available as `$CHROMATIC_TOKEN` and
`$CURRENTS_RECORD_KEY` in the E2E test and proxy containers. They are not injected
into unit tests or the application sidecar by this mechanism. Check required
variables without printing their values:

```bash
if [ -z "${CHROMATIC_TOKEN:-}" ]; then
  echo "CHROMATIC_TOKEN is missing"
  exit 1
fi
```

## Architecture and parameters

`run-unit-tests` extracts source into the shared workspace and installs
dependencies through `workspace-setup-script` before running `unit-tests-script`.
`run-e2e-tests` waits for the unit tests and built image, then reuses that workspace.
Its Playwright container runs alongside `frontend-dev-proxy` and
`run-application`. There is no chrome-dev sidecar. The proxy uses the ConfigMap
routes and `HCC_ENV_URL` to reach the local application and upstream services.

| Parameter | Purpose |
| --- | --- |
| `workspace-setup-script` | Optional non-root dependency setup inside `run-unit-tests`. |
| `unit-test-image` | Image for diagnostics, setup, and unit tests; default UBI9 Node.js 22. |
| `unit-tests-script` | Required unit-test script. |
| `e2e-tests-script` | Required E2E script, including readiness checks needed by the tests. |
| `run-app-script` | Required application sidecar script, including the nop guard. |
| `frontend-proxy-routes-configmap` | ConfigMap with a nonempty `routes` key. |
| `e2e-credentials-secret` | Existing Secret for E2E and proxy environment variables. |
| `e2e-hcc-env` | Proxy environment name; default `stage`. |
| `e2e-hcc-env-url` | Upstream URL used as `HCC_ENV_URL`. |
| `e2e-playwright-image` | Pinned Playwright test image; overrides must support the selected identity. |
| `e2e-proxy-image` | Frontend proxy image. |

Although `e2e-app-port` is declared, the current proxy readiness check uses port
8000 directly. Keep the application on port 8000. `e2e-chrome-dev-image` is not
a parameter of this pipeline. See the [pipeline YAML](./docker-build-run-all-tests-v2.yaml)
for the complete parameter list and defaults.

## Troubleshooting from logs

`diagnose-workspace` runs before extraction. It reports effective UID/groups,
workspace ownership/mode, disk capacity, and inode availability, then creates
and removes a temporary file. Failure stops the task before extraction.

- **Permission denied:** Compare the groups printed by `id` with the writable
  group printed by `stat`. Astro's failing run had process group `1000` but
  workspace group `1005770000` with mode `2775`. Matching `fsGroup` to the
  workspace group resolved that failure. A credential-copy warning creating
  `/var/workdir/.docker` can have the same filesystem cause.
- **Cannot utime / cannot change mode on `.`:** The extraction step uses
  `TAR_OPTIONS=--no-recursion --anchored --exclude=.` to skip only the archive
  root entry while extracting its contents. This preserves the mounted
  directory's metadata. Confirm the selected revision contains that fix.
- **ENOSPC during npm installation:** Check disk and inode consumption; source,
  dependencies, and the default npm cache share the workspace. Diagnostics show
  usage before installation, so capture `df -h`, `df -i`, and directory sizes in
  the setup script's failure handler if installation fills the volume.
- **Missing custom secret variable:** Check the Secret key's exact name and the
  `e2e-credentials-secret` parameter. `envFrom` does not rename keys. Avoid
  printing Secret values or dumping the environment into logs.

## Related documentation

- [Deprecated v1 documentation](./README.md)
- [Chrome sidecar migration](./MIGRATION.md)
- [Sidecar termination requirements](./E2E-SIDECAR-BEST-PRACTICES.md)
