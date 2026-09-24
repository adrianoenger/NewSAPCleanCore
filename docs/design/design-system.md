# Design System — SAP Clean Core Analyzer

**Status:** Approved for PoC  
**Version:** 1.0  
**Updated:** 2026-09-23

## 1. Objective

Estabelecer uma linguagem visual única para toda a PoC, evitando que cada visão seja projetada isoladamente. O design deve transmitir uma **enterprise engineering platform** para SAP, com IA integrada naturalmente ao fluxo de trabalho.

A interface não deve parecer um dashboard genérico, uma modernização do SAP GUI, um chatbot em tela cheia ou uma experiência cyberpunk.

## 2. Visual direction

- Dark Mode é o padrão.
- Alta densidade de informação é aceitável, desde que haja hierarquia visual clara.
- Elevação é criada prioritariamente por **camadas de superfície + bordas de 1px**, não por sombras intensas.
- O magenta oficial da T-Systems, **#E30074**, representa identidade, IA, seleção, foco e ações primárias.
- Não usar #E30074 em grandes áreas de fundo. Seu impacto vem do uso controlado.
- Evitar preto puro (`#000000`).
- Evitar efeitos neon, glassmorphism excessivo e gradientes decorativos.

## 3. Core tokens

### 3.1 Surfaces

| Token | Value | Usage |
|---|---:|---|
| `surface.background` | `#0D0F12` | application background |
| `surface.sidebar` | `#111318` | sidebar and Copilot |
| `surface.card` | `#171A20` | cards, panels, input containers |
| `surface.elevated` | `#1D2128` | selected rows, elevated controls |
| `surface.hover` | `#242831` | hover state |
| `border.default` | `#2B3038` | primary 1px border |
| `border.soft` | `#23272E` | internal separators |

### 3.2 Text

| Token | Value |
|---|---:|
| `text.primary` | `#F4F5F7` |
| `text.secondary` | `#A7ADB7` |
| `text.tertiary` | `#737A85` |
| `text.button` | `#D4D7DD` |

### 3.3 Brand and interaction

| Token | Value | Usage |
|---|---:|---|
| `brand.primary` | `#E30074` | primary actions, active state, AI, focus |
| `brand.hover` | `#F21C88` | primary action hover |
| `brand.text` | `#FF5FAE` | interactive magenta text on dark surfaces |
| `brand.text.soft` | `#FF8CC4` | selected chips/context |
| `brand.tint` | `#1E1118` | subtle selected/AI background |
| `brand.border` | `#6A1F45` | AI/selected border |

### 3.4 Semantic colors

| Meaning | Value |
|---|---:|
| Success / Released API / compliant | `#4CC38A` |
| Attention | `#E5B53C` |
| Legacy / modernization | `#E8944A` |
| Risk / critical finding | `#F0605A` |
| Information / custom SAP | `#7EA6E8` |
| Low severity | `#8FA3BF` |

## 4. Graph node semantics

| Kind | Background | Border | Badge |
|---|---:|---:|---:|
| Custom | `#141C2A` | `#2A4470` | `#7EA6E8` |
| SAP Standard | `#191C22` | `#3A404A` | `#9098A3` |
| Released API | `#12211A` | `#275E43` | `#4CC38A` |
| Legacy | `#231A12` | `#6B4526` | `#E8944A` |
| Clean Core Risk | `#261517` | `#7C3036` | `#F0605A` |

Selected node: border `#E30074` with only a subtle halo. No neon.

## 5. Typography

Primary UI font: **Inter**, weights 400/500.  
Code/object identifiers: **JetBrains Mono**, weights 400/500.

Recommended scale:

- 24px: page title
- 18–22px: primary KPIs
- 14–14.5px: component headings
- 13–13.5px: body text
- 11–12.5px: metadata and secondary content
- 10–10.5px: labels/tags; uppercase allowed with restrained tracking

Avoid bold-heavy typography. Hierarchy comes from size, spacing, color and position.

## 6. Shape and elevation

- Chips/tags: 4px radius.
- Buttons, graph nodes, rows: 6px radius.
- Cards/canvas: 8px radius.
- Suggestion pills: up to 14px radius.
- Shadows: minimal. The selected graph node is the principal exception.

## 7. Core component patterns

### Buttons

Primary: `#E30074` background with light text.  
Secondary: transparent/dark surface with 1px border.  
AI contextual action: dark surface + magenta border/text.

### Tables and rows

- Default border separators: 1px.
- Hover: `#242831` or `#1D2128` depending on density.
- Selected row: `#1D2128` + controlled magenta border.
- Severity represented by small semantic indicators, not full-row fills.

### Cards

- Surface `#171A20`.
- 1px border.
- Minimal/no shadow.
- Do not overload each card with multiple accent colors.

### Inputs

- Surface `#171A20`.
- Border `#2B3038`.
- Focus: `#E30074`.

### Evidence links

Evidence, source references and cross-navigation are first-class components. Use mono text for object/method/line references and magenta only for clickable evidence/action affordances.

## 8. Accessibility and usability

- Preserve sufficient contrast for text and interactive controls.
- Never communicate risk only by color; include labels/icons.
- Selected and focused states must remain distinguishable without relying only on magenta.
- Graph dimming must not make all context unreadable; highlighted paths should preserve enough neighboring context to understand the relationship.
- Keyboard navigation and visible focus states are expected in production; the PoC must at least preserve clear focus semantics on critical actions.

## 9. Non-negotiable rules

1. Dark Mode is the default visual language.
2. `#E30074` is reserved for identity, AI, selection, focus and primary actions.
3. No large magenta backgrounds.
4. No pure black.
5. No neon aesthetic.
6. AI output always exposes or links to evidence when the content represents analysis or recommendation.
7. The same shell and token set must be reused across all major views.
