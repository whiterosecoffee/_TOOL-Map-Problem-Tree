# Map Problem Tree (`mpt`)

Traverse and edit free (unrooted) spanning trees of problem graphs. Pure standard library, Python 3.9+. Design background: [TOOLS.md](TOOLS.md).

Edges are directed **cause -> effect**, but the tree view ignores direction, so any node can be the root. `span` marks a spanning tree on the graph; unmarked edges stay as dashed non-tree edges.

```bash
python -m mpt init g.json
python -m mpt import g.json outline.md          # child = cause of parent
python -m mpt add g.json c3 "Late planting" --causes drought
python -m mpt link g.json c3 poor-soil          # extra edge, may create a cycle
python -m mpt span g.json --algo mst            # bfs | dfs | mst  (--max keeps heaviest)
python -m mpt info g.json                       # counts, centre, diameter
python -m mpt walk g.json --order euler         # pre | post | level | euler
python -m mpt axis g.json c3 path-to --to low-yield
python -m mpt reroot g.json c3                  # same tree, new root
python -m mpt why g.json low-yield              # all upstream causes (whole graph)
python -m mpt so-what g.json c3                 # all downstream effects
python -m mpt move g.json c3 --to poor-soil
python -m mpt undo g.json
python -m mpt render g.json --to mermaid        # text | mermaid | dot
python -m mpt export g.json --to opml -o out.opml
```

Without `--root`, views are rooted at the tree's centre. Read commands take `--json` for JSON lines. Run tests with `python -m unittest discover -s tests -t .`.

## v0 limits
- No SVG output yet (Mermaid/DOT only).
- Undo keeps up to 100 full snapshots inside the graph file.
- No Steiner trees, LCA/distance commands, or query/diff (later families in TOOLS.md).
