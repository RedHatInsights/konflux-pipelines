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

### Testing in ephemeral Konflux namespace

Motivation for this pipeline was deprecation of Jenkins jobs (PR check) and avoiding use of docker-compose. If the test/deploy script is written wisely, you can use the script to run tests locally in Minikube K8S and run the same script in ephemeral Konflux namespace.

Pipeline has 4 tasks
- parse values from SNAPSHOT variable
- clone repository
- deploy ephemeral namespace
- run custom script

Pipeline reuses image which was built into redhat-user-workloads space.

#### Define ITS
- define konflux IntegrationTestScenario and point it to PipelineRun `pipelines/test-scripts-pipeline-run.yaml`, define `component-name`, `SCRIPT_PATH` and `output-image` parameters e.g.
```yaml
---
apiVersion: appstudio.redhat.com/v1beta2
kind: IntegrationTestScenario
metadata:
  labels:
    test.appstudio.openshift.io/optional: "true" # Change to "true" if you don't need the test to be mandatory
    appstudio.openshift.io/component: konfluxcomponent
  name: insights-konfluxcomponent-tekton-tests
  namespace: insights-management-tenant
spec:
  application: insights-konfluxcomponent
  contexts:
    - description: Component Testing
      name: component_konfluxcomponent
  resolverRef:
    resourceKind: pipelinerun
    params:
      - name: url
        value: https://github.com/RedHatInsights/konflux-pipelines.git
      - name: revision
        value: main
      - name: pathInRepo
        value: pipelines/test-scripts-pipeline-run.yaml
    resolver: git
  params:
    - name: SCRIPT_PATH
      value: 'scripts/deploy_test_env.sh'
    - name: component-name
      value: 'konfluxcomponent'
    - name: output-image
      value: quay.io/redhat-user-workloads/konflux-tenant/insights-konfluxcomponent/konfluxcomponent:on-pr-
```

### Define test/deploy script and Openshift/K8s resource
Check how this was done for (Floorist app)[https://github.com/RedHatInsights/konfluxcomponent/pull/300]. Openshift template can be used for local templating and applied as normal K8S resources to local Minikube instance.`

## Pipeline Parameters

### build-container-additional-secret

All pipelines in this repository support the `build-container-additional-secret` parameter, which allows you to provide an additional secret to the container build process.

**Description:** Name of a Konflux-managed secret that will be mounted and made available to the container build process when the `build-container` task runs.

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

   **Note:** This parameter is optional. If you don't specify it in your pipeline, it will default to looking for a secret named `build-container-additional-secret`. If no such secret exists in your Konflux environment, the build will proceed without mounting any additional secrets.

3. **Use the secret in your Containerfile/Dockerfile:**
   ```dockerfile
   # The secret will be available as a mounted file
   RUN --mount=type=secret,id=your-secret-name/your-secret cat /run/secrets/your-secret-name/your-secret
   ```

## Learn more

For complete details including MintMaker customization options and guidance on hosting remote pipelines, see the full blog post: [Easing the maintenance of Konflux build pipelines](https://gwenneg.com/2025/04/11/konflux-remote-pipeline.html).

## Remote Renovate configuration

The `renovate` folder in this repository contains files for remote Renovate configuration.
This allows you to share and apply the same configuration across many repositories without repeating it.

example:
```
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "github>RedHatInsights/konflux-pipelines//renovate/foreman_satellite/renovate.json"
  ],
  "tekton": {
    "schedule": ["at any time"]
  }
}
```

This repository uses a [GitHub Action](.github/workflows/renovate-mintmaker-config-validator.yaml) that automatically checks on every pull request for syntax errors in all `renovate.json` files.

Official renovate configuration on [extends](https://docs.renovatebot.com/configuration-options/#extends).
