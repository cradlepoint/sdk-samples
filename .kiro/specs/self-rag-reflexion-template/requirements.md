# Requirements Document

## Introduction

The Self-RAG Reflexion Template is a domain-agnostic, cloneable workspace that implements a self-retrieval-augmented-generation loop with reflexion, generalized so any domain (a language, framework, SDK, API, or toolchain) can be dropped in via configuration. The template packages three cooperating layers — a retrieval layer backed by Kiro steering and local documentation, a reflection layer that forces post-task self-assessment and structured documentation updates, and an action layer of pluggable hooks (setup, verify, deploy) — plus a bootstrap wizard that interviews the user about their target domain and generates the initial scaffolding, and a discovery fallback loop that escalates from local corpus to domain introspection to web search when local retrieval comes up empty, with every learned fact carrying provenance and confidence metadata. The template is cloned once per domain instance; the generic patterns inside the template are protected from domain-specific learnings by enforced path rules.

## Glossary

- **Template**: The generic, domain-agnostic files and directories that ship with the repository and define the self-RAG reflexion patterns. Lives under a protected path (`template/`) and is never mutated by domain-instance learnings.
- **Domain_Instance**: The user's clone of the Template configured for a specific domain. Lives at the repository root alongside the Template directory.
- **Domain_Config**: The collection of TOML files under `.kiro/domain/` (`commands.toml`, `sources.toml`, `hooks.toml`, and optional `metadata.toml`) that declare domain-specific commands, knowledge sources, hook bindings, and domain identity.
- **Retrieval_Layer**: The subsystem composed of Kiro steering files under `.kiro/steering/`, local documentation under `docs/`, and the `load-steering-files` hook that guarantees steering context is loaded every prompt.
- **Reflection_Layer**: The subsystem composed of the reflection mandate (`meta.md`), the structured update procedure (`learn.md`), and the pre-action verification gate (`verify.md`).
- **Action_Layer**: The subsystem composed of Kiro hooks whose commands are read from `Domain_Config` rather than hardcoded (setup, verify, deploy).
- **Discovery_Loop**: The escalation procedure, defined in `discover.md`, invoked when `Retrieval_Layer` returns no relevant results for a question. Proceeds through local docs, local source, domain introspection, web search, fetch-and-summarize, verification, and record.
- **Bootstrap_Wizard**: The three-path interactive setup that generates the initial `Domain_Config` and scaffolds steering and docs skeletons. Available as a Kiro `userTriggered` hook, a Kiro spec, and a standalone Python script; the script is canonical and both other paths invoke it.
- **Provenance**: The metadata on every doc entry recording where the information came from. Required fields: `added` (ISO-8601 date), `source` (one of `local_path`, `command`, `url`, or `user`), and `confidence` (one of `verified` or `unverified`).
- **Quarantine_Directory**: The path `docs/unverified/` where findings from the `Discovery_Loop` are written when they have not been verified by runnable check. Entries are promoted to `docs/` only after verification.
- **Retrieval_Failure**: The agent-judged condition where a ripgrep query over `.kiro/steering/` and `docs/` for the terms relevant to the current question returns no relevant results. The agent MUST log the triggering query when this is declared.
- **Reflection_Gate**: The mandatory self-assessment step that runs on every `agentStop` event.
- **Introspection_Command**: A domain-specific command declared in `Domain_Config` (e.g., `--help`, schema introspection, DTD lookup, `man` pages) used by the `Discovery_Loop` to extract structured information from the domain's own tooling.

## Requirements

### Requirement 1: Template and Domain Instance Isolation

**User Story:** As a template maintainer, I want generic template patterns to live in a protected path distinct from domain-instance learnings, so that cloning the template for a new domain does not inherit unrelated domain-specific knowledge.

#### Acceptance Criteria

1. THE Template SHALL store all generic, domain-agnostic files under the path `template/`.
2. THE Domain_Instance SHALL store all domain-specific files under the repository root outside the `template/` path.
3. WHEN any component of the system attempts a file write targeting a path inside `template/`, THE Reflection_Layer SHALL classify the write as a template mutation and SHALL require the writing component to declare `scope = "template"` in the write call.
4. IF a domain learning produced by the Reflection_Layer targets a path inside `template/` without an explicit `scope = "template"` declaration, THEN THE Reflection_Layer SHALL redirect the write to the corresponding Domain_Instance path and SHALL log the redirection.
5. WHEN the verify hook runs and any file under the Domain_Instance `.kiro/steering/` or `docs/` path contains text that appears byte-for-byte identical to a file under `template/.kiro/steering/` or `template/docs/`, THE verify hook SHALL exit with a non-zero status and SHALL report the offending files as a suspected misclassified generic learning.
6. THE isolation enforcement SHALL NOT depend on git, git hooks, or commit messages.

### Requirement 2: Domain Configuration

**User Story:** As a domain user, I want to declare my domain's commands, knowledge sources, and hook bindings in a structured config, so that the template's action layer and discovery loop operate on my tooling without code changes.

#### Acceptance Criteria

1. THE Domain_Config SHALL reside in the directory `.kiro/domain/`.
2. THE Domain_Config SHALL consist of at minimum three files: `commands.toml`, `sources.toml`, and `hooks.toml`.
3. THE `commands.toml` file SHALL declare the domain's `setup`, `verify`, and `deploy` commands with explicit OS variants where applicable.
4. THE `sources.toml` file SHALL declare the domain's documentation roots, source tree roots, and `Introspection_Command` definitions.
5. THE `hooks.toml` file SHALL declare which Kiro hook events (`promptSubmit`, `agentStop`, `userTriggered`) are bound to which `commands.toml` entries.
6. THE Domain_Config SHALL include a `schema_version` field in each TOML file.
7. WHEN the Action_Layer executes a hook, THE Action_Layer SHALL resolve the command from `commands.toml` at runtime and SHALL NOT contain hardcoded domain commands.
8. IF a required field is missing from the Domain_Config at hook execution time, THEN THE Action_Layer SHALL halt with an error message naming the missing field and the expected file.

### Requirement 3: Retrieval Layer

**User Story:** As a domain user, I want steering files to be loaded every prompt with context-appropriate inclusion rules, so that the agent always has the relevant guardrails and workflows loaded before it acts.

#### Acceptance Criteria

1. THE Retrieval_Layer SHALL support three steering inclusion modes: `always`, `fileMatch` with a `fileMatchPattern`, and `manual` with a shortcut keyword.
2. THE Retrieval_Layer SHALL provide a `load-steering-files` hook bound to `promptSubmit` that invokes the agent's context disclosure tool on every `inclusion: always` steering file.
3. WHEN the user issues one of the shortcut keywords `#verify`, `#discover`, `#learn`, or `#deploy`, THE Retrieval_Layer SHALL load the corresponding steering file.
4. WHILE a prompt is being processed, THE Retrieval_Layer SHALL make loaded steering content available before any tool execution.
5. WHEN the same set of steering files is loaded multiple times in a single session, THE Retrieval_Layer SHALL produce the same effective context as loading them once (retrieval idempotence).

### Requirement 4: Reflection Layer

**User Story:** As a domain user, I want every task to end with a mandatory reflection that triggers a documentation update whenever something is learned (regardless of whether files were edited), so that discoveries from pure research or Q&A turns are captured and not lost.

#### Acceptance Criteria

1. THE Reflection_Layer SHALL provide a steering file `meta.md` that defines the Reflection_Gate.
2. WHEN an `agentStop` event occurs, THE Reflection_Gate SHALL execute regardless of whether any file was modified during the turn.
3. WHEN the Reflection_Gate executes, THE Reflection_Gate SHALL evaluate the turn against the following learning criteria: (a) an assumption was contradicted by evidence, (b) a new fact was discovered about the domain, (c) the Discovery_Loop produced a finding, (d) a gotcha or failure mode was observed, or (e) a better pattern was identified.
4. IF any learning criterion from (a) through (e) is met, THEN THE Reflection_Layer SHALL invoke the `learn.md` procedure and SHALL write an entry to `.kiro/steering/` or `docs/` according to the classification rules in `learn.md`, whether or not any code file was modified during the turn.
5. IF no learning criterion is met, THEN THE Reflection_Gate SHALL exit silently and SHALL NOT write any file or log entry.
6. THE `learn.md` procedure SHALL classify each learning as either generic (applies across domains) or domain-specific (applies only to the current Domain_Instance) before writing.
7. WHEN a learning is classified as generic, THE Reflection_Layer SHALL write it to `template/.kiro/steering/` or `template/docs/` as appropriate and SHALL include `scope = "template"` in the write call.
8. WHEN a learning is classified as domain-specific, THE Reflection_Layer SHALL write it to the Domain_Instance `.kiro/steering/` or `docs/` path.
9. THE Reflection_Layer SHALL provide a pre-action steering file `verify.md` that defines the verification gate used before writing code against an external API or command.

### Requirement 5: Discovery Fallback Loop

**User Story:** As a domain user, I want the agent to follow a defined escalation procedure when local retrieval fails, so that the agent does not guess or hallucinate answers.

#### Acceptance Criteria

1. THE Discovery_Loop SHALL be defined in a steering file `discover.md` with `inclusion: manual` and shortcut keyword `#discover`.
2. WHEN the agent judges that a ripgrep query over `.kiro/steering/` and `docs/` for the terms relevant to the current question returned no relevant results, THE agent SHALL declare Retrieval_Failure and log the triggering query.
3. WHEN Retrieval_Failure is declared, THE Discovery_Loop SHALL execute the following steps in order: (a) search local `docs/`, (b) search local source and config trees declared in `sources.toml`, (c) execute the `Introspection_Command` if one is declared for the current query type, (d) perform web search against sources declared authoritative in `sources.toml`, (e) fetch and summarize promising URLs, (f) verify the finding with a runnable check when possible, (g) record the finding via the Reflection_Layer.
4. THE Discovery_Loop SHALL define an exit condition for every step: `found`, `not_found`, or `escalate_to_user`.
5. THE Discovery_Loop SHALL terminate on every invocation; no step SHALL loop back to a prior step without a documented escalation reason.
6. WHEN a network error is raised during step (d) or step (e), THE Discovery_Loop SHALL record the condition as `network_unavailable`, halt further web steps, and escalate to the user with the partial results.
7. WHEN a finding is recorded in step (g) and has not passed verification in step (f), THE Discovery_Loop SHALL write the finding to the Quarantine_Directory `docs/unverified/`.
8. WHEN a finding is recorded in step (g) and has passed verification in step (f), THE Discovery_Loop SHALL write the finding to `docs/` and SHALL include `source` and `confidence: verified` fields in the front-matter.
9. WHEN a Discovery_Loop invocation resolves a question that has an existing verified entry in `docs/`, THE Discovery_Loop SHALL NOT remove or modify the existing verified entry (discovery monotonicity).
10. IF the user issues the shortcut `#discover`, THEN THE Discovery_Loop SHALL execute even in the absence of declared Retrieval_Failure.

### Requirement 6: Pluggable Action Layer

**User Story:** As a domain user, I want the setup, verify, and deploy hooks to read their commands from Domain_Config, so that I can retarget the template to a new domain without editing hook definitions.

#### Acceptance Criteria

1. THE Action_Layer SHALL provide a `setup` hook bound to `promptSubmit` that reads its command from `commands.toml` at the `setup` key.
2. THE Action_Layer SHALL provide a `verify` hook bound to the event declared in `hooks.toml` that reads its command from `commands.toml` at the `verify` key.
3. THE Action_Layer SHALL provide a `deploy` hook bound to `agentStop` that reads its command from `commands.toml` at the `deploy` key.
4. THE Action_Layer SHALL select the correct OS variant (for example `posix` or `windows`) at hook execution time based on the current platform.
5. IF a hook is invoked and its corresponding command is absent or empty in `commands.toml`, THEN THE Action_Layer SHALL skip the hook and record a skipped-hook log entry with the hook name and the missing key.

### Requirement 7: Bootstrap Wizard

**User Story:** As a new domain user, I want an interactive wizard that interviews me about my domain and generates the initial Domain_Config and steering skeleton, so that I can start productive work without hand-authoring configuration files.

#### Acceptance Criteria

1. THE Bootstrap_Wizard SHALL provide three entry paths: a Kiro `userTriggered` hook, a Kiro spec template, and a standalone Python script.
2. THE standalone Python script SHALL be the canonical implementation; THE Kiro hook and THE Kiro spec SHALL invoke the script to perform file generation.
3. THE Bootstrap_Wizard SHALL collect, at minimum, the following fields: domain name, primary language or framework, documentation root URLs or paths, `setup` command, `verify` command, `deploy` command, and any `Introspection_Command` definitions.
4. WHEN the Bootstrap_Wizard completes successfully, THE Bootstrap_Wizard SHALL write `.kiro/domain/commands.toml`, `.kiro/domain/sources.toml`, and `.kiro/domain/hooks.toml`.
5. WHEN the Bootstrap_Wizard completes successfully, THE Bootstrap_Wizard SHALL write an initial Domain_Instance steering skeleton including `setup.md`, `verify.md`, `discover.md`, `learn.md`, `meta.md`, and `deploy.md`.
6. WHEN the Bootstrap_Wizard is invoked on a repository that already contains a populated `.kiro/domain/` directory, THE Bootstrap_Wizard SHALL prompt for confirmation before overwriting any existing file.
7. IF the Bootstrap_Wizard is invoked with identical inputs on an empty repository twice, THEN the generated `.kiro/domain/` contents SHALL be byte-identical across the two invocations (bootstrap determinism).

### Requirement 8: Provenance and Confidence Tracking

**User Story:** As a domain user, I want every documentation entry written by the system to carry traceable provenance and a confidence level, so that unverified findings cannot silently pollute the knowledge base.

#### Acceptance Criteria

1. THE Reflection_Layer and THE Discovery_Loop SHALL write every new documentation entry with YAML front-matter containing the fields `added`, `source`, and `confidence`.
2. THE `added` field SHALL contain an ISO-8601 date.
3. THE `source` field SHALL contain exactly one of: a local file path, a command invocation, a URL, or the token `user`.
4. THE `confidence` field SHALL contain exactly one of the tokens `verified` or `unverified`.
5. WHEN a documentation entry is promoted from `docs/unverified/` to `docs/`, THE Reflection_Layer SHALL update the `confidence` field from `unverified` to `verified` and SHALL append the verification command or check to the `source` field.
6. THE verify hook SHALL scan all files under `.kiro/steering/` and `docs/` and SHALL exit non-zero if any entry is missing a required provenance field.

### Requirement 9: Parser and Serializer for Domain Config

**User Story:** As a template maintainer, I want a parser and pretty-printer for `Domain_Config` files, so that the bootstrap wizard, action hooks, and verify hook all read and write the config through a single verified interface.

#### Acceptance Criteria

1. THE Template SHALL provide a Parser that reads `commands.toml`, `sources.toml`, and `hooks.toml` into a typed Domain_Config object following the TOML specification v1.0.0.
2. THE Template SHALL provide a Pretty_Printer that serializes a Domain_Config object back into TOML text.
3. WHEN an invalid TOML file is provided to the Parser, THE Parser SHALL return a descriptive error identifying the file, line, and nature of the failure.
4. WHEN a Domain_Config object is required that is missing a required field, THE Parser SHALL return a descriptive error naming the missing field.
5. FOR ALL valid Domain_Config objects, parsing then printing then parsing SHALL produce an equivalent object (round-trip property).

### Requirement 10: Network and Rate-Limit Handling in Discovery

**User Story:** As a domain user operating in a restricted or rate-limited environment, I want the discovery loop to handle network failures gracefully, so that the loop terminates with a useful partial result rather than hanging or retrying indefinitely.

#### Acceptance Criteria

1. WHEN a web request in the Discovery_Loop raises a network error, THE Discovery_Loop SHALL catch the error and record the condition as `network_unavailable`.
2. WHEN a web request in the Discovery_Loop returns an HTTP 429 or an equivalent rate-limit signal, THE Discovery_Loop SHALL halt further web requests for the remainder of the invocation and record the condition as `rate_limited`.
3. THE Discovery_Loop SHALL enforce a maximum of three web-fetch round-trips per search hit during a single invocation.
4. WHEN the Discovery_Loop terminates with either `network_unavailable` or `rate_limited`, THE Discovery_Loop SHALL escalate to the user with the partial results gathered up to that point.

### Requirement 11: Shortcut Keyword Routing

**User Story:** As a domain user, I want a consistent set of keyboard shortcuts to invoke steering workflows, so that I can reach verify, discover, learn, and deploy behaviors without typing file paths.

#### Acceptance Criteria

1. THE Retrieval_Layer SHALL recognize the shortcut `#verify` and SHALL load the steering file `verify.md`.
2. THE Retrieval_Layer SHALL recognize the shortcut `#discover` and SHALL load the steering file `discover.md`.
3. THE Retrieval_Layer SHALL recognize the shortcut `#learn` and SHALL load the steering file `learn.md`.
4. THE Retrieval_Layer SHALL recognize the shortcut `#deploy` and SHALL load the steering file `deploy.md`.
5. WHEN a user-defined shortcut is declared in the Domain_Config, THE Retrieval_Layer SHALL recognize it alongside the default shortcuts.
