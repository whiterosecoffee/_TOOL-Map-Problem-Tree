"""Free-tree algorithms: adjacency, centre, re-rooting, walks, paths."""
from collections import deque, namedtuple

from .model import MptError

View = namedtuple("View", "adj parent children root")


def adjacency(nodes, edges):
    adj = {n: [] for n in nodes}
    for e in edges:
        adj[e["src"]].append(e["dst"])
        adj[e["dst"]].append(e["src"])
    return adj


def components(adj):
    seen, out = set(), []
    for start in adj:
        if start in seen:
            continue
        comp, q = [start], deque([start])
        seen.add(start)
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    comp.append(v)
                    q.append(v)
        out.append(comp)
    return out


def check_forest(nodes, edges):
    uf = {n: n for n in nodes}

    def find(x):
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    for e in edges:
        a, b = find(e["src"]), find(e["dst"])
        if a == b:
            raise MptError(f"tree view has a cycle through {e['src']} -- {e['dst']}; run `mpt span` first")
        uf[a] = b


def center(adj, comp):
    """Centre node of a tree component (the first of two if bicentral)."""
    deg = {n: len(adj[n]) for n in comp}
    leaves = [n for n in comp if deg[n] <= 1]
    remaining = len(comp)
    while remaining > 2:
        remaining -= len(leaves)
        nxt = []
        for leaf in leaves:
            for m in adj[leaf]:
                deg[m] -= 1
                if deg[m] == 1:
                    nxt.append(m)
            deg[leaf] = 0
        leaves = nxt
    return min(leaves, key=comp.index)


def bfs_dist(adj, start):
    dist, q = {start: 0}, deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def diameter(adj, start):
    d1 = bfs_dist(adj, start)
    far = max(d1, key=d1.get)
    return max(bfs_dist(adj, far).values())


def rooted(adj, root):
    parent, children = {root: None}, {root: []}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in parent:
                parent[v] = u
                children[v] = []
                children[u].append(v)
                q.append(v)
    return parent, children


def view(g, root=None):
    """Tree view of the graph, rooted at ``root`` (default: centre of the largest component)."""
    edges = g.tree_edges()
    check_forest(g.nodes, edges)
    adj = adjacency(g.nodes, edges)
    if root is None:
        if not g.nodes:
            raise MptError("graph is empty")
        root = center(adj, max(components(adj), key=len))
    else:
        g.require(root)
    parent, children = rooted(adj, root)
    return View(adj, parent, children, root)


def in_view(v, nid):
    if nid not in v.parent:
        raise MptError(f"{nid} is not in the same tree component as root {v.root}")


# -- walks -----------------------------------------------------------------
def preorder_depth(children, root):
    stack = [(root, 0)]
    while stack:
        n, d = stack.pop()
        yield n, d
        stack.extend((c, d + 1) for c in reversed(children[n]))


def preorder(children, root):
    return [n for n, _ in preorder_depth(children, root)]


def postorder(children, root):
    out, stack = [], [(root, iter(children[root]))]
    while stack:
        n, it = stack[-1]
        c = next(it, None)
        if c is None:
            stack.pop()
            out.append(n)
        else:
            stack.append((c, iter(children[c])))
    return out


def levelorder(children, root):
    out, q = [], deque([root])
    while q:
        n = q.popleft()
        out.append(n)
        q.extend(children[n])
    return out


def euler(children, root):
    out, stack = [root], [(root, iter(children[root]))]
    while stack:
        n, it = stack[-1]
        c = next(it, None)
        if c is None:
            stack.pop()
            if stack:
                out.append(stack[-1][0])
        else:
            out.append(c)
            stack.append((c, iter(children[c])))
    return out


WALKS = {"pre": preorder, "post": postorder, "level": levelorder, "euler": euler}


# -- axes ------------------------------------------------------------------
def ancestors(v, n):
    out, p = [], v.parent[n]
    while p is not None:
        out.append(p)
        p = v.parent[p]
    return out


def descendants(v, n):
    return preorder(v.children, n)[1:]


def siblings(v, n):
    p = v.parent[n]
    return [] if p is None else [c for c in v.children[p] if c != n]


def path(adj, a, b):
    """Unique tree path a..b, or None if they are in different components."""
    prev, q = {a: None}, deque([a])
    while q:
        u = q.popleft()
        if u == b:
            break
        for w in adj[u]:
            if w not in prev:
                prev[w] = u
                q.append(w)
    if b not in prev:
        return None
    out = []
    while b is not None:
        out.append(b)
        b = prev[b]
    return out[::-1]


def causal_walk(g, start, upstream):
    """BFS over directed edges (whole graph, not just the tree). Yields (depth, node).

    upstream=True follows effect -> cause (``why``); False follows cause -> effect (``so-what``).
    """
    g.require(start)
    nxt = {n: [] for n in g.nodes}
    for e in g.edges:
        a, b = (e["dst"], e["src"]) if upstream else (e["src"], e["dst"])
        nxt[a].append(b)
    seen, q = {start}, deque([(0, start)])
    while q:
        d, u = q.popleft()
        if d:
            yield d, u
        for w in nxt[u]:
            if w not in seen:
                seen.add(w)
                q.append((d + 1, w))
