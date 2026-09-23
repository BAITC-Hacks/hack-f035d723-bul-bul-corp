---
name: Qadam
description: От задачи к результату.
colors:
  paper: "#f7f8fb"
  surface: "#fff"
  ink: "#20232c"
  muted: "#606978"
  line: "#e0e4ec"
  accent: "#2458e6"
  accent-strong: "#1544c7"
  focus-ring: "#6c91f7"
  control-line: "#ccd3e0"
  button-line: "#ced5e1"
  button-hover: "#edf1f9"
  selected-surface: "#edf2ff"
  badge-surface: "#edf0f6"
  badge-ink: "#485268"
  error-surface: "#fff2f0"
  error-ink: "#962e27"
  ready-surface: "#e7f4f1"
  ready-ink: "#235f52"
typography:
  display:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "48px"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-.04em"
  headline:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "44px"
    fontWeight: 650
    lineHeight: 1.1
    letterSpacing: "-.035em"
  title:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.35
    letterSpacing: "-.02em"
  body:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "14px"
    lineHeight: 1.65
  label:
    fontFamily: '"Manrope Variable", sans-serif'
    fontSize: "13px"
    fontWeight: 600
rounded:
  badge: "5px"
  field: "7px"
  control: "8px"
  panel: "12px"
  auth: "14px"
spacing:
  compact: "8px"
  related: "12px"
  field: "20px"
  section: "24px"
  panel: "28px"
  desktop-gutter: "44px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "11px 17px"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "11px 17px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "28px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "11px 12px"
  badge:
    backgroundColor: "{colors.badge-surface}"
    textColor: "{colors.badge-ink}"
    rounded: "{rounded.badge}"
    padding: "4px 8px"
---

# Design System: Qadam

## Overview

The confirmed direction is light and strict: white surfaces, graphite text, a blue accent, and large headings. This document records the implemented React interface; it does not claim an approved visual comp or introduce a new metaphor. The source of truth is `frontend/src/styles.css`, supported by `frontend/src/app/App.tsx` and `frontend/src/app/ui.tsx`.

Qadam uses Russian interface copy. Dense task information remains readable through ordered rows, clear labels, generous section spacing, and a restrained application shell.

Key characteristics:

- White working surfaces on a pale canvas.
- Large, tightly spaced headings in self-hosted Manrope.
- Blue for actions, selected navigation, and task readiness figures.
- Thin borders and flat panels.

## Colors

### Primary

Accent blue identifies primary actions and links; its stronger variant marks button hover. Selected navigation uses a pale blue surface. Status colors describe state and accompany text labels.

### Neutral

Paper is the application canvas. Surface is used for panels, navigation, forms, and row lists. Ink carries headings and primary content; muted carries descriptions, metadata, and placeholders. Line separates structural regions. Control and button borders are slightly stronger than panel borders.

## Typography

Manrope Variable is bundled through `@fontsource-variable/manrope`; sans-serif is the fallback. Headline, title, and display roles use the frontmatter values. Display belongs to the authentication introduction; headline is the usual page title. Task titles use 20px, weight 650, and section subheadings use 16px, weight 700. Descriptions commonly use 13–15px. Metadata uses 11–12px.

At the mobile breakpoint, page headings become 34px, authentication headings 38px, and detail headings 28px. Readiness figures use tabular numerals where totals are compared. Introductory descriptions stay near 65 characters per line; catalogue descriptions allow 75.

## Layout

Desktop uses a fixed 220px sidebar, an 82px top bar, and a content region capped at 1380px. Main padding is 48px 44px 64px. At 1150px and below the sidebar becomes 190px, gutters become 28px, filters become two columns, and task details stack. At 800px and below the sidebar becomes a static top navigation, content uses 20px gutters, forms become one column, and editor side panels follow the main form. The minimum supported viewport width in CSS is 320px. At 1600px and above, main top padding increases to 64px.

Catalogue rows preserve a content column and a narrow score column. Forms pair related fields on desktop. Actions wrap instead of forcing horizontal scrolling. Public profiles and profile editors use narrower reading widths.

## Elevation & Depth

The interface uses no box shadows. White surfaces, pale backgrounds, thin borders, and spacing provide separation. Hover changes color without lifting a component. State transitions last 160ms. Loading content pulses between opacity .55 and 1; reduced-motion preferences disable animations and transitions.

## Shapes

Panels use the panel radius; buttons and notices use the control radius; inputs use the field radius. Authentication forms have slightly larger corners. Borders are generally 1px. Avatars are circular. Task lists form one shared enclosure with dividers between rows.

## Components

### Buttons

Primary buttons are blue with white text. Secondary buttons are white with graphite text and a thin border. Both have a minimum height of 44px and 13px text at weight 650. Hover changes background and border. Disabled buttons reduce opacity to .48 and use a disabled cursor. Text actions use transparent backgrounds and muted text.

### Fields

Labels remain visible above controls. Inputs and selects have a minimum height of 45px; textareas start at 108px and resize vertically. Placeholder text uses muted ink at full opacity. All interactive controls receive a 3px visible focus outline with a 3px offset. Errors appear in a tinted notice with `role="alert"`.

### Navigation

Navigation combines outlined icons and text labels. Active links use blue text on a pale blue background. Mobile links wrap below the brand. A keyboard-visible skip link targets the main content; route changes focus that region.

### Catalogue and readiness

Catalogue tasks are rows rather than independent floating cards. Titles remain the primary link. Supporting metadata precedes the title, descriptions follow, and readiness stays at the right behind a divider. Readiness describes the task, not company prestige. The rating panel exposes category details and a missing-information list.

### Feedback

Loading uses a status message or skeleton rows. Failed loads must leave the loading state and display an error with an available recovery action. Empty collections use a bordered empty state with a clear next action. Status badges always retain their text meaning.

## Do's and Don'ts

- Do reuse the white, graphite, and blue palette and existing Manrope hierarchy.
- Do use visible labels, keyboard focus, wrapping actions, and reduced-motion support.
- Do keep long Russian content readable and allow it to wrap.
- Do distinguish loading, empty, error, and successful states.
- Don't add decorative shadows or a second brand accent to this established direction.
- Don't replace task readiness with a company reputation signal.
- Don't leave a loading indicator visible after a failed request.
