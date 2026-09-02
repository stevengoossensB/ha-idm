# Release Guide - IDM

This document describes how to manage versions and trigger releases for the IDM integration.

## Overview

The release pipeline automates version bumping and release creation using GitHub Actions.

### Workflows

1. **Bump Version** (`bump-version.yml`) - Manually trigger version bumps
2. **Release** (`release.yml`) - Automatically builds and uploads artifacts when a release is published

## Quick Start: Triggering a Release

### Step 1: Bump the Version

1. Go to **Actions** tab in GitHub
2. Select **Bump Version** workflow
3. Click **Run workflow**
4. Choose the bump type:
   - **patch** - Bug fixes and minor changes (1.0.0 → 1.0.1)
   - **minor** - New features (1.0.0 → 1.1.0)
   - **major** - Breaking changes (1.0.0 → 2.0.0)
5. Click **Run workflow**

This will:
- Update `custom_components/idm/manifest.json` with the new version
- Update the `VERSION` file with the new version
- Create a git commit
- Create a git tag with 'v' prefix (e.g., `v1.0.1`)
- Push both to the repository
- Automatically create a GitHub Release with release notes

### Step 2: Release Workflow Runs Automatically

Once the release is published:
1. The **Release** workflow automatically triggers
2. It builds a zip archive of the component
3. It uploads the zip to the GitHub Release

## Manual Release (if needed)

If you prefer to manually create releases:

1. Update the version in `custom_components/idm/manifest.json`
2. Update the `VERSION` file (format: `v1.0.1`)
3. Commit both changes
4. Create a tag: `git tag v1.0.1`
5. Push the tag: `git push origin v1.0.1`
6. Go to GitHub and create a release from the tag
7. The Release workflow will automatically build and attach the zip

## Version Format

Versions follow semantic versioning: `MAJOR.MINOR.PATCH`

The `VERSION` file stores the version with a 'v' prefix:
```
v1.0.1
```

The `manifest.json` stores the version without prefix:
```json
{
  "version": "1.0.1"
}
```

Examples:
- `1.0.0` (initial release)
- `1.0.1` (patch fix)
- `1.1.0` (new features)
- `2.0.0` (major release)

## What Gets Updated

When you bump the version, these files are automatically updated:
- `custom_components/idm/manifest.json` - Main version file
- `VERSION` - Version reference file

## Release Artifacts

Each release includes:
- `idm.zip` - Complete component archive ready for installation
- Automatically generated release notes from commit messages

## Troubleshooting

### Workflow failed to push
Make sure the GitHub token has write permissions. This should be automatic for workflows.

### Version didn't update
Check the workflow logs in the **Actions** tab for error messages.

### Release zip not attached
Verify the Release workflow ran after the release was published. Check the Actions tab for any failures.

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Semantic Versioning](https://semver.org/)
- [Home Assistant Integration Documentation](https://developers.home-assistant.io/docs/creating_integration_manifest)
