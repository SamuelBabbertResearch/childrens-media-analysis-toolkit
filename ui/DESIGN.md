# CMAT — Classic Desktop UI specification

The visual language for the PySide6 front-end. Design detail lives here rather
than in `CLAUDE.md` so that file stays a short rules-and-orientation document;
`CLAUDE.md` §4 links here.

Each section gives the specification as written, then **Qt notes** — because Qt
Style Sheets are a subset of CSS and will silently ignore what they do not
support. A rule that is dropped rather than rejected is the worst kind, so the
gaps are called out where they occur.

---

## 0. How to build a screen in this style

Read this section before porting anything. The screens already built —
Library, the analysis report, the Pipeline workbench, the starting-layout
wizard — were all produced by this recipe, and the places where earlier work
went wrong were all places where a step was skipped.

### 0.1 The reference stylesheets are the source, not a thing to copy from

`ui/reference/*.css` is extracted **verbatim** from the supplied HTML mockups
and committed. Do not hand-copy values out of it. Re-deriving the CSS by eye
each time is what repeatedly lost or changed values, and the losses were
invisible until the two were put side by side.

| File | Covers |
|---|---|
| `library.css` | window chrome, toolbar, tabs, tree, results tables |
| `pipeline.css` | node canvas, node cards, ports, wires, inspector, zoom pill |
| `dialogs.css` | dialog frame, list views, fieldsets, action bars |

The three agree on every value they share: `#ECECEC` ground, `#7A7A7A` window
rim, `#B8B8B8` panel border, `#2B73DE` selection, `#999999` control border,
20px buttons, 11px text, the `#429CE3 → #1066C7` accent on `#0F4F96`. **That
agreement is the design.** A fourth mockup once disagreed on all of them — its
own window colour, 22px buttons, a second blue, a bespoke 28px header — and
building from it produced something that matched no other screen. If a mockup
departs from the values above, treat the departure as the thing to question.

`ui/reference_css.py` loads them, resolves `var()` against `:root`, and hands
back a named component's rules:

```python
from ui import reference_css
reference_css.rules(("data-table", "section-title"))      # library.css
reference_css.rules(("list-item",), "dialogs")            # another file
reference_css.variables("dialogs")["--select-bg"]         # a single token
```

To re-extract after a mockup changes, use the snippet in the commit that
created `ui/reference/`; the header of each file says not to hand-edit.

### 0.2 Which of the three ways to render applies

Choosing wrongly is the biggest single time sink, so decide first.

1. **Real HTML/CSS in a `QTextBrowser`** — anything document-shaped: the
   analysis report, exports, long prose. Here the reference CSS is used
   *directly*: emit the reference's own class names (`data-table`,
   `section-title`, `sub-text`) and its stylesheet applies unchanged. This is
   the strongest reason the Qt migration was worth doing. See `ui/report.py`.
2. **Qt Style Sheets** — ordinary widget chrome. QSS is *not* CSS; it must be
   translated, never pasted. See §0.4.
3. **Drawn with `QPainter`** — anything QSS cannot describe at all: the node
   graph, the title bar, the modal header. Name the reference's values as
   constants at the top of the module so they can still be diffed against the
   CSS. See `ui/pipeline_view.py`.

### 0.3 Density is a specification, not a default

Qt's own metrics are 20–50% airier than this design. Every box metric must be
stated or the interface drifts. All of them live in `ui/tokens.py`:

| Token | Value | Reference rule |
|---|---|---|
| `FONT_PX["body"]` | 11 | `body` |
| `METRICS["row_h"]` | 19 | `.tree-row` |
| `METRICS["control_h"]` | 20 | `.btn` |
| `METRICS["dialog_input_h"]` | 19 | `input` inside `.dialog-content` |
| `METRICS["header_h"]` | 20 | `.data-table th` |
| `METRICS["titlebar_h"]` | 30 | `.titlebar` — 24 in the mockups; see below |
| `METRICS["caption_btn_w"]` | 34 | not in the mockups; Windows caption |

Sizes are **device-independent pixels**. Qt 6 scales the whole interface by
the display's device-pixel ratio, so `11px` is 11px at 100% and 16.5 physical
at 150%. This reverses the Tk rule: there a pixel was physical, which is why
`FONT_PT` still exists and is marked Tk-only.

### 0.4 Qt behaviours that have already cost time

Each of these looked like a styling failure and was not.

- **QSS selectors do not match up an inheritance chain.** A rule written for
  `QTreeWidget` does *not* apply to a `QTreeView`. Style the class you
  actually instantiate.
- **`QTextDocument` overrides heading sizes.** Qt's HTML importer applies its
  own font-size *adjustment* to `h1`–`h6` which survives the stylesheet — a
  13px rule on an `h1` still rendered near 24px. Use classed paragraphs
  (`<p class="section-title">`). A test enforces this.
- **A bare `QWidget` ignores a stylesheet background** unless
  `setAttribute(Qt.WA_StyledBackground, True)` is set. `QFrame` does not need
  it. This is why the inspector and the zoom pill first rendered untinted.
- **No `:nth-child`, `:first-child`, or `border-collapse`** in the rich text
  engine. Emit striping as an explicit class per row, mark the label column
  explicitly, and use `cellspacing="0"`.
- **Never border an item *and* set `gridline-color`** — both draw, giving the
  doubled rule between cells. Items take `border: none`.
- **A view inside a `Panel` must not draw its own frame**, or its border sits
  a pixel inside the panel's. Set the `inPanel` property.
- **Do not pin `max-height` on a header section.** It cannot then grow to fit
  its text, which is a clipped heading.
- **`ResizeToContents` pins a column** after sizing it. Hand columns back as
  `Interactive` once sized, or long names elide with no way to widen them.
- Qt has no `box-shadow`, `text-shadow`, `inset`, or `line-height`. For a
  shadow on a real widget use `QGraphicsDropShadowEffect`; on a canvas item,
  paint it.

### 0.5 The frame is drawn, and it keeps the native window

Both the main window and every dialog draw their own title strip while keeping
their real Win32 frame styles — see §1 and `ui/native_frame.py`. Never reach
for `Qt.FramelessWindowHint`: it strips `WS_THICKFRAME`/`WS_CAPTION` and takes
Aero Snap, edge resizing, the drop shadow, the maximise animation, Win+Arrow
and the system menu with it.

**The caption controls are Windows', not the mockups'.** The mockups draw
three round lights in close-minimise-zoom order. That is another platform's
convention: the order is reversed from Windows, the shapes mean nothing to
someone who has not used that platform, and there is no restore affordance.
§7 already puts platform behaviour above the visual specification, so the
strip carries minimise, maximise/restore and close, left to right at the
right-hand end, painted as Windows paints them with the red close hover. The
strip is 30px rather than the mockups' 24 because the controls need the room,
and the title is set at the platform caption size rather than the mockups'
bold small type. The glyphs are painted, not taken from an icon font, so they
need neither Segoe Fluent Icons nor Segoe MDL2 Assets installed.

This is the standing rule for the rest of the port: **take the mockups'
surfaces, gradients, spacing and type; take Windows' controls and
behaviours.**

**A dialog is a small window, not a differently-styled object.** It uses the
same 24px strip, the same round controls, the same `#ECECEC` ground and the
same one accent. A dialog that introduces its own palette is a bug.

For a new dialog, do not rebuild any of this:

```python
from ui.modal import ModalDialogFrame

body = ModalDialogFrame.install(self, "Settings — Presets & Weights",
                                lights=("close",))   # or all three
body.addWidget(...)                                  # .dialog-content
row = ModalDialogFrame.add_action_bar(self)          # .dialog-action-bar
```

`install` supplies the strip, the controls, rounded corners and the 10px
content gutter, and falls back to the native title bar if the hook cannot
attach. `WindowTitleBar` is the same class the main window uses — one
implementation, not two.

### 0.6 Choosing between a list and a set of cards

A list of options is **one inset box with hairline-divided rows**, the chosen
row filled solid `#2B73DE` with white text and `#E0ECFF` secondary text — the
native list selection. It is not a stack of separately-bordered cards; that
was the rejected mockup's idea and it reads as a web page.

Build rows from radio buttons in one `QButtonGroup` when the prose varies in
height. That gives real keyboard selection — arrow keys move between rows —
which a hand-drawn row or a `QListView` delegate would have to reimplement.

### 0.7 Two table idioms, and when each applies

- **`.data-table`** — the numeric table, used for *every* table in a results
  pane: `#EAEAEA` headers, `#B8B8B8` outer and `#D0D0D0` cell rules,
  right-aligned figures with a left-aligned first column, `#F9F9F9` striping.
  Do not switch idioms between sections; neighbouring tables in different
  styles read as unrelated kinds of thing.
- **The inspector key/value grid** — a 140px right-aligned bold key on
  `#F0F0F0` with a `#E0E0E0` divider and one `#E5E5E5` hairline per row. For
  properties of a *selected object*, not for figures.

Striping belongs to tables read *across*. A tree is read *down* a hierarchy,
where banding fights the indentation — the reference tree has none.

### 0.8 The content rule

The mockups are the **styling** specification and nothing else. Words,
columns, figures and states come from the engine. Never adopt a mockup's
invented label, metric, or number; if a mockup shows a field the software has
no data for, the field does not get built. Where the registry has more than
the mockup illustrates — seven pipeline templates against four cards — build
all of them, and add a test so a new entry cannot be forgotten.

`§7` outranks everything above.

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

One accent, `accent` / `aqua_*`: `#429CE3 → #1066C7` on `#0F4F96`, used
everywhere including dialogs. All three reference files specify it. A fourth
mockup asked for `#37A2E8 → #0066CC` on `#003A70` and was set aside — the
period gel button was *luminous*, a bright top falling to a mid blue over a
dark-but-not-black rim, and `#003A70` is nearly navy, which makes a button
read as stamped out rather than lit.

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
