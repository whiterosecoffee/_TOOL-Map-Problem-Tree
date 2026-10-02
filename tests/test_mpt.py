import contextlib
import io
import os
import tempfile
import unittest

from mpt import formats, tree
from mpt.cli import main
from mpt.model import Graph, MptError
from mpt.span import span


def graph(edges, weights=None):
    g = Graph()
    for a, b in edges:
        for n in (a, b):
            if n not in g.nodes:
                g.add_node(n, n.upper())
    for i, (a, b) in enumerate(edges):
        g.add_edge(a, b, (weights or {}).get((a, b), 1.0))
    return g


# a - b - c - d - e path, plus f hanging off c
PATH = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("c", "f")]


class TreeTests(unittest.TestCase):
    def test_center_and_diameter(self):
        g = graph(PATH)
        v = tree.view(g)
        self.assertEqual(v.root, "c")
        self.assertEqual(tree.diameter(v.adj, "c"), 4)

    def test_bicentral_picks_first(self):
        g = graph([("a", "b")])
        self.assertEqual(tree.view(g).root, "a")

    def test_reroot_changes_parents(self):
        g = graph(PATH)
        v = tree.view(g, "a")
        self.assertEqual(v.parent["c"], "b")
        self.assertEqual(tree.view(g, "e").parent["c"], "d")

    def test_walk_orders(self):
        g = graph(PATH)
        v = tree.view(g, "c")  # children of c in edge order: b, d, f
        self.assertEqual(tree.preorder(v.children, "c"), ["c", "b", "a", "d", "e", "f"])
        self.assertEqual(tree.postorder(v.children, "c"), ["a", "b", "e", "d", "f", "c"])
        self.assertEqual(tree.levelorder(v.children, "c"), ["c", "b", "d", "f", "a", "e"])
        self.assertEqual(tree.euler(v.children, "c"),
                         ["c", "b", "a", "b", "c", "d", "e", "d", "c", "f", "c"])

    def test_axes(self):
        g = graph(PATH)
        v = tree.view(g, "c")
        self.assertEqual(tree.ancestors(v, "a"), ["b", "c"])
        self.assertEqual(tree.descendants(v, "d"), ["e"])
        self.assertEqual(tree.siblings(v, "b"), ["d", "f"])
        self.assertEqual(tree.path(v.adj, "a", "e"), ["a", "b", "c", "d", "e"])

    def test_cycle_rejected_until_span(self):
        g = graph([("a", "b"), ("b", "c"), ("c", "a")])
        with self.assertRaises(MptError):
            tree.view(g)
        span(g, "bfs")
        tree.view(g)

    def test_causal_walk(self):
        g = graph([("x", "y"), ("y", "z"), ("w", "z")])
        self.assertEqual(list(tree.causal_walk(g, "z", True)), [(1, "y"), (1, "w"), (2, "x")])
        self.assertEqual(list(tree.causal_walk(g, "x", False)), [(1, "y"), (2, "z")])


class SpanTests(unittest.TestCase):
    CYCLE = [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")]

    def check_spanning(self, g):
        edges = g.tree_edges()
        self.assertEqual(len(edges), len(g.nodes) - 1)
        tree.check_forest(g.nodes, edges)

    def test_all_algos_span(self):
        for algo in ("bfs", "dfs", "mst"):
            g = graph(self.CYCLE)
            t, nt, nc = span(g, algo)
            self.assertEqual((t, nt, nc), (3, 1, 1), algo)
            self.check_spanning(g)

    def test_mst_weights(self):
        g = graph(self.CYCLE, {("c", "a"): 9.0})
        span(g, "mst")
        self.assertFalse(g.find_edge("c", "a")["tree"])
        g = graph(self.CYCLE, {("c", "a"): 9.0})
        span(g, "mst", maximize=True)
        self.assertTrue(g.find_edge("c", "a")["tree"])

    def test_dfs_is_depth_first(self):
        # square a-b-c-d-a: dfs from a goes a-b-c-d (a path); bfs gives a star-ish tree
        g = graph([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
        span(g, "dfs", "a")
        self.assertFalse(g.find_edge("d", "a")["tree"])
        g = graph([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
        span(g, "bfs", "a")
        self.assertTrue(g.find_edge("d", "a")["tree"])

    def test_forest(self):
        g = graph([("a", "b"), ("c", "d")])
        self.assertEqual(span(g, "bfs"), (2, 0, 2))


class FormatTests(unittest.TestCase):
    MD = "# Low yield\n- Poor soil\n  - No compost\n- Drought\n"

    def test_markdown_roundtrip(self):
        g = Graph()
        formats.import_items(g, formats.parse_markdown(self.MD))
        self.assertEqual(len(g.nodes), 4)
        self.assertEqual(g.find_edge("poor-soil", "low-yield")["src"], "poor-soil")  # cause -> effect
        v = tree.view(g, "low-yield")
        self.assertEqual(formats.export_markdown(g, v), self.MD)

    def test_opml_roundtrip(self):
        g = Graph()
        formats.import_items(g, formats.parse_markdown(self.MD))
        v = tree.view(g, "low-yield")
        opml = formats.export_opml(g, v)
        g2 = Graph()
        formats.import_items(g2, formats.parse_opml(opml))
        self.assertEqual(formats.export_markdown(g2, tree.view(g2, "low-yield")), self.MD)

    def test_unique_ids(self):
        g = Graph()
        formats.import_items(g, [(0, "Same"), (1, "Same")])
        self.assertEqual(list(g.nodes), ["same", "same-2"])

    def test_renderers(self):
        g = graph([("a", "b"), ("b", "c"), ("c", "a")])
        span(g, "bfs")
        self.assertIn("-.->", formats.render_mermaid(g))
        self.assertIn("style=dashed", formats.render_dot(g))
        self.assertIn("~ ", formats.render_text(g, tree.view(g, "a")))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.f = os.path.join(self.dir.name, "g.json")

    def tearDown(self):
        self.dir.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_workflow(self):
        r = self.run_cli
        self.assertEqual(r("init", self.f)[0], 0)
        self.assertEqual(r("init", self.f)[0], 1)  # refuses to overwrite
        r("add", self.f, "prob", "Problem", "--type", "problem")
        r("add", self.f, "c1", "Cause 1", "--causes", "prob")
        r("add", self.f, "c2", "Cause 2", "--causes", "prob")
        r("add", self.f, "r1", "Root cause", "--causes", "c1")
        self.assertEqual(r("link", self.f, "r1", "c2")[0], 0)  # makes a cycle
        self.assertEqual(r("walk", self.f)[0], 1)              # cycle -> error
        self.assertIn("1 non-tree", r("span", self.f, "--algo", "bfs", "--root", "prob")[1])

        code, out, _ = r("walk", self.f, "--root", "prob", "--order", "pre")
        self.assertEqual([l.split("\t")[0] for l in out.splitlines()], ["prob", "c1", "r1", "c2"])
        code, out, _ = r("axis", self.f, "r1", "path-to", "--to", "c2", "--root", "prob", "--json")
        self.assertEqual(out.count("\n"), 4)  # r1, c1, prob, c2
        code, out, _ = r("why", self.f, "prob")
        self.assertIn("r1", out)

        # move r1 from under c1 to under c2, then undo
        self.assertEqual(r("move", self.f, "r1", "--to", "c2", "--root", "prob")[0], 0)
        self.assertEqual(Graph.load(self.f).find_edge("r1", "c2")["tree"], True)
        self.assertEqual(r("undo", self.f)[0], 0)
        self.assertEqual(Graph.load(self.f).find_edge("r1", "c1")["tree"], True)

        self.assertEqual(r("move", self.f, "prob", "--to", "c1", "--root", "prob")[0], 1)  # root
        self.assertEqual(r("move", self.f, "c1", "--to", "r1", "--root", "prob")[0], 1)    # into own subtree
        self.assertIn("Problem", r("reroot", self.f, "r1")[1])

        r("delete", self.f, "c2")
        self.assertNotIn("c2", Graph.load(self.f).nodes)
        self.assertEqual(r("walk", self.f, "--root", "nope")[0], 1)

    def test_import_export_render(self):
        src = os.path.join(self.dir.name, "o.md")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("# P\n- A\n  - A1\n- B\n")
        self.assertEqual(self.run_cli("import", self.f, src)[0], 0)
        code, out, _ = self.run_cli("export", self.f, "--root", "p")
        self.assertEqual(out, "# P\n- A\n  - A1\n- B\n")
        self.assertIn("graph BT", self.run_cli("render", self.f, "--to", "mermaid")[1])
        self.assertIn("diameter: 3", self.run_cli("info", self.f)[1])


if __name__ == "__main__":
    unittest.main()
