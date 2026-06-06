"""Pipeline Doctor — drift detection + bounded auto-fix + change-proposal authoring.

Reads the Decision Ledger continuously, surfaces drift signals, and produces
one of two outputs per signal:
  A. AUTO-FIX (within bounded envelopes per department bundle)
  B. PROPOSE-CHANGE (PR opened on standards-bundles/<dept> with ADR)

Cannot directly change rules. Cannot relax PHI rules. Bounded by per-bundle
envelopes. See:
  - openspec/changes/add-pipeline-doctor/proposal.md
  - openspec/changes/add-pipeline-doctor/specs/pipeline-doctor/spec-delta.md
"""
__version__ = "0.7.0"
