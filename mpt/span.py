"""Spanning-tree construction: mark a spanning forest on the graph's edges."""
from collections import deque

from .model import MptError

ALGOS = ("bfs", "dfs", "mst")


def span(g, algo="bfs", root=None, maximize=False):
    """Mark spanning-forest edges (``tree`` = True), leave the rest False.

    bfs/dfs start at ``root`` (default: first node) and cover every component.
    mst is Kruskal over edge weights as costs (``maximize`` keeps the heaviest instead).
    Returns (tree_edges, non_tree_edges, components).
    """
    if algo not in ALGOS:
        raise MptError(f"unknown algorithm: {algo} (choose from {', '.join(ALGOS)})")
    if not g.nodes:
        raise MptError("graph is empty")
    if root is not None:
        g.require(root)

    adj = {n: [] for n in g.nodes}
    for i, e in enumerate(g.edges):
        adj[e["src"]].append((e["dst"], i))
        adj[e["dst"]].append((e["src"], i))

    chosen, ncomp = set(), 0
    if algo == "mst":
        uf = {n: n for n in g.nodes}

        def find(x):
            while uf[x] != x:
                uf[x] = uf[uf[x]]
                x = uf[x]
            return x

        order = sorted(range(len(g.edges)), key=lambda i: g.edges[i]["weight"], reverse=maximize)
        for i in order:
            a, b = find(g.edges[i]["src"]), find(g.edges[i]["dst"])
            if a != b:
                uf[a] = b
                chosen.add(i)
        ncomp = len({find(n) for n in g.nodes})
    else:
        starts = ([root] if root else []) + list(g.nodes)
        seen = set()
        for s in starts:
            if s in seen:
                continue
            ncomp += 1
            if algo == "bfs":
                seen.add(s)
                q = deque([s])
                while q:
                    u = q.popleft()
                    for v, i in adj[u]:
                        if v not in seen:
                            seen.add(v)
                            chosen.add(i)
                            q.append(v)
            else:  # dfs: mark on pop so the result is a true depth-first tree
                stack = [(s, None)]
                while stack:
                    u, via = stack.pop()
                    if u in seen:
                        continue
                    seen.add(u)
                    if via is not None:
                        chosen.add(via)
                    stack.extend((v, i) for v, i in reversed(adj[u]) if v not in seen)

    for i, e in enumerate(g.edges):
        e["tree"] = i in chosen
    return len(chosen), len(g.edges) - len(chosen), ncomp
