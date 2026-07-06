# Design tokens — Map redesign

Source of truth: `frontend/static/css/tokens.css`. Linked from the `/map` page only (see
seam comment in tokens.css) until a wider rollout is decided.

## Principles

- **The pale map is the page; the dark instrument surrounds it.** The map itself — pins,
  paper, ground — carries the organisms being recorded. Chrome (drawer, config sheet,
  chips) is a dark, quiet instrument that frames the map without competing with it.
- **Serif for the organism and the invitation, sans for the instrument and the data.**
  Species names and headings that name a living thing use the display serif — they are
  the organism's voice. Controls, counts, filters, and sliders use the UI sans stack —
  they are the instrument's voice, not the subject's.
- **Minimum touch target: 44px.** Every tappable control — chips, drawer rows, sheet
  handles, base-layer buttons — must resolve to at least a 44×44px hit area, regardless
  of visual size.

## Colour tokens

| Token | Value | Role |
|---|---|---|
| `--ink` | `#1E2A22` | Darkest instrument surface (drawer, sheet chrome) |
| `--ground` | `#EEF0EA` | Map/page background |
| `--paper` | `#FDFDFB` | Card and panel surfaces |
| `--moss` | `#5A6B58` | Primary instrument text/icon colour |
| `--moss-light` | `#8A9884` | Secondary/muted instrument text |
| `--leaf` | `#7E9471` | Active/selected state accent |
| `--leaf-pale` | `#C9D2BC` | Subtle fills, hover states |
| `--hairline` | `#D8DCD2` | Dividers, borders |
| `--damson` | `#5B3A4E` | Fungi/secondary category accent |
| `--amber` | `#C89B3C` | Warning/attention accent |
| `--water` | `#6E8FA8` | Water/landscape category accent |
| `--alert` | `#B0524A` | Destructive/error state |

## Type roles

- **Display serif** — `Georgia, 'Times New Roman', serif` — species names, section
  headings, anything naming or inviting attention to a living organism.
- **UI sans** — system stack — controls, labels, counts, filters, sliders, all
  instrument chrome.
