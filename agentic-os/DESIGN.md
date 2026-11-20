---
name: Agentic OS — Control Room
description: A restrained dark workspace for deliberate local supervision.
colors:
  primary: "#7c9eff"
  success: "#63e6be"
  warning: "#ffba75"
  danger: "#ff8585"
  background: "#0b0e14"
  surface: "#131722"
  surface-raised: "#1b2130"
  border: "#2a3143"
  text: "#e6e9ef"
  muted: "#9ca6ba"
typography:
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    fontSize: "1.85rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    fontSize: "1rem"
    fontWeight: 600
    letterSpacing: "-0.015em"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontSize: "0.929rem"
    fontWeight: 500
  meta:
    fontSize: "0.857rem"
  code:
    fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace"
    fontSize: "0.929rem"
    lineHeight: 1.65
rounded:
  control: "7px"
  surface: "12px"
  count: "5px"
spacing:
  compact: "8px"
  small: "12px"
  medium: "16px"
  panel: "20px"
  section: "24px"
  page: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#101727"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.surface}"
  mission-card:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.surface}"
    padding: "15px 13px"
  field:
    backgroundColor: "#0e131d"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "9px 11px"
---

# Design System: Agentic OS

## Overview

**Creative North Star: "Control Room"**

A dark, precise workstation surface. The existing navy identity remains intact; refinement concentrates on readable state, deliberate actions, and continuity during refresh. No remote fonts or image dependencies.

**Key Characteristics:**
- Quiet navy surfaces with one-pixel boundaries.
- Blue for selection and primary action; mint, amber, and coral for semantic state.
- System typography for controls and reading; monospace only for code, identifiers, and output.
- Brief user-triggered transitions; no animated polling or decorative motion.

## Colors

### Primary

Blue marks the current workspace, selected missions, active processes, and primary actions. Primary buttons use dark ink for contrast. The subtle navy header wash is inherited identity, not a reason to add luminous decoration elsewhere.

### Secondary

Mint identifies successful process state and approval actions. Amber identifies decisions and intermediate control states. Coral identifies errors and destructive controls. Every state also has a written label.

### Neutral

Background, surface, and raised-surface tokens distinguish the workspace from inspectors and selectable records. Muted text remains readable against both ordinary and selected surfaces. Borders separate regions without introducing shadows.

**The State First Rule.** Color communicates action, state, and selection rather than ornament.

## Typography

One system sans family carries the interface. Headings use modest scale changes and medium-to-semibold weights rather than display typography. The root measure is the body token (14px). Below it there are exactly two steps: secondary text, labels, buttons and output at (0.929rem, 13px) and metadata (counts, dates, priorities, status, footer) at (0.857rem, 12px); nothing is smaller. Card and run titles sit at the body size, the detail title at (1.143rem, 16px). The page heading steps down to (1.6rem) below the narrow breakpoint. Prose hints are bounded to (72ch).

Use tabular numerals for clocks, counts, and dates. Output uses the code role, preserves whitespace, and wraps long tokens rather than widening the page.

## Layout

The desktop container is capped at (1800px), with page insets matching the page spacing token. Ordinary sections use the section gap; panel interiors use the panel inset. Related controls use compact spacing.

The mission workspace uses a wide board and a (344px) inspection column, increasing to (380px) on wide screens. Runs use a proportional list/inspector split. Below (1100px), page insets and column gaps tighten. Below (800px), work and inspection stack; below (520px), forms and inspection regions become single-column with (16px) page insets.

The mission board scrolls horizontally inside its own region. Output scrolls within its own reading pane. Neither should create document-level horizontal scrolling. On narrow screens, deliberate selection brings the completed inspector layout into view.

## Elevation & Depth

No box-shadow system. Depth comes from tonal separation, quiet outlines, and selected-surface color. The inherited header wash is restrained. Inspection remains visually stable during background updates.

## Shapes

Panels, lanes, and mission records use the surface radius. Controls use the smaller control radius; count labels use the count radius. Icons are consistent stroked SVGs. Selection is a thin outline plus a tonal change, not a wide side stripe.

## Components

### Buttons and fields

Primary actions are solid blue with dark text; secondary actions are quiet outlined controls. Approval and destructive actions use semantic text colors. Controls have visible hover and keyboard-focus states; disabled controls reduce opacity and reject interaction. Fields use a recessed navy ground and explicit labels. Native selects and disclosure controls retain familiar behavior.

### Workspace tabs

Current state is a solid blue underline and readable label, with native tab semantics and arrow-key navigation. Counts state their meaning: missions are a total; run counts explicitly say active.

### Mission records and inspection

Selectable records expose their pressed state, title, priority, date, and a brief description. The inspector holds acceptance criteria, the latest plan, history, and only legal transitions. Forms are separate from refreshed descriptive content so drafts survive polling.

### Run output and controls

Output is text, never interpreted markup. Preserve stream chunks, distinguish stderr, and avoid live-region announcements for every output chunk. Follow new output only while the operator is at the end. Interrupt and terminate use an inline confirmation naming the selected process.

### Motion

User-triggered workspace changes use View Transitions where available; selection uses a short directional reveal. Inspection easing is (`cubic-bezier(.16,1,.3,1)`) over (240ms); control hover feedback uses (150ms). Polling never animates. Reduced motion disables effects and smooth scrolling; unsupported browsers update immediately.

**Overdrive (2026-11-18): card → inspector morph.** Selecting a mission card or run row grows it into its inspector panel via a same-document View Transition on the shared name `mc-morph` (card in the old snapshot, panel in the new), 240ms with the inspection easing; the name is cleared when the transition settles so background polling never reuses it and never animates. New run output lines fade in on a staggered ≤200ms cadence (opacity only, so layout, scroll height and screen-reader content are unaffected) with a brief pulse on the active run's status badge; any new batch, scroll or selection flushes it to the final state. Reduced motion or no View Transitions: instant, current behaviour.

**The Continuity Rule.** Background refresh must preserve selected records, keyboard focus, draft inputs, and a paused output position.

## Do's and Don'ts

### Do:
- Do pair state colors with written labels.
- Do preserve drafts, focus, selection, and reading position during refresh.
- Do keep execution and destructive control explicit.
- Do derive new interface rules from the implemented tokens and native controls.

### Don't:
- Don't confuse process completion with mission completion.
- Don't add external visual dependencies to this local workspace.
- Don't use motion to decorate background refresh.
- Don't interpret prompts or captured output as markup.
