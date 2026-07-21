# Diagram sources

`ABOUT_PUBLIC.md` references these as PNGs rather than fenced ```mermaid blocks, because
Devpost and most non-GitHub markdown renderers do not run Mermaid and would show the raw
source instead.

The `.mmd` files are the editable originals. After changing one, re-render it:

```bash
npx @mermaid-js/mermaid-cli -i <name>.mmd -o <name>.png -c theme.json -b white -s 3
```

`theme.json` carries the Canopy palette (green borders, tinted fills) so the diagrams match
the product. `-b white` gives an opaque background, since a transparent PNG renders badly on
a dark-themed page. `-s 3` renders at 3x for a crisp result on high-density displays.

If `mermaid-cli` cannot find a browser, point it at an existing one:

```bash
npx @mermaid-js/mermaid-cli ... -p puppeteer.json
```

where `puppeteer.json` is `{"executablePath": "/path/to/chrome-headless-shell"}`.

Keep every diagram horizontal (`flowchart LR`) unless there is a reason not to. A tall
`flowchart TD` renders as a long narrow image that reads poorly in an article layout.
