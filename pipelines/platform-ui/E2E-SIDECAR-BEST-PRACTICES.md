# E2E Sidecar Best Practices

## Tekton Sidecar Termination Issue (CRITICAL)

**Affects:** All repos using `docker-build-run-all-tests.yaml` or `docker-build-run-all-tests-v2.yaml`

### Problem

When E2E tests complete, Tekton terminates sidecar containers by:
1. Sending SIGTERM to the sidecar process
2. **Replacing the sidecar's container image** with `pipelines-nop-rhel9` (a no-operation image)
3. **Keeping the original command/args** from the sidecar definition

On OpenShift/RHEL environments, the `pipelines-nop-rhel9` image contains `/bin/sh`. This causes the sidecar script to **execute again** in the nop image, where application binaries don't exist, resulting in errors like:

```
/bin/sh: line 8: caddy: command not found
/bin/sh: line 8: /usr/bin/myapp: No such file or directory
```

**Upstream Issue:** https://github.com/tektoncd/pipeline/issues/1347

### Solution: Guard Against Nop Image Execution

**All `run-app-script` implementations MUST include a guard** at the start to detect the nop environment and exit gracefully:

```bash
#!/bin/sh
set -e

# Guard against Tekton's sidecar termination mechanism
# Tekton replaces sidecar images with pipelines-nop-rhel9 after tests complete
# The nop image contains /bin/sh, so this script tries to run again
# Detect nop environment and exit gracefully
# See: https://github.com/tektoncd/pipeline/issues/1347
if ! command -v <your-app-binary> >/dev/null 2>&1; then
  echo "<your-app-binary> not found - running in nop image, exiting gracefully"
  exit 0
fi

# Rest of your script continues normally
echo "Starting application..."
<your-app-binary> <args>
```

Replace `<your-app-binary>` with whatever binary your application uses (e.g., `caddy`, `node`, `python`, `java`, etc.).

### Examples

#### Example 1: Caddy Server

```bash
#!/bin/sh
set -e

# Guard against nop image
if ! command -v caddy >/dev/null 2>&1; then
  echo "Caddy not found - running in nop image, exiting gracefully"
  exit 0
fi

echo "Starting Caddy server on port 8000..."
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
```

#### Example 2: Node.js Application

```bash
#!/bin/sh
set -e

# Guard against nop image
if ! command -v node >/dev/null 2>&1; then
  echo "Node not found - running in nop image, exiting gracefully"
  exit 0
fi

echo "Starting Node.js application..."
cd /app
node server.js
```

#### Example 3: Python Application

```bash
#!/bin/sh
set -e

# Guard against nop image
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python not found - running in nop image, exiting gracefully"
  exit 0
fi

echo "Starting Python application..."
cd /app
python3 app.py
```

## Complete Pipeline Configuration Example

Here's how to configure the `run-app-script` parameter in your `.tekton/<app>-pull-request.yaml`:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  annotations:
    pipelinesascode.tekton.dev/on-cel-expression: event == "pull_request" && target_branch == "master"
    pipelinesascode.tekton.dev/pipeline: https://github.com/RedHatInsights/konflux-pipelines/raw/main/pipelines/platform-ui/docker-build-run-all-tests.yaml
  name: <app>-on-pull-request
spec:
  params:
    - name: git-url
      value: '{{source_url}}'
    - name: revision
      value: '{{revision}}'
    - name: output-image
      value: quay.io/redhat-user-workloads/<namespace>/<app>/<component>:on-pr-{{revision}}
    
    # CRITICAL: Include the nop image guard!
    - name: run-app-script
      value: |
        #!/bin/sh
        set -e
        
        # Guard against Tekton nop image replacement
        # See: https://github.com/tektoncd/pipeline/issues/1347
        if ! command -v caddy >/dev/null 2>&1; then
          echo "Caddy not found - running in nop image, exiting gracefully"
          exit 0
        fi
        
        echo "Starting application on port 8000..."
        caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
    
    # Other required parameters...
    - name: e2e-tests-script
      value: |
        #!/bin/bash
        set -ex
        npm ci
        npx playwright test
    
    - name: frontend-proxy-routes-configmap
      value: '<app>-dev-proxy-caddyfile'
```

## Why This Guard Is Necessary

### What Happens Without the Guard

1. Tests complete → `step-e2e-tests` exits
2. Tekton sends SIGTERM → Your app (e.g., Caddy) shuts down cleanly
3. **Tekton replaces image** → `quay.io/your-app:tag` becomes `pipelines-nop-rhel9`
4. **Script runs again** → `/bin/sh -c "<your-script>"`
5. Script tries to execute your app binary → **Binary doesn't exist in nop image**
6. Error: `command not found` or `No such file or directory`
7. Container exits with non-zero code → **Logs show error even though tests passed**

### What Happens With the Guard

1. Tests complete → `step-e2e-tests` exits
2. Tekton sends SIGTERM → Your app shuts down cleanly
3. **Tekton replaces image** → `quay.io/your-app:tag` becomes `pipelines-nop-rhel9`
4. **Script runs again** → `/bin/sh -c "<your-script>"`
5. **Guard detects nop environment** → `command -v <app>` returns false
6. Script prints message and exits with code 0
7. **Clean shutdown, no errors in logs**

## Evidence of the Issue

You may see these symptoms:

**Pod Events:**
```
Container sidecar-run-application definition changed, will be restarted
Pulling image "pipelines-nop-rhel9"
```

**Container Logs:**
```
/bin/sh: line 8: caddy: command not found
```

**Container Status:**
```
RestartCount: 0  # Not a crash! This is image replacement, not restart
```

## Related Issues

- **Tekton Pipelines #1347**: https://github.com/tektoncd/pipeline/issues/1347
  - Root cause: RHEL-based nop images contain `/bin/sh`
  - Affects all OpenShift/RHEL Tekton deployments
  - Issue open since 2019

## Affected Pipelines

Both of these pipelines use the same sidecar pattern and require the guard:

- `docker-build-run-all-tests.yaml` (v1)
- `docker-build-run-all-tests-v2.yaml` (v2)

## Checklist for Implementers

When setting up E2E tests with these pipelines:

- [ ] Added nop image guard to `run-app-script`
- [ ] Guard checks for the specific binary your app uses
- [ ] Guard exits with code 0 (successful exit)
- [ ] Guard prints a clear message for debugging
- [ ] Tested in Konflux pipeline (not just locally)
- [ ] Verified no "command not found" errors in logs after tests complete

## Questions?

If you're unsure which binary to check for in the guard, look at what command your sidecar is running. Examples:

- Running `caddy run` → check for `caddy`
- Running `node server.js` → check for `node`
- Running `python3 app.py` → check for `python3`
- Running `/usr/local/bin/myapp` → check for `myapp` or use the full path
- Running a shell script that calls other tools → check for the first critical tool

The guard should detect the **first command that would fail** in the nop image.
