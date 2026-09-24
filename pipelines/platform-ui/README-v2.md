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
5. Serve the app on port **8000**. Supply a routes ConfigMap with a nonempty
   `routes` key. Include the [nop guard](./E2E-SIDECAR-BEST-PRACTICES.md) in
   `run-app-script`. There is no chrome-dev sidecar; remove old chrome routes
   using the [sidecar migration guide](./MIGRATION.md).
6. Run both triggers. Check extraction, dependency installation, and all tests.

### Pipeline reference

This fork revision contains the security and extraction fixes:

```yaml
spec:
  pipelineRef:
    resolver: git
    params:
      - name: url
        value: https://github.com/catastrophe-brandon/konflux-pipelines.git
      - name: revision
        value: d9defcaf6f7546563bcaad2f850488662d86503e
      - name: pathInRepo
        value: pipelines/platform-ui/docker-build-run-all-tests-v2.yaml
```

After upstream merge, choose an upstream revision containing the fixes.
For annotation references, update the file URL and use Pipeline name
`docker-build-v2`. Bundle users must select a bundle containing v2 through the
[bundles resolver](https://tekton.dev/docs/pipelines/bundle-resolver/).

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

Astro passed with this group and capacity on commit `6dd7133`. The reference
above includes later dependency updates, so validate your own run.
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
and defaults. The current proxy readiness check requires port 8000 even if
`e2e-app-port` is changed.
