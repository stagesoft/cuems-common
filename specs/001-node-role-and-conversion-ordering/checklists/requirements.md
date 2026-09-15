<!--
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Specification Quality Checklist: Node-role conversion ordering, the packaging gate, and the Avahi vocabulary cutover

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-15
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**Iteration 2 (2026-09-15) — all items pass.** The three scoping questions below were answered by the
decision-maker and the spec was rewritten around them; the single `[NEEDS CLARIFICATION]` marker is gone.

(These are the **specification** session's questions. The spec's own `## Clarifications` section
records a later `/speckit-clarify` session with three *different* questions — the live-file
rewrite rule, the sudoers conffile, and the version bound. Re-validated after it: still 16/16.)

| | Question | Answer | Effect on the spec |
|---|---|---|---|
| Q1 | Does the batch document conversion run during the upgrade? | **No — it is an operator command whose responsibility is `cuems-utils`', never a `cuems-common` necessity** | The whole document-conversion user story left this repository. It is now OOS-1, and all that remains here is FR-022: say so in the upgrade documentation. |
| Q2 | What migrates a deployed host's live discovery file? | **postinst migrates it, guarded** | Folded into User Story 1 as FR-004 to FR-008: recognise-or-report, idempotent, never fails the upgrade, effective without a reboot. |
| Q3 | Where is the power-off regression fixed? | **Out of scope — report only** | Its user story left the spec. It is now OOS-2, with FR-023 making the report (evidence plus operator-visible symptom) a deliverable. |

Two of three answers moved work *out* of this repository, which is why the spec has three user
stories rather than five. Neither exclusion is silent: both are recorded in Out of Scope with
the decision, its reasoning, and the consequence an operator will meet.

**Content-quality note.** Two items are met in the sense that matters here rather than
literally. This repository's product *is* packaging, so its "user value" is an operator's
upgrade and its "non-technical stakeholder" is an operator, not a layperson — the spec states
outcomes on a host rather than mechanisms in a file. Where a mechanism is named (a conffile, a
package relationship) it is named as a constraint the outcome must survive, not as a chosen
implementation.

**Carried into planning, not resolved here.**

- OOS-2 leaves a known-broken shipped tool on converted controllers. That is the decision; the
  plan must ensure FR-023's report actually gets written and filed, since nothing else in this
  feature will surface it.
- FR-004's migration writes a file this package does not own. It is acceptable only while the
  node-configuration daemon stays disabled cluster-wide (see Assumptions); if that changes, the
  two writers must be reconciled.
