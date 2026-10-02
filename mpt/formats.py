"""Import/export (Markdown outline, OPML) and rendering (text, Mermaid, DOT).

Outline convention: a child is a *cause* of its parent, so the top item is the
focal problem and import creates edges child -> parent (cause -> effect).
"""
import re
import xml.etree.ElementTree as ET

from .model import MptError
from .tree import preorder_depth


def slug(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "node"


def unique_id(label, taken):
    base, nid, i = slug(label), slug(label), 2
    while nid in taken:
        nid, i = f"{base}-{i}", i + 1
    return nid


# -- import ----------------------------------------------------------------
def parse_markdown(text):
    items, base = [], 0
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            depth = len(m[1]) - 1
            base = depth + 1
            items.append((depth, m[2]))
            continue
        m = re.match(r"^(\s*)[-*+]\s+(.+?)\s*$", line)
        if m:
            items.append((base + len(m[1].expandtabs(2)) // 2, m[2]))
    return items


def parse_opml(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise MptError(f"invalid OPML: {e}")
    body = root.find("body")
    if body is None:
        raise MptError("invalid OPML: no <body>")
    items = []
    stack = [(o, 0) for o in reversed(list(body))]
    while stack:
        el, d = stack.pop()
        items.append((d, el.get("text") or el.get("title") or "(untitled)"))
        stack.extend((c, d + 1) for c in reversed(list(el)))
    return items


def import_items(g, items):
    """Add outline items to ``g`` as a forest; returns the number of nodes added."""
    mark = g.has_marked() or not g.edges
    stack = []
    for depth, label in items:
        nid = unique_id(label, g.nodes)
        g.add_node(nid, label)
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if stack:
            g.add_edge(nid, stack[-1][1], tree=mark)
        stack.append((depth, nid))
    return len(items)


# -- export ----------------------------------------------------------------
def export_markdown(g, v):
    lines = []
    for n, d in preorder_depth(v.children, v.root):
        lines.append(f"# {g.label(n)}" if d == 0 else f"{'  ' * (d - 1)}- {g.label(n)}")
    return "\n".join(lines) + "\n"


def export_opml(g, v):
    opml = ET.Element("opml", version="2.0")
    ET.SubElement(ET.SubElement(opml, "head"), "title").text = g.label(v.root)
    body = ET.SubElement(opml, "body")
    elems = {}
    for n, _ in preorder_depth(v.children, v.root):
        parent = body if v.parent[n] is None else elems[v.parent[n]]
        elems[n] = ET.SubElement(parent, "outline", text=g.label(n))
    ET.indent(opml)
    return ET.tostring(opml, encoding="unicode", xml_declaration=False) + "\n"


# -- render ----------------------------------------------------------------
def render_text(g, v):
    lines = [f"{'  ' * d}{g.label(n)}  [{n}]" for n, d in preorder_depth(v.children, v.root)]
    if g.has_marked():
        extra = [e for e in g.edges if not e["tree"]]
        lines += [f"~ {e['src']} -> {e['dst']}" for e in extra]
    outside = [n for n in g.nodes if n not in v.parent]
    if outside:
        lines.append(f"(not reachable from {v.root}: {', '.join(outside)})")
    return "\n".join(lines) + "\n"


def render_mermaid(g, v=None):
    ids = {n: f"n{i}" for i, n in enumerate(g.nodes)}
    lines = ["graph BT"]  # causes below, the problem they feed on top
    for n, info in g.nodes.items():
        lines.append(f'  {ids[n]}["{info["label"].replace(chr(34), "#quot;")}"]')
    marked = g.has_marked()
    for e in g.edges:
        arrow = "-->" if (e["tree"] or not marked) else "-.->"
        lines.append(f"  {ids[e['src']]} {arrow} {ids[e['dst']]}")
    return "\n".join(lines) + "\n"


def render_dot(g, v=None):
    def q(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = ["digraph problem_tree {", "  rankdir=BT;"]
    for n, info in g.nodes.items():
        lines.append(f"  {q(n)} [label={q(info['label'])}];")
    marked = g.has_marked()
    for e in g.edges:
        style = "" if (e["tree"] or not marked) else " [style=dashed]"
        lines.append(f"  {q(e['src'])} -> {q(e['dst'])}{style};")
    lines.append("}")
    return "\n".join(lines) + "\n"


RENDERERS = {"text": render_text, "mermaid": render_mermaid, "dot": render_dot}
