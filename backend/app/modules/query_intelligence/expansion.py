"""Context expansion: enrich query entities with domain synonyms.

A curated enterprise-domain synonym map generates alternative phrasings
of the detected entities. The expansions are fed into retrieval so a
query about "leave policy" also surfaces chunks about "vacation rules".
Deterministic by construction (stable ordering, no randomness).
"""

_SYNONYMS: dict[str, list[str]] = {
    "policy": ["rules", "guidelines", "procedure"],
    "leave": ["vacation", "time off", "absence"],
    "employee": ["staff", "personnel", "worker"],
    "employees": ["staff", "personnel", "workers"],
    "salary": ["compensation", "pay", "wages"],
    "pay": ["compensation", "salary"],
    "remote": ["work from home", "hybrid", "telecommuting"],
    "benefits": ["perks", "entitlements"],
    "termination": ["dismissal", "offboarding"],
    "hiring": ["recruitment", "onboarding"],
    "security": ["protection", "safeguards"],
    "budget": ["spending", "costs"],
    "deadline": ["due date", "cutoff"],
    "meeting": ["sync", "call"],
    "training": ["onboarding", "learning"],
    "expense": ["reimbursement", "spending"],
    "contract": ["agreement", "terms"],
    "holiday": ["public holiday", "leave"],
    "sick": ["illness", "medical"],
    "parental": ["maternity", "paternity"],
    "drift": ["change", "evolution"],
    "retrieval": ["search", "lookup"],
    "document": ["file", "record"],
}

# Head nouns that commonly appear with an implicit "employee" qualifier.
_EMPLOYEE_TOPICS = frozenset({"leave", "benefits", "salary", "training", "expense"})


def expand_entities(entities: list[str], *, max_expansions: int = 6) -> list[str]:
    """Alternative phrasings for the given entities (originals excluded)."""
    expansions: list[str] = []

    def add(phrase: str) -> None:
        phrase = phrase.strip()
        if phrase and phrase not in expansions and phrase not in entities:
            expansions.append(phrase)

    for entity in entities:
        words = entity.split()
        # Implicit-qualifier variant first: "leave ..." -> "employee leave".
        for word in words:
            if word in _EMPLOYEE_TOPICS:
                add(f"employee {word}")
        # Single-word substitutions: "leave policy" -> "vacation policy",
        # "leave rules", ...
        for i, word in enumerate(words):
            for synonym in _SYNONYMS.get(word, []):
                add(" ".join([*words[:i], synonym, *words[i + 1 :]]))

    return expansions[:max_expansions]
