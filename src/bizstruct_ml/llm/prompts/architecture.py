from bizstruct_ml.schemas.project import ProjectState
from ._shared import bilingual_system, context_section

_EPICENTERS = """\
- resource_driven — the model is built around a key resource (technology, patent, brand, location).
- offer_driven — the model is built around a novel value proposition that creates a new market.
- customer_driven — the model is built around a customer need, segment, or access channel.
- finance_driven — the model is built around a novel revenue stream, pricing mechanism, or cost structure.
- multiple_epicenter — several of the above shift together as one coherent redesign."""

_PATTERNS = """\
- unbundling — separating customer-relationship, product-innovation, and infrastructure businesses that were previously combined.
- long_tail — offering a large number of niche products, each sold in small volume.
- multi_sided_platform — connecting two or more distinct, interdependent customer groups.
- free — at least one segment pays nothing, subsidized by another part of the model. Requires pattern_subtype:
  - freemium — a free tier funds itself by converting a share of users to a paid tier.
  - ad_supported — a free product/content is monetized through advertising to a third party.
  - bait_and_hook — an initial low-cost/free offer locks in continuous, later purchases.
- open_business_model — value is created by systematically collaborating with outside partners. Requires pattern_subtype:
  - outside_in — the model draws in external ideas/partners to feed internal innovation.
  - inside_out — the model licenses out or exposes internal ideas/assets for external parties to build on."""


def build_messages(project: ProjectState) -> list[dict]:
    user = f"""Project: {project.title}
Idea: {project.idea}{context_section(project)}

Classify this business model's architecture, using the already-generated
Business Model Canvas above as the basis for both choices.

1. epicenter — the primary driver of business model innovation. Choose exactly one:
{_EPICENTERS}

2. pattern — the dominant business model pattern. Choose exactly one:
{_PATTERNS}

3. pattern_subtype:
   - REQUIRED if pattern is "free" or "open_business_model" — pick the subtype that
     actually matches this idea's economics (do not default to the same subtype
     every time; freemium, ad-supported, and bait-and-hook are different revenue
     mechanics and must be told apart).
   - FORBIDDEN (must be omitted/null) for "unbundling", "long_tail", and
     "multi_sided_platform".

4. Rationale — for both the epicenter and the pattern, write a substantive
   explanation (roughly 2-4 sentences, specific to this idea, not generic
   boilerplate) in BOTH Ukrainian and English:
   - epicenter_rationale_uk / epicenter_rationale_en
   - pattern_rationale_uk / pattern_rationale_en"""
    return [
        {"role": "system", "content": bilingual_system()},
        {"role": "user", "content": user},
    ]
