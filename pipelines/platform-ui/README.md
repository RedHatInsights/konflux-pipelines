# Platform UI E2E Testing Pipeline

## Overview

This pipeline (`docker-build-run-all-tests.yaml`) extends the standard Konflux docker-build pipeline with end-to-end testing capabilities for Platform UI applications.

## Purpose

Enables full integration testing of frontend applications by:
1. Building the application container image
2. Running the application with dynamic route configuration
3. Setting up a reverse proxy for routing requests
4. Executing Playwright-based E2E tests

## Key Features

### Dynamic Route Generation

The pipeline supports dynamic generation of Caddyfile configurations through script parameters:

#### proxy-routes-script Parameter
- **Type**: Shell script
- **Purpose**: Generates Caddyfile proxy route configuration
- **Execution**: Runs in `setup-proxy-routes` step before tests
- **Output**: Writes Caddyfile directives to `/config/routes`

The `setup-proxy-routes` step:
```yaml
- name: setup-proxy-routes
  image: quay.io/quay/busybox
  script: |
    #!/bin/sh
    set -e
    echo "Generating proxy routes configuration..."

    # Write the proxy routes script to a temporary file
    cat > /tmp/generate_proxy_routes.sh << 'SCRIPT_EOF'
    $(params.PROXY_ROUTES_SCRIPT)
    SCRIPT_EOF

    # Execute the script to generate routes
    chmod +x /tmp/generate_proxy_routes.sh
    /tmp/generate_proxy_routes.sh > /config/routes
```

This allows consuming pipelines to provide a script that dynamically generates routes based on application-specific parameters.

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
   - Uses configuration from `proxy-routes-script`
   - Distributes traffic between application and Chrome server

4. **Playwright Tests**:
   - Connects to `https://stage.foo.redhat.com:1337`
   - Executes E2E test scenarios

## Parameters

### Pipeline Parameters

- **proxy-routes-script**: Script to generate proxy routes configuration
  - Receives Tekton-interpolated parameters
  - Outputs Caddyfile `handle` directives
  - Must include shebang (`#!/bin/sh`)

- **run-app-script**: Script to run the application
  - Configures application-specific Caddyfile routes
  - Starts Caddy server

- **e2e-tests-script**: Script to execute E2E tests
  - Waits for servers to be ready
  - Runs Playwright tests

### Task Parameters

The `run-e2e-tests` task receives:
- `PROXY_ROUTES_SCRIPT`: The proxy routes generation script
- `APP_PORT`: Application port (default: 8000)
- `PLAYWRIGHT_IMAGE`: Image for running tests
- `CHROME_DEV_IMAGE`: Chrome development server image
- `PROXY_IMAGE`: Reverse proxy image

## Usage Example

Consumer pipelines (like `learning-resources`) provide scripts that:

1. Accept parameterized inputs (app name, ports, route lists)
2. Perform validation (security checks)
3. Generate appropriate Caddyfile configuration
4. Output the configuration to stdout

Example `proxy-routes-script`:
```bash
#!/bin/sh
set -e

# Parse comma-separated route,port pairs
while IFS= read -r line; do
    route=$(echo "$line" | cut -d',' -f1)
    port=$(echo "$line" | cut -d',' -f2)

    # Validate and generate handle directive
    cat << EOF
handle ${route} {
    reverse_proxy 127.0.0.1:${port}
}
EOF
done < /tmp/routes_input.txt
```

## Security Considerations

Consumer scripts should validate:
- Route paths (prevent path traversal)
- Character allowlists (prevent injection)
- Port ranges (1-65535)
- No double slashes or special characters

## Maintenance

### Related Repositories

- **Consumer Example**: `RedHatInsights/learning-resources`
  - Path: `.tekton/learning-resources-pull-request.yaml`
  - Demonstrates parameterized route generation

### Branch Information

- **Branch**: `btweed/platform-ui-e2e`
- **Status**: Development/Testing
- **Upstream**: To be merged to main branch

## Troubleshooting

### Dev Server Not Ready

If E2E tests timeout waiting for the dev server:
1. Check `SIDECAR-RUN-APPLICATION` logs for Caddy errors
2. Verify `setup-proxy-routes` step executed successfully
3. Ensure proxy routes script outputs valid Caddyfile syntax
4. Confirm ports match between application and proxy configuration

### Script Execution Failures

If `proxy-routes-script` fails:
1. Verify script has proper shebang (`#!/bin/sh`)
2. Check for heredoc syntax errors
3. Ensure all referenced Tekton parameters exist
4. Test script locally with interpolated values

## Future Improvements

- Support for additional protocol handlers (gRPC, WebSocket)
- Enhanced validation and error reporting
- Metrics collection from proxy layer
- Dynamic host-based routing
