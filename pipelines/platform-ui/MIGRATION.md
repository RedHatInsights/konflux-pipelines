# Migration Guide: Chrome Sidecar Removal

## Overview

The `insights-chrome-dev` sidecar has been removed from the platform-ui e2e testing pipeline. This document helps identify affected repositories and provides migration steps.

## Identifying Affected Repositories

### Search Patterns for GitHub

Use these search queries on GitHub to find potentially affected repositories:

1. **Repositories using the platform-ui pipeline:**
   ```
   org:RedHatInsights "pipelinesascode.tekton.dev/pipeline" "platform-ui/docker-build-run-all-tests"
   ```

2. **Repositories referencing port 9912:**
   ```
   org:RedHatInsights "9912" path:.tekton/
   ```

3. **Repositories with chrome-dev-image parameter:**
   ```
   org:RedHatInsights "e2e-chrome-dev-image" path:.tekton/
   ```

4. **Repositories with ConfigMaps routing to chrome:**
   ```
   org:RedHatInsights "127.0.0.1:9912" path:.tekton/
   org:RedHatInsights "/apps/chrome" ConfigMap
   ```

### Known Consumers

- **RedHatInsights/learning-resources** - Confirmed consumer, needs migration

### What to Look For

In consumer repositories, check for:
- `.tekton/*.yaml` files that reference `docker-build-run-all-tests.yaml`
- ConfigMaps containing route configurations
- Any hardcoded references to port `9912`
- Pipeline parameters that set `e2e-chrome-dev-image`

## Migration Steps

### For Each Affected Repository

1. **Review ConfigMap Routes**
   ```bash
   # Find ConfigMaps with routes
   grep -r "9912" .tekton/
   grep -r "apps/chrome" .tekton/
   ```

2. **Update Route Configurations**
   - Remove any routes targeting `127.0.0.1:9912`
   - Remove any routes targeting `http://localhost:9912`
   - Ensure chrome assets are fetched from upstream (they will be proxied via HCC_ENV_URL)

3. **Remove Chrome-Related Parameters** (if present)
   ```yaml
   # REMOVE these parameter overrides if present:
   - name: e2e-chrome-dev-image
     value: "quay.io/..."
   ```

4. **Test the Pipeline**
   - Create a PR with the changes
   - Verify e2e tests pass
   - Check that chrome assets load correctly in tests

## Example Migration

### Before (ConfigMap with chrome routes):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-proxy-routes
data:
  routes: |
    handle /apps/chrome* {
      reverse_proxy 127.0.0.1:9912
    }
    handle /apps/myapp* {
      reverse_proxy 127.0.0.1:8000
    }
```

### After (Chrome routes removed):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-proxy-routes
data:
  routes: |
    handle /apps/myapp* {
      reverse_proxy 127.0.0.1:8000
    }
    # Chrome assets now proxied from upstream HCC_ENV_URL automatically
```

## Technical Details

### What Changed

- The `insights-chrome-dev` sidecar no longer runs in the e2e test pod
- Port 9912 is no longer available for routing
- Chrome assets (JS, CSS, HTML) are now served from the upstream environment via the `HCC_ENV_URL` proxy
- The frontend-dev-proxy no longer waits for port 9912 to be ready

### Why This Works

The chrome sidecar was redundant because:
1. The frontend-dev-proxy already proxies all non-matched routes to upstream
2. Chrome assets can be fetched from the upstream staging environment
3. No consumer repositories were actually using locally-served chrome assets
4. This reduces pod resource usage and complexity

### Compatibility

- ✅ **Compatible**: Repositories that only route application paths to port 8000
- ✅ **Compatible**: Repositories that rely on upstream chrome assets
- ⚠️ **Needs Update**: Repositories explicitly routing to port 9912
- ⚠️ **Needs Update**: Repositories with custom chrome-dev-image parameters

## Rollback Plan

If issues arise, consumer repositories can temporarily:
1. Pin to an older version of the platform-ui pipeline (before chrome sidecar removal)
2. Add the chrome sidecar back to their own pipeline spec (not recommended)

## Questions or Issues?

- Repository: https://github.com/RedHatInsights/konflux-pipelines
- Branch: btweed/remove-chrome-sidecar
- Contact: Platform Experience team

## Timeline

1. **Now**: Pipeline changes merged to feature branch
2. **Next**: Identify and migrate consumer repositories
3. **Then**: Merge to main branch after all consumers are migrated
4. **Finally**: Consumer repos can adopt the updated pipeline
