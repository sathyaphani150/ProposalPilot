from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.confidence import calculate_agent_confidence
from app.war_room.llm_provider import get_war_room_llm_provider

SYSTEM_PROMPT = """
You are the Tech Architect on an internal proposal war room team. You
bring 15+ years of solution architecture experience across web platforms,
data systems, and enterprise integrations. Your job is to propose a
concrete, buildable, opportunity-specific technical direction - not a
generic "modern, scalable, secure" template.

EVIDENCE HIERARCHY - use in this strict order of trust:
1. RFP analysis fields (functional/non-functional requirements,
   integration_needs, data_needs, compliance_needs) - ground truth.
2. Retrieved past-project matches - only claim reuse or experience tied to
   a SPECIFIC matched project; cite which one. Never imply experience that
   isn't backed by a retrieved match.
3. Call notes - client-confirmed detail, more trustworthy than your own
   inference but less than the RFP analysis itself.
4. Your own inference - only to fill structural gaps the above three
   don't cover. Every such inference MUST be listed in `assumptions`,
   never folded into the main recommendation as if it were a known fact.

ARCHITECTURE PATTERN SELECTION - choose one and justify it against the
opportunity's actual signals, don't default to microservices by habit:
- Modular monolith: prefer when the team/timeline is small, requirements
  are still being clarified (high missing_information count), or the
  evaluators are likely cost-sensitive.
- Microservices / service-oriented: justify only if there are genuinely
  independent scaling domains, multiple integration_needs implying
  separate bounded contexts, or an explicit NFR for independent
  team/service deployment.
- Event-driven / async: recommend when integration_needs include
  real-time data flows, webhooks, or systems that must stay eventually
  consistent rather than synchronously coupled.

NON-FUNCTIONAL REQUIREMENT MAPPING - for every item in the RFP analysis's
non_functional_requirements, name the specific architectural decision that
addresses it (e.g. "sub-second search latency" -> "vector index + caching
layer"), not a restated requirement with nothing attached to it.

COMPLIANCE-DRIVEN CONTROLS - if compliance_needs names a specific
framework (HIPAA, PCI-DSS, GDPR, SOC2, or similar), call out the
architectural controls that follow from it (encryption at rest/in
transit, audit logging, RBAC, data residency, retention policy) rather
than a vague "we will ensure compliance" statement.

REUSE-FIRST PRINCIPLE - if a retrieved past-project match has reusable
components relevant to this RFP, prefer recommending reuse over a net-new
build for that component and say so explicitly. Only design net-new where
no match supports reuse.

If human_overrides contains architecture guidance (e.g. "keep architecture
simple", "use offshore-heavy model"), apply it and state in one sentence
what changed because of it.

OUTPUT FIELDS:
- architecture_summary: 2-4 sentences naming the actual core workflow and
  chosen pattern, not generic language.
- architecture_pattern: one of "modular monolith" | "microservices" |
  "event-driven" | "hybrid", plus a one-sentence justification.
- recommended_stack: max 6 items, each tied to a stated requirement.
- reusable_components: empty list if no retrieved match supports reuse.
- assumptions: every tier-4 inference goes here, nowhere else.

Return JSON matching the schema.
"""


class ArchitectOutput(BaseModel):
    architecture_summary: str
    architecture_pattern: str = ""
    recommended_stack: list[str] = Field(default_factory=list)
    reusable_components: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    technical_risks: list[str] = Field(default_factory=list)
    validation_questions: list[str] = Field(default_factory=list)
    reasoning: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def _override_text(state: dict[str, Any]) -> str:
    overrides = state.get("user_overrides") or []
    parts: list[str] = []
    for item in overrides:
        if not isinstance(item, dict):
            continue
        override = item.get("override")
        if isinstance(override, dict):
            parts.extend(
                str(value).strip()
                for value in override.values()
                if isinstance(value, str) and value.strip()
            )
        elif isinstance(override, str) and override.strip():
            parts.append(override.strip())
    call_notes = state.get("call_notes")
    if isinstance(call_notes, str) and call_notes.strip():
        parts.append(call_notes.strip())
    return " | ".join(parts)


def _suggest_stack(analysis: dict[str, Any], domain_tags: list[str]) -> list[str]:
    business_problem = str(analysis.get("business_problem") or "").lower()
    integration_needs = [str(item).lower() for item in (analysis.get("integration_needs") or [])]
    non_functional = [str(item).lower() for item in (analysis.get("non_functional_requirements") or [])]
    compliance_needs = [str(item).lower() for item in (analysis.get("compliance_needs") or [])]
    tags_text = " ".join(domain_tags).lower()
    combined = " ".join([business_problem, tags_text, *integration_needs, *non_functional, *compliance_needs])

    if any(keyword in combined for keyword in ["bus", "fleet", "vehicle", "manufactur", "procurement", "supply", "commissioning"]):
        stack = [
            "ERP and supply-chain workflow platform",
            "Vendor and contract management portal",
            "QA inspection and commissioning tracker",
            "Document management and compliance repository",
        ]
        if integration_needs:
            stack.append("API and EDI integration layer")
        if any(keyword in combined for keyword in ["gps", "telemetry", "tracking", "maintenance", "operations"]):
            stack.append("Fleet operations and telemetry module")
        return stack[:6]

    if any(keyword in combined for keyword in ["health", "patient", "hospital", "clinic"]):
        stack = [
            "Secure application services",
            "Clinical or operational data store",
            "Identity and access control",
            "Audit logging and reporting layer",
        ]
        if integration_needs:
            stack.append("Healthcare system integration layer")
        if any("search" in item or "latency" in item for item in non_functional):
            stack.append("Indexed search and caching layer")
        return stack[:6]

    stack = ["FastAPI", "PostgreSQL", "LangGraph", "Qdrant"]
    if integration_needs:
        stack.append("Adapter layer")
    if any("search" in tag.lower() or "retrieval" in tag.lower() for tag in domain_tags):
        stack.append("Semantic retrieval pipeline")
    if any("data" in tag.lower() or "analytics" in tag.lower() for tag in domain_tags):
        stack.append("Governed data services")
    if any("security" in tag.lower() or "compliance" in tag.lower() for tag in domain_tags):
        stack.append("Security control plane")
    return stack[:6]


def _fallback(state: dict[str, Any]) -> ArchitectOutput:
    analysis = state.get("rfp_analysis") or {}
    context = state.get("similar_projects") or []
    session_title = str(state.get("session_title") or "the RFP")
    client_name = str(state.get("client_name") or "the client")
    business_problem = str(analysis.get("business_problem") or "an unclarified proposal opportunity")
    domain_tags = [str(tag).replace("_", " ") for tag in (analysis.get("domain_tags") or [])[:4]]
    override_text = _override_text(state)
    missing_information = analysis.get("missing_information") or []
    integration_needs = analysis.get("integration_needs") or []
    non_functional = analysis.get("non_functional_requirements") or []
    compliance_needs = [str(item) for item in (analysis.get("compliance_needs") or [])]
    stack = _suggest_stack(analysis, domain_tags)
    pattern = "modular monolith"
    pattern_justification = "Preferred because scope is still being clarified and a simpler delivery shape reduces coordination overhead."
    if any(word in override_text.lower() for word in ["simple", "mvp", "fixed-price", "fixed price"]):
        pattern_justification = "Selected to honor the override to keep scope and operating complexity controlled."
    elif any(
        any(signal in str(item).lower() for signal in ["real-time", "realtime", "webhook", "event", "stream"])
        for item in integration_needs
    ):
        pattern = "event-driven"
        pattern_justification = "Selected because the integration profile suggests asynchronous coordination across systems."
    elif len(integration_needs) >= 3 and len(missing_information) <= 1:
        pattern = "microservices"
        pattern_justification = "Selected because multiple integration domains imply clearer bounded contexts and independent scaling concerns."
    elif integration_needs and non_functional:
        pattern = "hybrid"
        pattern_justification = "Selected because the opportunity combines integration-heavy workflows with non-functional demands that benefit from selective decomposition."
    reusable_components = [
        f"{project.get('title')} pattern"
        for project in context[:3]
        if isinstance(project, dict) and project.get("title")
    ]
    return ArchitectOutput(
        architecture_summary=(
            f"Use a {pattern} architecture for {session_title} at {client_name}. "
            f"The current business problem is: {business_problem}. "
            "Keep workflow, retrieval, proposal assembly, and integration boundaries explicit so delivery can stay modular and controllable. "
            f"The architecture should directly address {len(integration_needs)} integration signals, {len(non_functional)} non-functional requirements, and compliance controls such as "
            f"{', '.join(compliance_needs[:2]) if compliance_needs else 'auditability and access control'}."
            + (f" Human override applied: {override_text}." if override_text else "")
        ),
        architecture_pattern=f"{pattern}: {pattern_justification}",
        recommended_stack=stack[:6],
        reusable_components=reusable_components[:6],
        assumptions=[
            f"{client_name} will confirm integration access and data ownership.",
            "Initial delivery can start with the selected architecture pattern and evolve selectively once operational evidence is available.",
            f"Domain focus: {', '.join(domain_tags) if domain_tags else 'general proposal workflow'}.",
        ],
        technical_risks=[
            *(
                item
                for item in [
                    "Unverified external APIs can delay delivery." if analysis.get("integration_needs") else "",
                    "Compliance and security controls may require dedicated implementation time." if analysis.get("compliance_needs") else "",
                    "Weak retrieval evidence can reduce proposal credibility." if context else "",
                ]
                if item
            ),
            *[f"Timeline risk: {item}" for item in (analysis.get("timeline_risks") or [])[:2]],
        ],
        validation_questions=[
            f"Which systems are authoritative for the {', '.join(domain_tags[:2]) if domain_tags else 'core'} data domains?",
            "What non-functional requirements are truly mandatory for go-live?",
            "Which reusable assets from prior projects are most relevant to this opportunity?",
            f"What specifically makes {session_title} different from other opportunities in the pipeline?",
        ],
        reasoning=(
            f"Architecture decisions are grounded in {len(context)} context items, {len(domain_tags)} domain tags, {len(non_functional)} non-functional requirements, and complexity {analysis.get('estimated_complexity') or 'medium'}."
            + (f" Override changed the scope toward: {override_text}." if override_text else "")
        ),
    )


async def run_architect_agent(state: dict[str, Any]) -> dict[str, Any]:
    provider = get_war_room_llm_provider()
    analysis = state.get("rfp_analysis") or {}
    prompt = f"""
{SYSTEM_PROMPT}

RFP analysis: {analysis}
Retrieved context: {state.get('retrieved_context') or []}
Call notes: {state.get('call_notes') or ''}
User overrides: {state.get('user_overrides') or []}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt=SYSTEM_PROMPT,
        user_content=prompt,
        output_schema=ArchitectOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    payload = output.model_dump()
    generated_by = "llm" if structured else "deterministic_fallback"
    payload["generated_by"] = generated_by
    payload["confidence"] = calculate_agent_confidence(
        agent="architect",
        state=state,
        payload=payload,
        generated_by=generated_by,
    )
    return {"architect_output": payload}
