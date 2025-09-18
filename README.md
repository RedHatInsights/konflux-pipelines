# Remote pipeline definitions for Konflux

This repository provides remote pipeline definitions that can help ease the maintenance of Konflux build pipelines across multiple repositories.

When a component is onboarded to Konflux, two build pipelines are automatically created:
- `${component.name}-pull-request.yaml`
- `${component.name}-push.yaml`

Instead of maintaining inline pipeline definitions in each repository, you can use remote pipelines to centralize pipeline management.

## Using remote pipelines

Remote pipelines use [Pipelines as Code](https://pipelinesascode.com/docs/guide/resolver/#remote-pipeline-annotations) annotations to reference pipeline definitions from external repositories. You need to replace the `pipelineSpec` section with a `pipelineRef` and add a remote pipeline annotation.

### Depending on the latest version

To always use the latest version of remote pipelines:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  annotations:
    pipelinesascode.tekton.dev/pipeline: >
      https://github.com/RedHatInsights/konflux-pipelines/raw/main/pipelines/docker-build-oci-ta.yaml
  # Other metadata...
spec:
  params: # Your existing params
  pipelineRef:
    name: docker-build-oci-ta
  workspaces: # Your existing workspaces
```

**Benefits:**
- MintMaker will no longer open PRs to update Konflux task references
- Pipeline runs automatically use the latest version
- Minimal maintenance required

**Drawback:**
- Changes in remote pipelines go untested until another PR triggers a pipeline run

### Depending on a specific version

To depend on a specific release version:

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  annotations:
    pipelinesascode.tekton.dev/pipeline: >
      https://github.com/RedHatInsights/konflux-pipelines/raw/v1.2.0/pipelines/docker-build-oci-ta.yaml
  # Other metadata...
spec:
  params: # Your existing params
  pipelineRef:
    name: docker-build-oci-ta
  workspaces: # Your existing workspaces
```

**Benefits:**
- MintMaker automatically opens PRs when new releases are published
- Changes are immediately tested in your repository
- You catch issues as early as possible
- Still avoid Konflux task reference updates and migrations

**Drawback:**
- Requires occasional PRs to update to newer versions (but automated by MintMaker)

## Pipeline Parameters

### build-container-additional-secret

All pipelines in this repository support the `build-container-additional-secret` parameter, which allows you to provide an additional secret to the container build process.

**Description:** Name of a Konflux-managed secret that will be mounted and made available to the container build process during the build step.

**Default value:** `build-container-additional-secret`

**How it works:** The secret is mounted into the build container and can be accessed during the Docker/Podman build process, allowing you to authenticate with private registries, access private repositories, or provide other sensitive configuration needed during the build.

#### Creating and using additional secrets

1. **Create a secret in Konflux:**
   Follow the [Konflux documentation for creating secrets](https://konflux-ci.dev/docs/building/creating-secrets/#referencing-secrets-in-a-containerfile) to create your secret in the Konflux environment.

2. **Reference the secret in your pipeline:**
   ```yaml
   spec:
     params:
       - name: build-container-additional-secret
         value: "your-secret-name"
       # ... other parameters
   ```

3. **Use the secret in your Containerfile/Dockerfile:**
   ```dockerfile
   # The secret will be available as a mounted file
   RUN --mount=type=secret,id=your-secret-name/your-secret cat /run/secrets/your-secret-name/your-secret
   ```

**Note:** This parameter is optional. If not specified, it defaults to looking for a secret named `build-container-additional-secret`. If no such secret exists, the build will proceed without mounting any additional secrets.

## Learn more

For complete details including MintMaker customization options and guidance on hosting remote pipelines, see the full blog post: [Easing the maintenance of Konflux build pipelines](https://gwenneg.com/2025/04/11/konflux-remote-pipeline.html).
