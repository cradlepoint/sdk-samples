# Security Policy

## About this policy

This repository (`cradlepoint/sdk-samples`) contains sample and demonstration
applications for the Ericsson Cradlepoint NCOS SDK. It is published as free and
open-source software under Ericsson's brand.

Ericsson acts as an **Open Source Software Steward** for this repository under the
EU Cyber Resilience Act (CRA). This policy documents how to report security issues,
what is in and out of scope, and the response you can expect.

## Scope

**In scope**

- The security and integrity of this repository itself: its contents, release
  artifacts (the built app packages published under the
  [`built_apps`](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps)
  release), build/CI configuration (`.github/workflows/`), and the repository's
  GitHub configuration.
- Vulnerabilities in the shared SDK libraries maintained in this repository that are
  common to the samples (for example `cp.py`, `make.py`, `setup_env.py`).
- Reports that a published artifact has been tampered with or that a contributor
  account or GitHub Action has been compromised.

**Out of scope**

- The behavior, correctness, or security of individual sample application code under
  `apps/`. These are provided as **known-working examples**, not as supported
  products. Ericsson supports the platform (NCM deployment and NCOS app execution)
  but does **not** support the application code itself. See *What Ericsson supports*
  below.
- The NCOS operating system, NetCloud Manager (NCM), and Cradlepoint router hardware
  and firmware. These are commercial products with their own support and security
  reporting channels — see *Reporting a vulnerability in the platform* below.
- Vulnerabilities that exist only because a sample was modified, extended, or
  combined with other code after it was copied from this repository.

## What Ericsson supports

Ericsson supports the **platform**: deploying apps through NetCloud Manager and
running them on NCOS. The sample apps in this repository are provided as examples
that are known to work at the time of publication. The individual application code is
not sold as a product and is not supported as one. Use it as a starting point and
review and test it before deploying to production routers.

## Reporting a vulnerability

### A vulnerability in this repository (in scope)

Please report privately. **Do not open a public issue for a security vulnerability.**

- Use GitHub's **private vulnerability reporting**: go to the **Security** tab of this
  repository and click **Report a vulnerability**. This opens a private advisory
  visible only to you and the maintainers.

Please include:

- The affected file(s), release artifact, or configuration.
- A description of the issue and its potential impact.
- Steps to reproduce, a proof of concept, or a patch if you have one.
- Any relevant version, commit hash, or release tag.

### A vulnerability in the platform (NCOS, NCM, hardware/firmware)

Vulnerabilities in Ericsson Cradlepoint products — as opposed to this sample
repository — should be reported to Ericsson's Product Security Incident Response Team
(PSIRT). See the PSIRT page for how to contact them and what to include:

- https://www.ericsson.com/en/about-us/security/psirt

If you are unsure whether an issue is in this repository or in the platform, report it
privately here and we will route it appropriately.

## Response expectations

As a Steward, Ericsson provides best-effort handling of in-scope reports:

- **Acknowledgement:** within 10 business days of receipt.
- **Initial assessment:** we will confirm whether the report is in scope and provide
  an initial severity assessment.
- **Resolution:** for confirmed in-scope issues, we will work on a fix or mitigation
  and coordinate disclosure with you. Timelines depend on severity and complexity.

Reports that are out of scope (for example, issues in individual sample app code or in
the platform) will be acknowledged and redirected to the appropriate channel rather
than fixed under this policy.

## Supported versions

Security maintenance applies only to the **latest** state of the `master` branch and
the most recent set of published
[built app artifacts](https://github.com/cradlepoint/sdk-samples/releases/tag/built_apps).
Older commits, tags, and previously published artifacts are **not** maintained. If you
are running an older copy, update to the latest version before reporting an issue.

## Coordinated disclosure

We ask that you give us a reasonable opportunity to investigate and remediate an
in-scope issue before any public disclosure. We will keep you informed of progress and
credit reporters who wish to be acknowledged.
