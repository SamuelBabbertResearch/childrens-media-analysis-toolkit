# CMAT — Classic Desktop UI specification

The visual language for the PySide6 front-end. Design detail lives here rather
than in `CLAUDE.md` so that file stays a short rules-and-orientation document;
`CLAUDE.md` §4 links here.

Each section gives the specification as written, then **Qt notes** — because Qt
Style Sheets are a subset of CSS and will silently ignore what they do not
support. A rule that is dropped rather than rejected is the worst kind, so the
gaps are called out where they occur.

---

## Terminology

Call this a **Classic Desktop UI**, or a **Mavericks-inspired layout** when a
period reference is needed. Avoid naming trademarked operating systems or
applications in documentation, code comments, commit messages, or UI strings.
Section headings below follow that rule even where the source specification did
not.

## Where the colours live

Every value below resolves to a token in `ui/tokens.py`, which imports no GUI
framework and is shared by both front-ends. **Do not write a literal colour into
a widget or a stylesheet** — add or reuse a token. Two sources of truth is how
two different blues both came to mean "selected".

### Values that map to an existing token

Eight hex values in this specification are near-duplicates of colours already in
the palette. They are **not** added as new tokens; use the token instead.
Shipping both would recreate the fragmentation the token file exists to prevent
— `#3875D7` in particular is a second accent blue, and there is a test asserting
only one exists.

| In the spec | Use instead | Token | Difference |
|---|---|---|---|
| `#3875D7` | `#2B73DE` | `accent` | a second accent blue |
| `#333333` | `#202122` | `text` | near-black either way |
| `#A6A6A6` | `#A8ABB1` | `chrome_line` | seam hairline |
| `#E6E6E6` | `#F4F5F7` | `chrome_top` | chrome gradient top |
| `#D1D1D1` | `#DCDEE2` | `chrome_bottom` | chrome gradient bottom |
| `#FFFBE5` | `#FFFBE6` | `warn_bg` | one value apart |
| `#E1C463` | `#E8D9A0` | `warn_border` | callout border |
| `#4A3800` | `#5C4400` | `warn_text` | callout text |

If a difference here turns out to matter visually, change the **token** so both
front-ends move together — do not introduce a second value.

---

## 1. Modal window framing and structure

**Container (`.modal-dialog`)**

| Property | Value |
|---|---|
| Surface | `background-color: #ECECEC` |
| Window ring | `border: 1px solid #7A7A7A; border-radius: 6px` |
| Shadow depth | `box-shadow: 0 12px 30px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.6)` |

**Titlebar (`.titlebar`)**

| Property | Value |
|---|---|
| Height | fixed `24px`, `padding: 0 8px` |
| Fill | `linear-gradient(180deg, #E6E6E6 0%, #D1D1D1 100%)` |
| Seam | `border-bottom: 1px solid #A6A6A6` |
| Typography | `11px`, weight `600`, `#333333`, `text-shadow: 0 1px 0 rgba(255,255,255,0.7)` |
| Traffic lights | `10px` circles, `border: 1px solid rgba(0,0,0,0.25)` — close `#FF5F56`, min `#FFBD2E`, max `#27C93F` |

### Qt notes

- **`box-shadow` is not supported.** A real `QDialog` gets its shadow from the
  platform. For a shadow on an internal panel use `QGraphicsDropShadowEffect`.
  Writing `box-shadow` into a stylesheet does nothing and reports nothing.
- **`text-shadow` is not supported.** The engraved titlebar effect must be
  painted or omitted. Prefer omitting — it is the least load-bearing part of the
  look.
- **`inset` shadows are not supported.** Simulate a sunken edge with
  `border-top-color` darker than the other three, which Qt does honour.
- **The custom title bar is built** (`ui/native_frame.py`, `TitleBar`), and the
  way it is built is the point. The usual route — `Qt.FramelessWindowHint` —
  strips `WS_THICKFRAME` and `WS_CAPTION`, and with them Aero Snap, edge
  resizing, the drop shadow, the maximise animation, Win+Arrow, and the
  right-click system menu. That cost is what this section used to forbid, and
  it is still not acceptable.

  Instead the window keeps its real Win32 frame styles and only suppresses the
  frame's *drawing*, by answering `WM_NCCALCSIZE` with a client area covering
  the whole window. Hit testing goes back to Windows through `WM_NCHITTEST`:
  the strip answers `HTCAPTION`, so drag, snap, double-click-to-maximise and
  the system menu are all still the system's, not reimplementations. If the
  hook cannot attach, the native title bar is kept — a window that does not
  match the reference beats a window that cannot be moved.

  The lights run close, minimise, zoom left to right, which is the reference's
  order and the reverse of the Windows one. They carry tooltips, and every
  action remains on the system menu and the usual keyboard shortcuts.

---

## 2. Dialog action bars (`.dialog-action-bar`)

| Property | Value |
|---|---|
| Placement | anchored bottom, `border-top: 1px solid #B0B0B0` |
| Fill | `linear-gradient(180deg, #E2E2E2 0%, #D0D0D0 100%)` |
| Padding | `6px 10px`, vertically centred, space-between |
| Button order | secondary left (`Back`, options); primary commit right (`Create Pipeline`, `Apply & Re-score`) |

### Qt notes

- Prefer `QDialogButtonBox`: it gets platform button ordering, the default
  button, and Enter/Esc handling right without extra code.
- **One primary button per dialog.** Set the `primary="true"` property; the
  stylesheet supplies the blue treatment. More than one and it stops meaning
  "this is the default action" — the earlier mockups had three.

---

## 3. List views (`.list-view` / `QListView`)

| Element | Value |
|---|---|
| Container | sunken: `1px solid #B8B8B8`, top edge `#666666`, white fill, inset shadow |
| Row divider | `1px solid #F0F0F0` |
| Radio integration | native radio inline on the left margin |
| Selected row | fill `#2B73DE` full width; text white bold; secondary text `#E0ECFF` at `10.5px` |

### Qt notes

- Inline radios in a list mean either a `QStyledItemDelegate` that paints the
  indicator, or a scrolled column of `QRadioButton`s in a `QButtonGroup`. The
  second is simpler and keyboard-navigable by default; prefer it unless the list
  is long enough to need virtualisation.
- **Exception — data tables.** A selected row in a table of *figures* uses the
  light wash (`row_selected_bg`, `#E8F2FF`) with dark text, not the solid
  accent. White-on-blue is right for picking one item out of a list; over a
  column of numbers it destroys the contrast the numbers are read with.
  **Solid accent for choosing, light wash for reading.**

---

## 4. Group boxes and dense forms

**Framing (`fieldset` / `QGroupBox`)**

| Property | Value |
|---|---|
| Border | `1px solid #B8B8B8`, `border-radius: 3px` |
| Fill | `rgba(255,255,255,0.4)` |
| Legend | inline with the top border, `10.5px`, bold, `#333333`, `padding: 0 3px` |

**Dense form rows (`.form-row-dense`)**

| Property | Value |
|---|---|
| Input height | `19px`, `padding: 0 4px`, `font-size: 11px` |
| Numeric inputs | right-aligned, width `44px` |
| Total indicator | right-aligned validation status, `#1B7A2B`, bold, `10.5px` |

### Qt notes

- **`text-align` does not apply to `QLineEdit` via stylesheet.** Right-alignment
  must be set in code: `field.setAlignment(Qt.AlignRight)`.
- **A fixed `19px` height will clip.** Body text is 9pt ≈ 12px, so 19px leaves
  ~3px of vertical padding, and any face with taller metrics is cut off. Use
  `min-height` and let the widget grow; set the width, not the height.
- Translucent fills (`rgba(...,0.4)`) render against the parent, not the window,
  so a group box inside a tinted panel picks up that tint. Use an opaque token
  where the result must be predictable.
- The total indicator is a validation state, so it must not rely on green alone
  — pair it with a tick or the word "balanced", per the colour rule below.

---

## 5. Callouts and focus states

**Note / warning callouts (`.callout-box`)**

| Property | Value |
|---|---|
| Surface | `background: #FFFBE5; border: 1px solid #E1C463; color: #4A3800` |
| Typography | `10px`, `line-height: 1.35` |

**Focus ring** (`QLineEdit:focus`, `QComboBox:focus`)

| Property | Value |
|---|---|
| Border | `#3875D7` |
| Glow | `inset 0 1px 2px rgba(0,0,0,0.2), 0 0 0 1px #3875D7` |

### Qt notes

- **The glow uses `box-shadow`, which Qt ignores.** Achieve the same read with a
  1px accent border plus `outline: 1px solid` in the accent, or widen the border
  to 2px on focus. Do not leave the rule in believing it works.
- `line-height` is not supported in Qt Style Sheets. Line spacing in rich text
  is set through `QTextBlockFormat`; for plain labels it cannot be set at all.
- 10px callout text is below the readable floor once the display scales. Use the
  `small` role (8pt) and let Qt scale it.

---

## 6. Typography

Sizes are **points**, not pixels — Qt scales points for the display. Copying a
pixel value from a period specification is a units error: that era's "11" was
points, roughly 15px at current densities. The pixel values quoted throughout
this document are from the source specification and should be read as
proportions, not as literals to type into a stylesheet.

| Role | Size |
|---|---|
| tiny / small | 8pt |
| body / table | 9pt |
| heading | 11pt |
| title | 13pt |

Face: first available of Lucida Grande, Lucida Sans Unicode, Segoe UI, Tahoma.
Fixed-pitch (`Consolas`) is for content needing column-exact *characters* —
coding-sheet timestamps, raw provenance. **Not** for table numbers: every face
above renders digits at one fixed advance width, so right-alignment already
aligns a numeric column, and a mono face there only makes surrounding text look
like source code.

---

## 7. Constraints that outrank the visual specification

1. **The stimulus-only guardrail** (`CLAUDE.md` §2.2). No field, badge, column,
   or infobox row reports appropriateness, target audience age, educational
   value, or quality. If a mockup contains such a row, it does not get built.
2. **Windows behaviour is preserved.** Window management, keyboard conventions,
   file dialogs, DPI scaling, platform accessibility. Note the wording: the
   *behaviour*, not the native title bar — §1 explains how the strip is drawn
   without giving any of it up. A visual change that costs a window behaviour
   is still refused; one that does not is fair game.
3. **Nothing is conveyed by colour alone.** Every status carries a glyph and a
   word as well, so it survives greyscale and colour blindness.
