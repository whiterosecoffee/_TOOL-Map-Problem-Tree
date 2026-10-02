# Tool Families for Traversing and Interacting with Free / Spanning Trees

Scope: a "Map Problem Tree" is a *free tree* (no privileged root; any node can become the root of a view) that *spans* a problem graph (causes, effects, dependencies, evidence). Tools therefore split into two jobs: **derive** a tree from a graph, and **traverse/edit** a tree. Each family lists its prior art, the operations it contributes, and a candidate tool for this repo.

## 1. Spanning-tree construction (graph -> tree)
Prior art: Kruskal / Prim / Borůvka MST; BFS/DFS spanning trees; Wilson's uniform random spanning tree; Steiner tree approximations; Chu-Liu/Edmonds (directed, arborescence); Spanning Tree Protocol (IEEE 802.1D); Kirchhoff matrix-tree theorem.
Candidate tools:
- `span --algo {bfs,dfs,mst,steiner,random}`: derive a tree from a causal/dependency graph, weights = evidence strength or edge cost.
- `span --terminals A,B,C`: Steiner tree connecting only the nodes of interest.
- `count-spans`: number of spanning trees via matrix-tree theorem (measures how ambiguous the problem structure is).
- `swap-edge`: fundamental-cycle edge exchange to move between spanning trees.

## 2. Traversal and iteration
Prior art: pre/in/post/level-order walks; Euler tour; zippers (Huet); XPath axes (parent, child, sibling, ancestor, descendant); DOM TreeWalker; `find`/`tree` in Unix; Tree-sitter cursors; jq paths.
Candidate tools:
- `walk --order {pre,post,level,euler} --from NODE`: free-tree walk from any node, re-rooting implicit.
- `axis NODE ancestors|descendants|siblings|path-to OTHER`: XPath-style queries.
- `cursor`: zipper-style stateful focus with `up/down/left/right`, O(1) local edits.
- `lca A B`, `distance A B`, `center`, `diameter`: unrooted-tree metrics (center picks the natural root).

## 3. Re-rooting and views
Prior art: unrooted phylogenetic trees (Newick/NEXUS, FigTree, iTOL); radial / balloon layouts; focus+context (hyperbolic browser, Lamping & Rao); degree-of-interest trees (Card & Nation).
Candidate tools:
- `reroot NODE`: render same free tree with a new root.
- `view --layout {radial,indented,icicle,hyperbolic}`.
- `focus NODE --radius k --doi`: degree-of-interest pruning, collapse the rest.

## 4. Outline / hierarchy editors
Prior art: Workflowy, Roam/Logseq block trees, OPML, Org-mode, Obsidian outline, mind-mapping (Freeplane, XMind), Treemacs, VS Code explorer.
Candidate tools:
- `add / move / merge / split / collapse / fold`: structural edits with undo log.
- `import/export`: OPML, Org, Markdown headings, Newick, DOT, JSON.
- Keyboard-first TUI (vim-like) over the cursor.

## 5. Argument and problem-structure mapping
Prior art: Problem/Objective trees (GTZ/PCM), Ishikawa fishbone, 5 Whys, Current Reality Tree (Theory of Constraints), IBIS/gIBIS/Compendium, Toulmin, Argdown, Kialo, fault trees (FTA), attack trees, decision trees, Goal-Structuring Notation.
Candidate tools:
- Node types: problem, cause, effect, evidence, objective, action.
- `why NODE`: walk to causes (5 Whys); `so-what NODE`: walk to effects.
- `rank-roots`: leaf causes ordered by reach/evidence.
- Fault-tree style cut sets: minimal sets of leaves whose removal severs a path to the focal problem.
- Argdown/IBIS import.

## 6. Querying and diffing
Prior art: SQL recursive CTEs, closure tables, nested sets, materialized paths; Cypher/Gremlin path queries; tree edit distance (Zhang-Shasha); git tree objects; Merkle trees; XML/JSON diff; CRDT trees (Kleppmann move operation).
Candidate tools:
- `query 'cause* where evidence<2'`: path-pattern queries.
- `diff A B`: tree edit distance between two versions or two analysts' trees.
- `merge`: three-way merge using CRDT move semantics for concurrent edits.
- Content-hash node IDs for stable references.

## 7. Layout and visualization
Prior art: Reingold-Tilford, Walker, Buchheim; treemaps (Shneiderman), sunburst, d3-hierarchy, Graphviz (dot, twopi), Mermaid, Cytoscape, Markmap.
Candidate tools:
- `render --to {svg,mermaid,dot,html}`, with the spanning-tree edges solid and non-tree edges dashed so the discarded graph structure stays visible.

## 8. Interaction surface
Prior art: Language Server Protocol (tree of symbols), Model Context Protocol (tools over a structure), DOM events, Emacs Org agenda, fzf pickers.
Candidate tools:
- CLI with composable subcommands emitting JSON lines.
- MCP server exposing `walk`, `axis`, `edit`, `query` so an agent can navigate the tree.
- fzf-style fuzzy jump to node.

## Suggested minimal core (v0)
1. Data model: node/edge JSON, free tree + retained non-tree edges.
2. `span`, `reroot`, `walk`, `axis`, `why`/`so-what`.
3. `add/move/delete` with undo.
4. `render` to Mermaid/DOT/SVG.
5. Import/export OPML + Markdown.

## Open questions
- "Free spanning trees" is read here as unrooted trees derived as spanning trees of a problem graph. If you meant something else (e.g. free-form, or a specific formalism), the families above reweight.
- Language/stack for the tool (Python CLI vs TypeScript web app) is not yet chosen.
