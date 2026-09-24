# Handoff: SAP Clean Core Analyzer — Architecture & Clean Core screen

## Overview
SAP Clean Core Analyzer is a T-Systems enterprise platform that analyzes SAP custom applications (ABAP), discovers business rules and assesses adherence to SAP Clean Core principles. This handoff covers the first screen: **Architecture & Clean Core** for the application `ZSD_ORDER_MANAGEMENT`. It includes a navigable dependency graph, a selected-object detail panel and a permanent AI Copilot that is aware of the current screen and selection.

## About the Design Files
The files in this bundle are **design references created in HTML**: prototypes that show the intended look and behavior. They are not production code to copy directly. Recreate the design in the target codebase's environment (React, Vue, etc.) using its established patterns and libraries. If no environment exists yet, choose an appropriate framework (e.g. React + TypeScript, with a graph library such as React Flow for the dependency graph).

`SAP Clean Core Analyzer.dc.html` is a self-rendering design component: the template markup sits inside `<x-dc>` and the logic class (all data plus interaction handlers) is in the `<script data-dc-script>` block. Open it in a browser next to `support.js` to see it running.

## Fidelity
**High-fidelity.** Colors, typography, spacing and interactions are final. Recreate them pixel-accurately.

## Global layout (1920 × 1080 desktop)
Three permanent regions in a horizontal flex row:

| Region | Width | Background | Notes |
|---|---|---|---|
| Sidebar | 240px fixed | `#111318` | border-right 1px `#1F232A` |
| Workspace | flex 1 (1104px at 1920) | `#0D0F12` | main content |
| AI Copilot | 576px fixed (30%) | `#111318` | border-left 1px `#2B3038`; can collapse to a 52px rail |

Base font: Inter 13px / 1.45. Code and object names: JetBrains Mono. Icons: Phosphor (regular + fill).

## Sidebar
- **Brand block** (76px tall, 18px horizontal padding, bottom border `#1F232A`): T-Systems wordmark image, 18px tall (`assets/tsystems-wordmark.png`), then "SAP Clean Core Analyzer" in 13px / 500, `#F4F5F7`, 9px gap.
- **Section label**: "WORKSPACE", 10.5px, uppercase, letter-spacing 0.08em, `#737A85`.
- **Nav items** (36px tall, 10px padding, 6px radius, 10px gap between icon and label, 17px icon, `#A7ADB7`; hover background `#1A1D23`, text `#F4F5F7`): Dashboard (squares-four), Application Discovery (compass), **Architecture & Clean Core** (graph, active), Business Rules (scroll), Engineering (code), Analysis Runs (pulse).
- **Active item**: background `#1D2128`, text `#F4F5F7` at weight 500, icon `#E30074`, and a 3px vertical `#E30074` indicator on the left edge (inset 8px top and bottom, 0 2px 2px 0 radius).
- **"APPLICATION" section**: a card (background `#15181D`, border `#2B3038`, 6px radius) with a cube icon in `#7EA6E8`, `ZSD_ORDER_MANAGEMENT` in mono 11.5px and "47 objects · SD" in 11px `#737A85`.
- **Footer** (top border): a connection card (background `#171A20`, border `#23272E`) with a database icon, "SAP ECC · PRD" in 12.5px / 500, and "Connected · RFC" next to a 6px green dot (`#3FBF7F`). Below it, the user row: a 28px avatar circle showing "MA", "Marta Albers" / "SAP Architect", and a gear icon.

## Workspace
### Top bar (52px, bottom border `#1F232A`, 24px horizontal padding)
- Left: breadcrumb "Applications › ZSD_ORDER_MANAGEMENT (mono) › Architecture & Clean Core". Size 12.5px, colors `#737A85` → `#A7ADB7` → `#F4F5F7`. `nowrap`.
- Right (`nowrap`, 10px gap): "Run #2026-0042" (mono), a check-circle icon with "Completed" in green `#4CC38A`, "23 Sep 2026" in `#737A85`, two icon-only 30×30 secondary buttons (Compare Runs = git-diff, View Changes = clock-counter-clockwise), and the primary button **Re-run Analysis**.
- Primary button: height 30, background and border `#E30074`, white text 12px / 500, 6px radius. Hover `#F21C88`.
- Secondary button: transparent background, 1px `#2B3038` border, text `#D4D7DD`. Hover background `#1D2128`.

### Content area (padding 18px 24px 20px, vertical flex, 14px gap)
1. **Header row**
   - Left: `ZSD_ORDER_MANAGEMENT` in JetBrains Mono 24px / 500. Next to it, a tag "SD · Sales & Distribution" (1px `#2B3038` border, 4px radius, 11px). Subtitle: "Sales Order Management — dependency graph and Clean Core assessment", 13.5px `#A7ADB7`.
   - Right: three KPI cards (background `#171A20`, border `#23272E`, 8px radius, padding 9px 14px, uppercase 11px labels in `#737A85`):
     - Clean Core Score: "42%" at 22px, with a 4px bar (track `#2B3038`, fill orange `#E8944A` at 42%).
     - Risk: warning-octagon icon in `#F0605A` and "High" at 18px.
     - Findings: "12" plus "· 4 high".
2. **Toolbar (single row, `nowrap`)**
   - Filter chips: All, Classes, Function Modules, Tables, Reports, Enhancements, BAdIs, RFCs, APIs. Each is 28px tall, padding 0 8px, 11.5px, 6px radius.
     - Idle: 1px `#2B3038` border, text `#A7ADB7`.
     - Active: border `#E30074`, background `#1E1118`, text `#FF8CC4`.
   - Legend on the right (11px, 10×10 swatches): Custom, SAP Standard, Released API, Legacy, Clean Core Risk. Swatch colors are in Design Tokens below.
3. **Graph canvas** (flex 1, about 560px tall)
   - Background `#111318` with a dot grid: `radial-gradient(#1E2229 1px, transparent 1px)` at 20px spacing. Border `#23272E`, 8px radius.
   - SAP Standard band: from x=812 to the right edge, background `#14161B`, with a dashed left border `#2B3038`.
   - Zone labels at the top: "CUSTOM CODE · Z NAMESPACE" and "SAP STANDARD · ECC 6.0 EHP8".
   - **15 nodes**, absolutely positioned. Column x positions are 12, 212, 412, 612 and 826. Nodes are 176px wide (222px in the SAP column) and 52px tall, with 6px radius and padding 7px 10px.
     - Row 1: type badge (mono 9.5px, 1px border in the kind color), type label (10.5px `#A7ADB7`), and an optional findings count on the right (warning icon plus number, `#F0605A`).
     - Row 2: object name in mono 11px, `#F4F5F7`, with ellipsis.
   - **Selected node**: border `#E30074` plus `box-shadow: 0 0 0 1px #E30074, 0 0 0 5px rgba(227,0,116,.10), 0 8px 20px rgba(0,0,0,.45)`. This gives an effective 2px magenta border with a very faint halo and no neon.
   - **Copilot-highlighted node**: border `#B0105E` and `0 0 0 3px rgba(227,0,116,.10)`. All nodes that are not highlighted drop to 0.32 opacity. Nodes that don't match the active filter also drop to 0.32 opacity.
   - **Edges** (SVG, cubic bezier from the source's right-middle to the target's left-middle; same-column edges run vertically from bottom-center to top-center; arrowhead markers):
     - Default: `#3A404B`, 1.2px.
     - Risk: `#F0605A`, dashed 4 3, opacity 0.75.
     - Legacy: `#E8944A`, dashed 4 3, opacity 0.6.
     - Edges touching the selected node: `#E30074`, 1.6px (risk edges stay red).
     - While a Copilot highlight is active, edges outside it drop to 0.25 opacity.
   - Highlight pill at bottom-left: sparkle icon and "Copilot highlighted N components", plus a Clear button.
   - Zoom control at bottom-right: stacked 30×28 buttons for +, − and fit.
4. **Selected object panel** (262px tall, two cards with a 12px gap)
   - **Left card** (300px wide):
     - Label "SELECTED OBJECT" and the object name in mono 14.5px.
     - A 2×2 grid separated by 1px `#23272E` lines: Type, Risk (dot plus label), Dependencies and Business Rules (values at 18px / 500).
     - Buttons: "Open in Engineering" (secondary) and "Ask Copilot" (1px `#6A1F45` border, text `#FF5FAE`, sparkle icon).
   - **Right card**: a tab bar (42px) with Clean Core Findings, Business Rules and Dependencies. Each tab has a count pill (`#242831`). The active tab gets a 2px `#E30074` underline and white text. The "for <object>" label is right-aligned.
     - Findings rows (grid 78 / 64 / 1fr / 120 / 170): severity dot and label, ID, title, category, and code evidence in magenta mono (e.g. "CHECK_CREDIT · L128").
     - Rules rows (grid 64 / 1fr / 150 / 140 / 110): ID, title, process, confidence bar with %, and "N sources".
     - Dependency rows: direction ("Calls" or "Called by", with an arrow icon), name, type, and kind label in the kind color. Below them: "+N dependencies outside the current view".
     - Selected row: background `#1D2128` and 1px border `#8A1452`. Row hover: `#1D2128`.

## AI Copilot panel
- **Header** (52px): a 26px icon tile (border `#6A1F45`, background `#1E1118`, sparkle icon in `#E30074`), "AI Copilot" at 14px / 500, the small T logo (14px, `assets/tsystems-t.png`) with "by T-Systems", and icon buttons on the right for history, new chat and collapse.
- **Context card**: label "CONTEXT" with three chips: app `ZSD_ORDER_MANAGEMENT`, view "Architecture & Clean Core", and the current selection. The selection chip is magenta-tinted (background `#1E1118`, border `#6A1F45`, text `#FF8CC4`) and updates live.
- **Conversation** (scrolls, 16px gap between messages):
  - User bubble: aligned right, max width 82%, background `#1D2128`, border `#2B3038`, radius 8 8 2 8.
  - AI message:
    - Label row: sparkle icon, "Copilot", "· grounded in Run #2026-0042".
    - Intro paragraph at 13.5px / 1.6 in `#E3E5E9`.
    - Numbered items with 20px mono index tiles.
    - Optional outro in `#A7ADB7`.
    - Reference chips: background `#1A1217`, border `#3A1A2C`, text `#FF5FAE`. Hover border is `#E30074`. Icons: cube for objects, warning-diamond for findings, scroll for rules.
    - Footer: a "View Evidence · 3 Sources" toggle that expands a source list (object, method and line range, "Run 2026-0042"), an optional magenta outlined action button, and copy / thumbs icons.
  - "Context updated · <object> selected" divider line, with fading gradient rules, added when the selection changes.
  - "Highlighted N components in the architecture graph" note, shown after the Copilot drives the UI.
  - Pending state: "Tracing dependencies and evidence for <object>…"
- **Footer**:
  - Suggestion chips (28px, pill-shaped, border `#2B3038`, hover border `#E30074`): Explain architecture, Summarize risks, Find SAP standard alternatives, Show affected business rules, Create modernization summary.
  - Input box: background `#171A20`, border `#2B3038` (focus-within border `#E30074`), 2-row textarea with placeholder "Ask about this application…", @ icon, and a 34px `#E30074` send button with an arrow-up icon.
  - Disclaimer at 10.5px in `#737A85`.
- **Collapsed rail** (52px): a sparkle button and the vertical text "AI Copilot".

## Interactions & Behavior
- **Click a node**: it becomes selected. The detail panel updates, the Copilot context chip updates, a "Context updated" divider is added to the chat (replacing a previous consecutive one), and the first finding of that object becomes the active finding.
- **Filter chip**: dims every node whose group doesn't match.
- **Tabs**: switch between Findings, Rules and Dependencies. Clicking a dependency row selects that object.
- **Copilot reference chips**: an object chip selects that node; a finding chip selects its object, opens the Findings tab and activates the row; a rule chip opens the Rules tab and activates the row.
- **Suggestion chips and free-text send** (Enter sends, Shift+Enter adds a newline): the user message is added, a pending state shows for about 750ms, then the AI reply appears. Most replies **automatically highlight related components in the graph**, so the Copilot controls the UI. The initial answer offers a "Highlight in architecture" action button instead. The rules answer includes an "Open in rules panel" action.
- **"Ask Copilot"** in the detail panel sends a question scoped to the selected object.
- **Collapse and expand the Copilot**: the workspace reflows into the freed width.
- Transitions: nodes animate opacity, box-shadow and border-color over 0.2s.
- The chat auto-scrolls to the bottom when a new message arrives.
- All AI output carries evidence (sources with object, method and line range, plus the analysis run). Keep traceability as a recurring visual pattern.

## State
`sel` (selected object id), `filter`, `tab` (findings / rules / deps), `hl` (array of highlighted ids, or null), `activeFinding`, `activeRule`, `open` (Copilot panel), `messages[]` (user / ai / ctx), `pending`, `evOpen` (index of the message whose evidence is expanded), `input`.
In production the AI replies come from the backend (AWS Bedrock or Azure AI Foundry behind an abstraction; don't expose the provider in the UI). A reply should return structured data: `intro`, `items[]`, `outro`, `refs[]` (typed: object / finding / rule), `sources[]` and optional `highlight[]` / `action`.

## Data model (sample data lives in the logic class)
- `NODES`: name, type label, badge abbreviation, kind (custom | sap | api | legacy | risk), column, y, dependency count, risk, filter group.
- `EDGES`: [from, to, kind?], where kind is risk or legacy.
- `FINDINGS`: id, severity, title, object, category, code evidence.
- `RULES`: id, title, objects[], confidence, process, source count.

## Design Tokens
**Surfaces:** background `#0D0F12` · sidebar / Copilot `#111318` · cards `#171A20` · elevated / selected rows `#1D2128` · hover `#242831` · border `#2B3038` · soft border `#23272E` / `#1F232A`
**Text:** primary `#F4F5F7` · secondary `#A7ADB7` · tertiary `#737A85` · button text `#D4D7DD`
**Brand / interaction:** `#E30074` · hover `#F21C88` · magenta text on dark `#FF5FAE` / `#FF8CC4` · magenta tint fill `#1E1118` / `#1A1217` / `#24121B` · magenta tint borders `#6A1F45` / `#3A1A2C` / `#8A1452`
**Semantic:** green `#4CC38A` (connected dot `#3FBF7F`) · yellow `#E5B53C` · orange `#E8944A` · red `#F0605A` · blue (info / custom) `#7EA6E8` · low-severity blue-grey `#8FA3BF`
**Graph node kinds (background / border / badge):**
- Custom: `#141C2A` / `#2A4470` / `#7EA6E8`
- SAP Standard: `#191C22` / `#3A404A` / `#9098A3`
- Released API: `#12211A` / `#275E43` / `#4CC38A`
- Legacy: `#231A12` / `#6B4526` / `#E8944A`
- Clean Core Risk: `#261517` / `#7C3036` / `#F0605A`

**Type:** Inter (400 / 500; headings never above 500), JetBrains Mono (400 / 500). Sizes: 24 (page title), 22 / 18 (KPIs), 14–14.5, 13–13.5 (body), 12–12.5, 11–11.5, 10.5 (labels, uppercase with 0.08em letter-spacing).
**Radii:** 4px (chips, tags), 6px (buttons, nodes, rows), 8px (cards, canvas), 14px (suggestion pills).
**Shadows:** minimal. Elevation comes from layered surfaces and 1px borders. The only shadow is on the selected node.
**Rules:** never use pure black. Magenta is reserved for identity, AI, selection and primary actions, and is never used to flood large areas.

## Assets
- `assets/tsystems-wordmark.png`: T-Systems wordmark in magenta (sidebar).
- `assets/tsystems-t.png`: T-Systems "T" app icon (Copilot header).
- Icons: Phosphor Icons web font v2.1.1 (regular + fill).
- Fonts: Inter and JetBrains Mono (Google Fonts).

## Files
- `SAP Clean Core Analyzer.dc.html`: the full screen (template, logic and sample data).
- `support.js`: the runtime needed to open the HTML reference in a browser.
- `assets/`: logos.

## Next screens (defined in the product brief, not yet designed)
Applications list, New SAP Analysis wizard, Analysis Run pipeline, Executive Overview, Clean Core Findings (full table and detail drawer), Business Rules, Engineering (object tree plus ABAP viewer with line annotations), Application Discovery, Modernization Opportunities. The sidebar, top bar and Copilot shell shown here are shared by all of them.
