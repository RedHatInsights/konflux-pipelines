# Platform UI E2E Testing Pipeline v2

## Overview

This is **version 2** of the Platform UI E2E testing pipeline with enhanced secret management capabilities. It extends the standard Konflux docker-build pipeline with end-to-end testing capabilities for Platform UI applications.

## What's New in v2

### Flexible Secret Management

The key difference in v2 is the use of `envFrom` for secret management, which allows consumers to add any credentials they need **without modifying the shared pipeline definition**.

**v1 (Legacy)**: Hardcoded secret keys
```yaml
env:
  - name: E2E_USER
    valueFrom:
      secretKeyRef:
        name: $(params.CREDENTIALS_SECRET)
        key: e2e-user
  - name: E2E_PASSWORD
    valueFrom:
      secretKeyRef:
        name: $(params.CREDENTIALS_SECRET)
        key: e2e-password
```

**v2 (Current)**: Flexible secret loading
```yaml
envFrom:
  - secretRef:
      name: $(params.CREDENTIALS_SECRET)
      optional: false
```

All keys in the secret automatically become environment variables, enabling easy integration with third-party services like Chromatic, Currents, or any other testing platform.

## Migration Guide

### Should You Migrate?

- **Stay on v1** if: Your current setup works and you don't need additional secrets
- **Migrate to v2** if: You need to add custom secrets (Chromatic, Currents, etc.) or want more flexibility

### Migration Steps

1. **Update your pipeline reference** (in `.tekton/*.yaml`):
   ```yaml
   # Before
   pipelineRef:
     name: docker-build
     bundle: quay.io/.../pipelines/platform-ui/docker-build-run-all-tests

   # After
   pipelineRef:
     name: docker-build-v2
     bundle: quay.io/.../pipelines/platform-ui/docker-build-run-all-tests-v2
   ```

2. **Verify your existing secrets work**: v2 is backwards compatible with v1 secrets
   - Existing keys like `e2e-user`, `e2e-password` automatically become `E2E_USER`, `E2E_PASSWORD` env vars

3. **Add any new secrets** (optional):
   ```yaml
   # Your ExternalSecret
   data:
     # Existing
     - secretKey: e2e-user
       remoteRef:
         key: standard/e2e/user

     # New: Add custom secrets
     - secretKey: chromatic-token
       remoteRef:
         key: my-app/chromatic/token
   ```

4. **Use new secrets in your test scripts**:
   ```bash
   #!/bin/bash
   # In your e2e-tests-script parameter

   if [ -n "$CHROMATIC_TOKEN" ]; then
     npx playwright test --reporter=@chromatic/playwright
   fi
   ```

## Secret Management

The `e2e-credentials-secret` parameter accepts a Kubernetes Secret name. **All keys** in that secret are automatically exposed as environment variables to:
- The E2E test container (Playwright)
- The frontend-dev-proxy sidecar

Secret keys are automatically converted to environment variable names (e.g., `e2e-user` → `E2E_USER`, `chromatic-token` → `CHROMATIC_TOKEN`).

### Standard Secret Keys

Common keys used across multiple consumers:
- `e2e-user`: Test user credentials
- `e2e-password`: Test user password
- `e2e-hcc-env-url`: Environment URL for testing
- `e2e-stage-actual-hostname`: Stage hostname

### Adding Custom Secrets

Consumers can add any additional keys to their ExternalSecret definition without pipeline changes.

#### Example: Chromatic Integration

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-app-e2e-secrets
spec:
  # ... standard configuration ...
  data:
    # Standard keys
    - secretKey: e2e-user
      remoteRef:
        key: standard/e2e/user
    - secretKey: e2e-password
      remoteRef:
        key: standard/e2e/password

    # Chromatic-specific keys
    - secretKey: chromatic-token
      remoteRef:
        key: my-app/chromatic/token
    - secretKey: chromatic-project-id
      remoteRef:
        key: my-app/chromatic/project-id
```

**Using in test script:**
```bash
#!/bin/bash
# e2e-tests-script

# Run tests
npx playwright test

# Chromatic integration (if token is in the secret)
if [ -n "$CHROMATIC_TOKEN" ]; then
  echo "Publishing visual snapshots to Chromatic..."
  npx chromatic --project-token="$CHROMATIC_TOKEN"
fi
```

#### Example: Currents Integration

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-app-e2e-secrets
spec:
  data:
    # Standard keys
    - secretKey: e2e-user
      remoteRef:
        key: standard/e2e/user

    # Currents-specific keys
    - secretKey: currents-record-key
      remoteRef:
        key: my-app/currents/record-key
    - secretKey: currents-project-id
      remoteRef:
        key: my-app/currents/project-id
    - secretKey: currents-ci-build-id
      remoteRef:
        key: my-app/currents/ci-build-id
```

**Using in test script:**
```bash
#!/bin/bash
# e2e-tests-script

# Currents integration (if keys are in the secret)
if [ -n "$CURRENTS_RECORD_KEY" ]; then
  echo "Recording test results to Currents..."
  export CURRENTS_RECORD_KEY
  export CURRENTS_PROJECT_ID
  export CURRENTS_CI_BUILD_ID
  npx playwright test --reporter=@currents/playwright
fi
```

### Benefits

- **No pipeline changes required**: Add new secrets by updating your ExternalSecret only
- **Per-consumer flexibility**: Each consuming repository can define their own secret keys
- **Backwards compatible**: Existing v1 secrets continue to work unchanged
- **Secure**: Secrets never appear in pipeline definitions or logs
- **Extensible**: Easy integration with any third-party service that needs credentials

## Architecture

### Test Environment Setup

```
┌─────────────────────────────────────────────────────┐
│  E2E Test Pod                                       │
│                                                     │
│  ┌─────────────────┐  ┌──────────────────────┐    │
│  │  Playwright     │  │  Frontend Proxy      │    │
│  │  Tests          │─▶│  (Port 1337)         │    │
│  └─────────────────┘  └──────────────────────┘    │
│                        │                           │
│                        ├─ /apps/chrome* → 9912    │
│                        ├─ /apps/app* → 8000       │
│                        └─ /other* → 9912          │
│                                                     │
│  ┌─────────────────┐  ┌──────────────────────┐    │
│  │  Chrome Dev     │  │  Application         │    │
│  │  Server         │  │  (Port 8000)         │    │
│  │  (Port 9912)    │  │  + Caddyfile routes  │    │
│  └─────────────────┘  └──────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### Component Responsibilities

1. **Application Sidecar** (Port 8000):
   - Runs the built application
   - Serves static files via Caddy
   - Handles application-specific routes defined by `run-app-script`

2. **Chrome Dev Server** (Port 9912):
   - Provides Chrome UI shell
   - Serves shared frontend infrastructure

3. **Frontend Proxy** (Port 1337):
   - Routes requests based on path
   - Uses configuration from ConfigMap
   - Distributes traffic between application and Chrome server

4. **Playwright Tests**:
   - Connects to `https://stage.foo.redhat.com:1337`
   - Executes E2E test scenarios
   - Has access to all secrets as environment variables

## Parameters

### Pipeline Parameters

- **e2e-tests-script**: Script to execute E2E tests
  - Waits for servers to be ready
  - Runs Playwright tests
  - Has access to all secrets as environment variables

- **run-app-script**: Script to run the application
  - Configures application-specific Caddyfile routes
  - Starts Caddy server

- **e2e-credentials-secret**: Name of the Kubernetes Secret containing test credentials
  - **All keys in this secret are automatically exposed as environment variables**
  - Enables flexible credential management without pipeline modifications

- **frontend-proxy-routes-configmap**: Name of ConfigMap containing proxy routes data

- **e2e-app-port**: Application port (default: 8000)

- **e2e-playwright-image**: Playwright image to use for testing

- **e2e-chrome-dev-image**: Chrome dev image

- **e2e-proxy-image**: Frontend proxy image

### Task Parameters

The `run-e2e-tests` task receives:
- `CREDENTIALS_SECRET`: Name of secret (all keys become environment variables)
- `APP_PORT`: Application port (default: 8000)
- `PLAYWRIGHT_IMAGE`: Image for running tests
- `CHROME_DEV_IMAGE`: Chrome development server image
- `PROXY_IMAGE`: Reverse proxy image

## Security Considerations

### Secret Key Naming

Choose secret key names carefully:
- Use lowercase with hyphens: `chromatic-token` (becomes `CHROMATIC_TOKEN`)
- Avoid conflicts with system environment variables
- Be descriptive: `currents-record-key` not just `key`

### Validation in Test Scripts

Even though secrets are automatically available, validate they exist before using them:

```bash
#!/bin/bash

if [ -z "$CHROMATIC_TOKEN" ]; then
  echo "Warning: CHROMATIC_TOKEN not found, skipping Chromatic upload"
else
  npx chromatic --project-token="$CHROMATIC_TOKEN"
fi
```

## Troubleshooting

### Environment Variables Not Available

If your custom secrets aren't appearing as environment variables:

1. **Check the secret exists**: `kubectl get secret <secret-name> -n <namespace>`
2. **Verify secret keys**: `kubectl get secret <secret-name> -o yaml`
3. **Check key naming**: Keys with underscores or uppercase letters may not convert as expected
4. **Check pipeline parameter**: Ensure `e2e-credentials-secret` parameter matches your secret name

### Testing Secret Availability

Add debugging to your e2e-tests-script:

```bash
#!/bin/bash
set -e

echo "=== Available Environment Variables ==="
env | grep -E '(E2E_|CHROMATIC_|CURRENTS_)' | sed 's/=.*/=***/'
echo "======================================="

# Run tests
npx playwright test
```

## Related Documentation

- **v1 Pipeline**: See [README.md](./README.md) for the original pipeline documentation
- **Consumer Example**: `RedHatInsights/learning-resources` (uses v1)

## Future Improvements

- Support for additional protocol handlers (gRPC, WebSocket)
- Enhanced validation and error reporting
- Metrics collection from proxy layer
- Dynamic host-based routing
