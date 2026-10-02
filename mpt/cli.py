"""Command-line interface: ``mpt <command> FILE ...``."""
import argparse
import json
import os
import sys

from . import formats, tree
from .model import Graph, MptError, mutate
from .span import ALGOS, span


def out_nodes(g, rows, as_json):
    """rows: iterable of (node_id, extra_dict)."""
    for n, extra in rows:
        if as_json:
            print(json.dumps({"id": n, "label": g.label(n), "type": g.nodes[n]["type"], **extra}))
        else:
            prefix = "".join(f"{v}\t" for v in extra.values())
            print(f"{prefix}{n}\t{g.label(n)}")


def cmd_init(a):
    if os.path.exists(a.file) and not a.force:
        raise MptError(f"{a.file} exists (use --force to overwrite)")
    Graph().save(a.file)
    print(f"created {a.file}")


def cmd_add(a):
    def fn(g):
        other = a.causes or a.caused_by
        if other:
            g.require(other)
        g.add_node(a.id, a.label, a.type)
        mark = g.has_marked()
        if a.causes:
            g.add_edge(a.id, a.causes, a.weight, tree=mark)
        elif a.caused_by:
            g.add_edge(a.caused_by, a.id, a.weight, tree=mark)

    mutate(a.file, fn)
    print(f"added {a.id}")


def cmd_link(a):
    mutate(a.file, lambda g: g.add_edge(a.cause, a.effect, a.weight, tree=a.tree))
    print(f"linked {a.cause} -> {a.effect}")


def cmd_move(a):
    def fn(g):
        g.require(a.node)
        g.require(a.to)
        v = tree.view(g, a.root)
        tree.in_view(v, a.node)
        tree.in_view(v, a.to)
        p = v.parent[a.node]
        if p is None:
            raise MptError(f"{a.node} is the root; reroot the view instead of moving it")
        if a.to in tree.preorder(v.children, a.node):
            raise MptError(f"cannot move {a.node} under its own descendant {a.to}")
        old = g.find_edge(a.node, p)
        g.edges.remove(old)
        existing = g.find_edge(a.node, a.to)
        if existing:  # already linked off-tree: promote that edge instead of duplicating it
            existing["tree"] = True
        else:
            src, dst = (a.node, a.to) if old["src"] == a.node else (a.to, a.node)
            g.add_edge(src, dst, old["weight"], tree=old["tree"])

    mutate(a.file, fn)
    print(f"moved {a.node} under {a.to}")


def cmd_delete(a):
    mutate(a.file, lambda g: g.remove_node(a.node))
    print(f"deleted {a.node}")


def cmd_undo(a):
    g = Graph.load(a.file)
    g.restore()
    g.save(a.file)
    print(f"undone ({len(g.undo)} more step(s) available)")


def cmd_span(a):
    t, nt, nc = mutate(a.file, lambda g: span(g, a.algo, a.root, a.max))
    print(f"{a.algo}: {t} tree edge(s), {nt} non-tree edge(s), {nc} component(s)")


def cmd_info(a):
    g = Graph.load(a.file)
    te = g.tree_edges()
    print(f"nodes: {len(g.nodes)}\nedges: {len(g.edges)} ({len(te)} in tree view)")
    if g.nodes:
        v = tree.view(g)
        comps = tree.components(v.adj)
        print(f"components: {len(comps)}\ncenter: {v.root}\ndiameter: {tree.diameter(v.adj, v.root)}")


def _view(a):
    g = Graph.load(a.file)
    v = tree.view(g, a.root)
    skipped = len(g.nodes) - len(v.parent)
    if skipped:
        print(f"note: {skipped} node(s) not reachable from {v.root}", file=sys.stderr)
    return g, v


def cmd_walk(a):
    g, v = _view(a)
    out_nodes(g, ((n, {}) for n in tree.WALKS[a.order](v.children, v.root)), a.json)


def cmd_axis(a):
    g, v = _view(a)
    g.require(a.node)
    tree.in_view(v, a.node)
    n = a.node
    if a.axis == "ancestors":
        nodes = tree.ancestors(v, n)
    elif a.axis == "descendants":
        nodes = tree.descendants(v, n)
    elif a.axis == "siblings":
        nodes = tree.siblings(v, n)
    elif a.axis == "children":
        nodes = v.children[n]
    elif a.axis == "parent":
        nodes = [v.parent[n]] if v.parent[n] else []
    else:  # path-to
        if not a.to:
            raise MptError("path-to needs --to NODE")
        g.require(a.to)
        nodes = tree.path(v.adj, n, a.to)
        if nodes is None:
            raise MptError(f"no tree path between {n} and {a.to}")
    out_nodes(g, ((x, {}) for x in nodes), a.json)


def _causal(a, upstream):
    g = Graph.load(a.file)
    out_nodes(g, ((n, {"depth": d}) for d, n in tree.causal_walk(g, a.node, upstream)), a.json)


def cmd_why(a):
    _causal(a, True)


def cmd_so_what(a):
    _causal(a, False)


def cmd_reroot(a):
    g = Graph.load(a.file)
    sys.stdout.write(formats.render_text(g, tree.view(g, a.node)))


def _emit(text, path):
    if path:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"wrote {path}")
    else:
        sys.stdout.write(text)


def cmd_render(a):
    g = Graph.load(a.file)
    v = tree.view(g, a.root) if a.to == "text" else None
    _emit(formats.RENDERERS[a.to](g, v), a.output)


def cmd_import(a):
    with open(a.source, encoding="utf-8") as f:
        text = f.read()
    fmt = a.format or ("opml" if a.source.lower().endswith((".opml", ".xml")) else "md")
    items = formats.parse_opml(text) if fmt == "opml" else formats.parse_markdown(text)
    if not items:
        raise MptError(f"no outline items found in {a.source}")
    n = mutate(a.file, lambda g: formats.import_items(g, items), create=True)
    print(f"imported {n} node(s) from {a.source}")


def cmd_export(a):
    g = Graph.load(a.file)
    v = tree.view(g, a.root)
    fn = formats.export_opml if a.to == "opml" else formats.export_markdown
    _emit(fn(g, v), a.output)


def build_parser():
    p = argparse.ArgumentParser(prog="mpt", description="Map Problem Tree: traverse and edit free spanning trees.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, root=False, js=False):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("file", help="graph JSON file")
        sp.set_defaults(fn=fn)
        if root:
            sp.add_argument("--root", help="root of the view (default: tree centre)")
        if js:
            sp.add_argument("--json", action="store_true", help="emit JSON lines")
        return sp

    sp = add("init", cmd_init, "create an empty graph file")
    sp.add_argument("--force", action="store_true")

    sp = add("add", cmd_add, "add a node, optionally linked to an existing one")
    sp.add_argument("id")
    sp.add_argument("label")
    sp.add_argument("--type", default="node", help="problem, cause, effect, evidence, objective, action, ...")
    sp.add_argument("--weight", type=float, default=1.0)
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--causes", metavar="NODE", help="new node is a cause of NODE")
    g.add_argument("--caused-by", metavar="NODE", help="new node is an effect of NODE")

    sp = add("link", cmd_link, "link two existing nodes (cause -> effect)")
    sp.add_argument("cause")
    sp.add_argument("effect")
    sp.add_argument("--weight", type=float, default=1.0)
    sp.add_argument("--tree", action="store_true", help="mark the edge as a spanning-tree edge")

    sp = add("move", cmd_move, "move a node (and its subtree) under another node", root=True)
    sp.add_argument("node")
    sp.add_argument("--to", required=True, metavar="NODE", help="new neighbour toward the root")

    sp = add("delete", cmd_delete, "delete a node and its edges")
    sp.add_argument("node")

    add("undo", cmd_undo, "undo the last change")

    sp = add("span", cmd_span, "mark a spanning tree/forest on the graph", )
    sp.add_argument("--algo", choices=ALGOS, default="bfs")
    sp.add_argument("--root", help="start node for bfs/dfs")
    sp.add_argument("--max", action="store_true", help="mst: keep the heaviest edges instead of the lightest")

    add("info", cmd_info, "counts, centre and diameter")

    sp = add("walk", cmd_walk, "walk the tree", root=True, js=True)
    sp.add_argument("--order", choices=sorted(tree.WALKS), default="pre")

    sp = add("axis", cmd_axis, "XPath-style axis query from a node", root=True, js=True)
    sp.add_argument("node")
    sp.add_argument("axis", choices=["ancestors", "descendants", "siblings", "children", "parent", "path-to"])
    sp.add_argument("--to", help="target node for path-to")

    sp = add("why", cmd_why, "walk to causes (upstream, whole graph)", js=True)
    sp.add_argument("node")
    sp = add("so-what", cmd_so_what, "walk to effects (downstream, whole graph)", js=True)
    sp.add_argument("node")

    sp = add("reroot", cmd_reroot, "print the tree outline re-rooted at NODE")
    sp.add_argument("node")

    sp = add("render", cmd_render, "render to text, mermaid or dot", root=True)
    sp.add_argument("--to", choices=sorted(formats.RENDERERS), default="text")
    sp.add_argument("-o", "--output")

    sp = add("import", cmd_import, "import a Markdown or OPML outline (child = cause of parent)")
    sp.add_argument("source")
    sp.add_argument("--format", choices=["md", "opml"])

    sp = add("export", cmd_export, "export the tree as a Markdown or OPML outline", root=True)
    sp.add_argument("--to", choices=["md", "opml"], default="md")
    sp.add_argument("-o", "--output")
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except MptError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
