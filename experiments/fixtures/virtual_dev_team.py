#!/usr/bin/env python3
"""virtual_dev_team.py — a reusable "agents-as-roles" fixture.

Defines a small VIRTUAL PRODUCT ("Meridian", a customer-neutral patient
self-service portal) and a VIRTUAL DEV TEAM of agent roles + a human lead, so
pipeline/graph/ledger features can be exercised against a stable, legible cast
without spending real LLM calls or touching a live customer.

This is the canonical fixture behind scripts/seed_graph_demo.py. Import ROLES
and PRODUCT from here rather than redefining actors inline, so every test that
seeds decisions uses the same named team and the graph views render a coherent
story.

Customer-neutrality: "Meridian" is invented sample data; the roles are generic
pipeline personas (mirroring .github/agents/*.agent.md). No named engagement.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Role:
    """One member of the virtual dev team."""
    key: str
    kind: str  # "agent" | "human"
    id: str
    display_name: str
    responsibility: str

    def actor(self) -> dict:
        """Ledger `actor` object for this role."""
        return {"kind": self.kind, "id": self.id, "display_name": self.display_name}


# ── The virtual dev team (agents as roles + one human lead) ──────────────────
# Mirrors the repo's real pipeline personas (.github/agents/) so the fixture is
# faithful to how the production pipeline attributes decisions.
ROLES: dict[str, Role] = {
    "assessor": Role(
        "assessor", "agent", "assessor-agent@meridian", "Assessor Agent",
        "Classifies PRD ambiguities into typed cards (PHI, auth, retention, naming, SLA).",
    ),
    "architect": Role(
        "architect", "agent", "architect-agent@meridian", "Architect Agent",
        "Proposes architecture given resolved decisions; owns naming + SLA calls.",
    ),
    "codegen": Role(
        "codegen", "agent", "codegen-agent@meridian", "CodeGen Agent",
        "Generates code aligned to architecture decisions.",
    ),
    "review": Role(
        "review", "agent", "review-agent@meridian", "Review/Scan Agent",
        "Pre-merge review — SBOM + SAST + secret scan.",
    ),
    "lead": Role(
        "lead", "human", "idan@contoso.com", "Idan (Lead)",
        "Human lead; owns high-risk calls (PHI, auth, retention) and teaches the loop.",
    ),
}


@dataclass(frozen=True)
class Product:
    """The virtual product the team builds across runs."""
    name: str
    tagline: str
    modules: list[str] = field(default_factory=list)


PRODUCT = Product(
    name="Meridian",
    tagline="A customer-neutral patient self-service portal (sample product).",
    modules=["messaging", "appointments", "billing"],
)

# Standards rules the team's decisions cite (become graph hub nodes).
BUNDLE_RULES = {
    "phi": "security/v0.1.0/PHI-001",
    "auth": "security/v0.1.0/AUTH-002",
    "retention": "privacy/v0.1.0/RETAIN-004",
    "naming": "architect/v0.1.0/NAMING-001",
    "sla": "architect/v0.1.0/SLA-007",
}


def role(key: str) -> Role:
    return ROLES[key]


def actor(key: str) -> dict:
    return ROLES[key].actor()


if __name__ == "__main__":
    print(f"Virtual product: {PRODUCT.name} — {PRODUCT.tagline}")
    print(f"Modules: {', '.join(PRODUCT.modules)}\n")
    print("Virtual dev team:")
    for r in ROLES.values():
        print(f"  {r.display_name:20} [{r.kind:5}] {r.responsibility}")
    print("\nBundle rules cited:")
    for k, v in BUNDLE_RULES.items():
        print(f"  {k:10} {v}")
