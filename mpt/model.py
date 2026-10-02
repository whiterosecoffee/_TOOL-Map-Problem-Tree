"""Graph store: a problem graph whose spanning tree is marked on its edges.

Edges are directed cause -> effect (``src`` causes ``dst``) but traversal of
the tree view ignores direction, so any node can serve as the root.
"""
import copy
import json
import os

MAX_UNDO = 100


class MptError(Exception):
    """User-facing error; the CLI prints it without a traceback."""


class Graph:
    def __init__(self, nodes=None, edges=None, undo=None):
        self.nodes = nodes if nodes is not None else {}
        self.edges = edges if edges is not None else []
        self.undo = undo if undo is not None else []

    # -- persistence -------------------------------------------------------
    @classmethod
    def load(cls, path):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except FileNotFoundError:
            raise MptError(f"no such file: {path} (run `mpt init {path}`)")
        except json.JSONDecodeError as e:
            raise MptError(f"{path} is not valid JSON: {e}")
        return cls(d.get("nodes"), d.get("edges"), d.get("undo"))

    def save(self, path):
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"nodes": self.nodes, "edges": self.edges, "undo": self.undo},
                      f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)

    # -- undo --------------------------------------------------------------
    def checkpoint(self):
        self.undo.append({"nodes": copy.deepcopy(self.nodes),
                          "edges": copy.deepcopy(self.edges)})
        del self.undo[:-MAX_UNDO]

    def restore(self):
        if not self.undo:
            raise MptError("nothing to undo")
        s = self.undo.pop()
        self.nodes, self.edges = s["nodes"], s["edges"]

    # -- queries -----------------------------------------------------------
    def require(self, nid):
        if nid not in self.nodes:
            raise MptError(f"unknown node: {nid}")

    def label(self, nid):
        return self.nodes[nid]["label"]

    def has_marked(self):
        return any(e["tree"] for e in self.edges)

    def find_edge(self, a, b):
        for e in self.edges:
            if {e["src"], e["dst"]} == {a, b}:
                return e
        return None

    def tree_edges(self):
        """Marked spanning-tree edges, or every edge if none are marked yet."""
        if self.has_marked():
            return [e for e in self.edges if e["tree"]]
        return list(self.edges)

    # -- mutations ---------------------------------------------------------
    def add_node(self, nid, label, ntype="node"):
        if nid in self.nodes:
            raise MptError(f"node already exists: {nid}")
        self.nodes[nid] = {"label": label, "type": ntype}

    def add_edge(self, src, dst, weight=1.0, tree=False):
        self.require(src)
        self.require(dst)
        if src == dst:
            raise MptError("self-loops are not allowed")
        if self.find_edge(src, dst):
            raise MptError(f"{src} and {dst} are already linked")
        self.edges.append({"src": src, "dst": dst, "weight": weight, "tree": tree})

    def remove_node(self, nid):
        self.require(nid)
        del self.nodes[nid]
        self.edges = [e for e in self.edges if nid not in (e["src"], e["dst"])]


def mutate(path, fn, create=False):
    """Load, checkpoint for undo, apply ``fn(graph)``, save. Nothing is written if fn raises."""
    g = Graph() if create and not os.path.exists(path) else Graph.load(path)
    g.checkpoint()
    result = fn(g)
    g.save(path)
    return result
