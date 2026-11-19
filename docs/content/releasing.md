# Releasing and Deploying

## How a release happens

The function apps are released together, as a set, from GitHub releases:

1. Merge the changes into `main`.
1. Create a GitHub release with a semantic version tag, for example `1.9.3`.
   Mark it as a pre-release if it is not ready for general use.
1. The `deploy.yml` workflow triggers on the `released` and `prereleased`
   events and, for each of the three apps in turn, exports the main
   dependencies to a `requirements.txt`, builds the Docker image and pushes it
   to Docker Hub.

Note that the `version` field in each `pyproject.toml` is fixed at `0.1.0`.
Do not change it — the release tag, not the package version, is what
identifies a release.

## Image tags

Each app is published as `turingrc/rctab-<function>`, where `<function>` is
`usage`, `status` or `controller`. Every build is pushed with two tags:

- the full release tag, for example `turingrc/rctab-usage:1.9.3`; and
- a rolling major-version tag, either `<major>.latest` for a full release or
  `<major>.prerelease` for a pre-release, for example
  `turingrc/rctab-usage:1.latest`.

Deployed function apps track the rolling tag, so publishing a release is what
rolls the new code out. Pin the full tag if you need a fixed version.

## Deployment

Function app Azure resources are created and configured by the RCTab Infrastructure
repository, using Pulumi, and by default pull the latest RCTab images from
Docker Hub — see the
[RCTab docs](https://rctab.readthedocs.io/) for the deployment itself.

To deploy custom code you need your own registry (Docker Hub or an Azure
Container Registry) and can either build and push images by hand or fork this
repository and use the `deploy.yml` workflow.

Once deployed, each function runs on the timer trigger in its
`function.json`: `usage`, `status` and `controller` run hourly, and
`monthly_usage` runs every two hours on the 7th and 8th of each month to pick
up the previous month's data. See [Setup](setup.md) for how to trigger a run
manually.

## Docs

The documentation on
[rctab-functions.readthedocs.io](https://rctab-functions.readthedocs.io/) is
built by Read the Docs from `docs/` on every push, using `.readthedocs.yaml`.
Because Sphinx imports the function app modules to generate the docstring
pages, adding a dependency to a function app can break the docs build.
