# How to Find Affected Consumer Repositories

Since the `insights-chrome-dev` sidecar has been removed, we need to identify which repositories use the platform-ui pipeline and may need migration.

## Option 1: GitHub Web Search (Easiest)

Go to GitHub and use these search queries:

### 1. Find repos using platform-ui pipeline
```
org:RedHatInsights "docker-build-run-all-tests" path:.tekton/
```
[Search now](https://github.com/search?q=org%3ARedHatInsights+%22docker-build-run-all-tests%22+path%3A.tekton%2F&type=code)

### 2. Find repos with port 9912 references
```
org:RedHatInsights "9912" path:.tekton/
```
[Search now](https://github.com/search?q=org%3ARedHatInsights+%229912%22+path%3A.tekton%2F&type=code)

### 3. Find repos with chrome-dev-image parameter
```
org:RedHatInsights "e2e-chrome-dev-image"
```
[Search now](https://github.com/search?q=org%3ARedHatInsights+%22e2e-chrome-dev-image%22&type=code)

### 4. Find repos with chrome route configurations
```
org:RedHatInsights "/apps/chrome" "reverse_proxy"
```
[Search now](https://github.com/search?q=org%3ARedHatInsights+%22%2Fapps%2Fchrome%22+%22reverse_proxy%22&type=code)

## Option 2: GitHub CLI (If installed)

If you have `gh` CLI installed, run:

```bash
./find-consumers.sh
```

This will generate a report of all potentially affected repositories.

## Option 3: Manual Check

### Known Consumers

1. **learning-resources** - CONFIRMED consumer
   - Repository: https://github.com/RedHatInsights/learning-resources
   - Needs migration: YES

### How to Check a Specific Repository

```bash
# Clone the repo
git clone https://github.com/RedHatInsights/REPO_NAME
cd REPO_NAME

# Search for platform-ui usage
grep -r "docker-build-run-all-tests" .tekton/

# Search for port 9912
grep -r "9912" .tekton/

# Search for chrome-dev-image
grep -r "e2e-chrome-dev-image" .tekton/

# Look for ConfigMaps with routes
find .tekton -name "*configmap*" -o -name "*routes*"
```

## Expected Consumer Repositories

Based on the platform-ui pipeline design, potential consumers include:

- Any frontend application using e2e testing
- Repositories in the HCC platform ecosystem
- Repositories using the insights-chrome shell
- Repositories with Playwright-based tests

### Team Areas to Check

- Platform Experience (PlatEx) team repositories
- Console.redhat.com frontend applications
- HCC service UIs

## After Identifying Consumers

For each consumer repository found:

1. ✅ Document it in this file (add to the list below)
2. ✅ Create a tracking issue or task
3. ✅ Follow the migration steps in MIGRATION.md
4. ✅ Test the changes
5. ✅ Submit a PR to the consumer repo

## Consumer Repository Tracking

| Repository | Status | PR Link | Notes |
|------------|--------|---------|-------|
| learning-resources | 🔍 Needs Check | - | Known consumer |
| _Add more as found_ | - | - | - |

### Status Legend
- 🔍 Needs Check - Not yet verified if migration needed
- ⚠️ Needs Migration - Confirmed to need updates
- 🚧 In Progress - Migration PR created
- ✅ Complete - Migration merged

---

## For Platform Team

After completing the search and identifying all consumers, update this section with:
- Total number of affected repositories
- Migration completion status
- Timeline for main branch merge
