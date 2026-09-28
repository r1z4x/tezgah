---
name: design-contract
description: >
  The artifact shape of a repository's design contract - the colour roles, the
  type scale, the spacing unit and its rhythm, the component inventory, and the
  state set every interactive control and every data view owes - and the rule
  that derives it from the repository's own tokens.
  Use when a UI or component turn needs a design floor, tokens, a state set or
  a named `tezgah-design` check.
---

This skill owns ONE thing: the shape of `.tezgah/design-contract.md`, the
per-repo floor a UI turn is judged against, and the derivation rule that fills it
when the repository never had a design system. The reading of the running app is
`analyze-app`'s, the measurement vocabulary is `product-analysis`'s, and the
always-on rules are `tezgah-contract`'s.

The contract is not injected into a session - `bin/tezgah-design check` reads the
file, so it costs nothing until it is used.

## The artifact

`.tezgah/design-contract.md`, in the private `.tezgah` repository beside
`.tezgah/lessons.md`. A human header, then ONE fenced `json` block: the block is
the machine half and the only part `check` reads, and the header is what a person
opens. Field names and prose stay English.

- `source` - where the floor came from: `css-custom-properties`, `tailwind-config`
  or `theme-json` when it was read out of the repository, `derived` when it could
  not be and someone chose it. An empty `source` is refused: a floor nobody can
  trace is not a floor.
- `tokens.colors` - the colour roles, as role name to hex. A measured colour that
  is not one of them is a `palette` violation.
- `tokens.type_scale` - the type steps in px. A measured `font-size` off the scale
  is a `type-scale` violation.
- `tokens.space_unit` - the spacing unit in px, and the rhythm it implies: every
  padding, margin and gap is a multiple of it, or it is a `spacing-rhythm`
  violation. `null` when the repository states none, which leaves spacing values
  unjudged rather than guessed at.
- `tokens.tap_target` and `tokens.contrast` - the WCAG 2.2 floors (SC 2.5.8:
  24x24 CSS px; SC 1.4.3: 4.5:1, 3:1 above 24px). These are the standard's, not
  the repository's; they are never derived away.
- `states.interactive` and `states.data` - the state sets below. The contract
  must carry them exactly; a floor that drops a state is a `state-set` violation.
- `components` - the inventory: one `{name, kind}` per component the repository
  owns. A component the measurement shows that is not listed is a
  `component-inventory` violation, so a new component is added here, in the same
  turn it is written.

```json
{
  "version": 1,
  "source": "css-custom-properties",
  "tokens": {
    "space_unit": 4,
    "type_scale": [14, 16, 20],
    "colors": {"text": "#111111", "surface": "#ffffff", "accent": "#0b5fff"},
    "tap_target": 24,
    "contrast": {"normal": 4.5, "large": 3.0}
  },
  "states": {
    "interactive": ["default", "hover", "focus", "active", "disabled",
                    "loading", "error"],
    "data": ["empty", "loading", "skeleton", "error", "offline", "partial",
             "long-text", "permission-denied"]
  },
  "components": [{"name": "Button", "kind": "interactive"}]
}
```

## The state set

Every interactive control owes all of `states.interactive`; every data view owes
all of `states.data`. A state that does not exist is a finding - the empty,
loading and error states usually a bigger one than a state that merely looks
wrong - and a component whose measurement does not show a state it owes gets a
`state-coverage` violation naming the states it is missing. `kind` decides which
half applies, so a component measured without one is unjudged, never passed.

## Derivation

Read the repository's own token source. In this order, and nothing else:

1. **CSS custom properties** - `--name: value` declarations in `*.css`, `*.scss`,
   `*.sass`, `*.less`. A property whose value is a colour literal is a colour
   role, named by the property (the `color-`/`c-` prefix and a trailing `-color`
   are dropped); one named `space`, `spacing`, `unit`, `rhythm` and the like
   states the unit; `font-size`/`text-size`/`fs` properties are the type scale.
2. **A Tailwind config** - `tailwind.config.{js,cjs,mjs,ts,json}`, its `colors`,
   `spacing` and `fontSize` blocks. `unit`/`base` in `spacing` states the unit;
   otherwise the greatest common divisor of the scale the config declares is it.
3. **A tokens/theme JSON** - `theme.json`, `tokens.json` or `design-tokens.json`,
   its `colors`/`palette`, `spacing` and `fontSize` keys, found at any depth.

```sh
python3 bin/tezgah-design derive --repo .          # writes .tezgah/design-contract.md
python3 bin/tezgah-design derive --repo . --json   # the same, machine-readable
```

`derive` writes nothing and exits 2 when the repository has none of the three, and it never
overwrites a contract that already exists - that file carries the component inventory someone
filled in, so a re-derive over changed tokens is a hand edit or a deliberate removal first. It
does not invent a palette, a type scale or a unit either: a repository with no design system gets
its floor written by hand, with `source: derived` and a line saying where the floor came from -
the platform's own guide (Apple HIG / Material), an existing brand asset, or a colour read off the
running screen. A derived floor is a decision someone made and wrote down, which is why the file
has to say so; an invented palette is not a floor at all.

## The check

```sh
python3 bin/tezgah-design check --contract .tezgah/design-contract.md \
  --measured .tezgah/design/measurement.json
python3 bin/tezgah-design check --contract ... --measured ... --json
```

`--measured` takes the JSON the running-app read produces - the per-component
computed styles and observed states - or a dash for stdin:

```json
{"components": [
  {"name": "Button", "kind": "interactive",
   "states": ["default", "hover", "focus", "active", "disabled", "loading",
              "error"],
   "styles": {"font-size": "16px", "padding": "8px 12px", "gap": "8px",
              "color": "#111111", "background-color": "#ffffff",
              "width": "120px", "height": "40px"}}]}
```

It prints `N violations` and one `component: rule - detail` line per
violation, and exits 0 only on `0 violations` (1 with at least one, 2 for a usage
error or an unreadable contract). The rules are `contract-source`,
`contract-palette`, `state-set`, `palette`, `type-scale`, `spacing-rhythm`,
`tap-target`, `contrast`, `state-coverage` and `component-inventory`. A measured
value the contract cannot judge - `em`, `%`, a unitless non-zero - is counted on
its own line and never read as a pass.

The checker judges only what the measurement reports. It is not a substitute for
the screen read: a turn that changed a component owes the app read AND the check,
which is what the Stop rule's `no ui_ok` class now asks for.
