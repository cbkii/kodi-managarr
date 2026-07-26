# Kodi Managarr add-on repository

This is the generated download branch used by Kodi. It currently publishes:

- **Kodi Managarr add-on:** `{{ADDON_VERSION}}`
- **Kodi repository add-on:** `{{REPOSITORY_VERSION}}`

The normal source code lives on the [`main` branch](https://github.com/cbkii/kodi-managarr/tree/main). Do **not** edit this `gh-pages` branch by hand: each repository publication replaces the branch with newly generated and verified files.

## What this branch does

Kodi uses this branch as a small software catalogue:

1. `addons.xml` tells Kodi which add-on version is available.
2. `addons.xml.md5` lets Kodi detect catalogue changes.
3. `context.arr.manager/` contains the latest installable Kodi Managarr ZIP and metadata.
4. `repository.managarr/` contains the small repository ZIP that users install once in Kodi.
5. `index.html` provides the beginner-friendly download page.

After the repository ZIP is installed, Kodi checks these files and can offer normal Kodi Managarr updates.

## Normal release process

Open **Actions → Build and publish Kodi release → Run workflow**.

For a new release:

1. Leave **Branch** as `main` unless intentionally releasing another branch.
2. Leave **Version** blank to use the maintained untagged version or automatically increment the latest tag. You may instead enter a new exact version such as `1.5.0`.
3. Select **stable** to publish to the Kodi add-on repository.
4. Leave **Publish the stable release to the Kodi add-on repository** checked.
5. Run the workflow.

The workflow validates and packages the add-on, creates the GitHub release, then directly calls the repository publication workflow. It does not rely on a second workflow being triggered indirectly by the release event.

Drafts and prereleases are not placed in the stable Kodi repository.

## Re-publish an existing release

Use this when a GitHub release exists but `gh-pages` is missing it or shows an older version.

1. Open **Actions → Build and publish Kodi release → Run workflow**.
2. Enter the existing stable version in **Version**, for example `1.4.0` or `v1.4.0`.
3. Select **stable**.
4. Check **Publish the stable release to the Kodi add-on repository**.
5. Run the workflow.

The workflow recognises that the release already exists. It does **not** create a duplicate tag or release. It downloads that release's existing ZIP, regenerates the Kodi repository, force-replaces the generated `gh-pages` branch, and verifies the published files and checksums.

## Repository-only repair workflow

You can also open **Actions → Generate and publish Kodi repository → Run workflow**.

- Enter a stable release tag such as `v1.4.0`, or leave it blank to select the latest stable GitHub release.
- Run the workflow.

This is useful when the GitHub release is correct and only the generated Kodi repository needs repair.

## How to verify publication

After the workflow succeeds:

1. Open [`addons.xml`](addons.xml) and find `id="context.arr.manager"`.
2. Confirm its `version` matches the intended stable release.
3. Open the [repository website](https://cbkii.github.io/kodi-managarr/) and confirm the displayed Kodi Managarr version.
4. Optionally download the [repository ZIP](repository.managarr/repository.managarr.zip) and its [SHA-256 checksum](repository.managarr/repository.managarr.zip.sha256).

The workflow itself also downloads the published files again, verifies both ZIPs, checks their SHA-256 files, and confirms the versions in `addons.xml` before reporting success.
