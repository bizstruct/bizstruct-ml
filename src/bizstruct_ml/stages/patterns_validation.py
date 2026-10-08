"""Structural validation of a Patterns answer, on the ml side. TEMPORARY.

The pairwise NetScore and the compatibility graph are the Patterns prompt's
proposal (not from the book, see ml ADR-0001). The domain cannot check the model's
arithmetic, so this module checks that the answer is *structurally* what the
prompt's method implies:

1. every unordered pair of segment aliases is scored exactly once;
2. every alias is in exactly one group;
3. the groups are exactly the connected components of the graph whose edges are
   the pairs with `synergy + conflict >= EDGE_THRESHOLD`.

It must disappear when NetScore moves into the domain (the domain would then
compute the scores and groups itself). That is why it imports nothing from the
rest of the package: plain strings and ints in, `ValueError` out, so deleting
the file and its one call site removes the whole thing.
"""

from collections.abc import Sequence
from itertools import combinations

EDGE_THRESHOLD = -1  # NetScore >= -1: no hard conflict, the two segments may share a canvas


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _alias_order(aliases: Sequence[str]) -> dict[str, int]:
    return {alias: i for i, alias in enumerate(aliases)}


def components(aliases: Sequence[str], edges: Sequence[tuple[str, str]]) -> list[list[str]]:
    """Connected components, each sorted by `aliases` order, components ordered by their first alias."""
    order = _alias_order(aliases)
    parent = {alias: alias for alias in aliases}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    grouped: dict[str, list[str]] = {}
    for alias in aliases:
        grouped.setdefault(find(alias), []).append(alias)
    return sorted((sorted(g, key=order.__getitem__) for g in grouped.values()), key=lambda g: order[g[0]])


def validate_patterns_structure(
    aliases: Sequence[str],
    scores: Sequence[tuple[str, str, int, int]],
    groups: Sequence[Sequence[str]],
) -> None:
    """Raise `ValueError` with every problem found.

    `aliases`: all segment aliases of the project, in order (S1..SN).
    `scores`: (alias_a, alias_b, synergy, conflict) as the model wrote them.
    `groups`: the aliases of each group as the model wrote them.
    """
    known = set(aliases)
    problems: list[str] = []

    # 1. every unordered pair exactly once
    seen: dict[tuple[str, str], int] = {}
    for a, b, _, _ in scores:
        for alias in (a, b):
            if alias not in known:
                problems.append(f"pairwise_scores names the unknown alias '{alias}' (known: {', '.join(aliases)})")
        seen[_pair(a, b)] = seen.get(_pair(a, b), 0) + 1
    expected_pairs = {_pair(a, b) for a, b in combinations(aliases, 2)}
    missing = sorted(expected_pairs - seen.keys())
    if missing:
        problems.append("pairwise_scores is missing the pairs " + ", ".join(f"{a}-{b}" for a, b in missing))
    repeated = sorted(p for p, n in seen.items() if n > 1 and p in expected_pairs)
    if repeated:
        problems.append("pairwise_scores scores these pairs more than once: " + ", ".join(f"{a}-{b}" for a, b in repeated))

    # 2. every alias in exactly one group
    if any(not group for group in groups):
        problems.append("a group has no aliases")
    count: dict[str, int] = {}
    for group in groups:
        for alias in group:
            if alias not in known:
                problems.append(f"groups names the unknown alias '{alias}' (known: {', '.join(aliases)})")
            count[alias] = count.get(alias, 0) + 1
    absent = [alias for alias in aliases if alias not in count]
    if absent:
        problems.append("these aliases are in no group: " + ", ".join(absent))
    twice = [alias for alias in aliases if count.get(alias, 0) > 1]
    if twice:
        problems.append("these aliases are listed more than once in the groups: " + ", ".join(twice))

    # 3. the groups are the connected components (only meaningful once 1 and 2 hold)
    if not problems:
        edges = [(a, b) for a, b, synergy, conflict in scores if synergy + conflict >= EDGE_THRESHOLD]
        expected = components(aliases, edges)
        got = sorted((sorted(g, key=_alias_order(aliases).__getitem__) for g in groups), key=lambda g: aliases.index(g[0]))
        if got != expected:
            problems.append(
                "the groups must be the connected components of the graph of pairs with synergy + conflict >= "
                f"{EDGE_THRESHOLD}. From your scores the components are {_show(expected)}, but you wrote {_show(got)}"
            )
    if problems:
        raise ValueError("; ".join(problems))


def _show(groups: Sequence[Sequence[str]]) -> str:
    return "[" + ", ".join("{" + ", ".join(g) + "}" for g in groups) + "]"
