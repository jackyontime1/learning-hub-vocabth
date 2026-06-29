---
name: Daily English Reader
description: A calm bilingual reading tool for Thai learners.
colors:
  action-blue: "#1264df"
  action-blue-dark: "#0e4fb7"
  action-blue-soft: "#eaf2ff"
  ink: "#162033"
  muted-ink: "#657087"
  divider: "#e1e7f0"
  page: "#f4f7fb"
  surface: "#ffffff"
  success: "#20a967"
  success-soft: "#effaf2"
typography:
  interface:
    fontFamily: "Arial, Noto Sans Thai, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  reading:
    fontFamily: "Georgia, Times New Roman, serif"
    fontSize: "20px"
    fontWeight: 400
    lineHeight: 1.85
  title:
    fontFamily: "Arial, Noto Sans Thai, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.3
rounded:
  inline: "3px"
  compact: "4px"
  control: "5px"
  soft: "6px"
  control-large: "7px"
  panel: "8px"
  card: "12px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  xl: "20px"
components:
  button-primary:
    backgroundColor: "{colors.action-blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    height: "40px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "18px"
---

# Design System: Daily English Reader

## Overview

**Creative North Star: "The Quiet Reading Desk"**

The interface should feel like a well-organized reading desk in clear daylight: focused, dependable, and ready for repeated study. English remains the primary task while Thai support and vocabulary tools appear exactly where they help.

This is a product surface, not a promotional site. It rejects generic SaaS landing pages, decorative gradients, glass effects, nested cards, and visual noise. Familiar controls, restrained blue actions, and readable editorial spacing carry the experience.

**Key Characteristics:**
- Reading-first hierarchy
- Clear bilingual typography
- Restrained color and elevation
- Familiar controls with visible states
- Mobile-first learning support

## Colors

The palette uses a crisp action blue against cool neutral surfaces, with green reserved for successful learning states.

### Primary
- **Clear Action Blue**: Primary actions, active navigation, focus cues, and interactive emphasis.
- **Deep Action Blue**: Hover and pressed states for primary actions.
- **Quiet Blue Tint**: Selected or informative backgrounds that must remain visually light.

### Neutral
- **Reading Ink**: Primary English and Thai text.
- **Supporting Ink**: Secondary labels and metadata; never use it below accessible contrast.
- **Cool Divider**: Structural separators and control outlines.
- **Clear Page**: The quiet app background behind reading surfaces.
- **White Surface**: Reading panels, navigation, and popup surfaces.

### Named Rules

**The One-Action-Color Rule.** Blue indicates interaction or current state; it is never scattered as decoration.

## Typography

**Display Font:** Arial with Noto Sans Thai and sans-serif fallbacks
**Body Font:** Georgia with Times New Roman and serif fallbacks for English reading
**Label Font:** Arial with Noto Sans Thai and sans-serif fallbacks

**Character:** Interface text is plain and dependable. Story text uses a familiar serif for sustained English reading, while Thai support uses the interface stack for clarity.

### Hierarchy
- **Title** (700, 20px, 1.3): Section and popup hierarchy.
- **Reading body** (400, 20px, 1.85): English story text, capped near 72 characters per line.
- **Interface body** (400, 16px, 1.5): Thai translation, controls, and supporting explanations.
- **Label** (700, 12-13px): Metadata and compact actions; avoid unnecessary uppercase tracking.

### Named Rules

**The Two-Language Comfort Rule.** English and Thai must each have enough line height and width to be read continuously, never squeezed into decorative boxes.

## Elevation

The system is flat by default. Borders and tonal backgrounds establish structure; a compact shadow is reserved for floating vocabulary UI that must sit above the reading surface.

### Shadow Vocabulary
- **Floating vocabulary** (`0 6px 8px rgba(17,31,54,.16)`): Vocabulary popup only.

### Named Rules

**The Flat Reading Rule.** Reading sections stay flat and stable; elevation appears only when an interaction genuinely floats above content.

## Components

### Buttons
- **Shape:** Compact, gently rounded controls (5px radius).
- **Primary:** Clear Action Blue with white text and at least a 40px height.
- **Hover / Focus:** Deep Action Blue on hover and a visible blue focus outline.
- **Secondary:** White or Quiet Blue Tint with a Cool Divider outline.

### Cards / Containers
- **Corner Style:** Restrained panel corners (8px radius).
- **Background:** White Surface or a quiet semantic tint.
- **Shadow Strategy:** Flat by default; do not pair a panel border with a broad decorative shadow.
- **Border:** Cool Divider when a boundary is needed.
- **Internal Padding:** 14-20px according to information density.

### Navigation
- Active navigation uses Clear Action Blue and a visible structural indicator. Mobile navigation remains fixed and uses familiar icon-plus-label controls.

### Vocabulary Popup
- A compact floating learning surface with word, optional IPA, part of speech, Thai meaning, browser speech, and save state.
- Missing optional metadata is hidden rather than replaced with fabricated content.

## Do's and Don'ts

### Do:
- **Do** keep prose between 65 and 75 characters per line.
- **Do** use visible keyboard focus and practical 44px mobile touch targets.
- **Do** keep optional learning metadata fail-safe and truthful.
- **Do** use restrained tonal sections and separators for bilingual content.

### Don't:
- **Don't** imitate generic SaaS landing pages or startup dashboards.
- **Don't** use purple or blue gradients, glassmorphism, glow effects, or decorative icon tiles.
- **Don't** build excessive cards, nested cards, or full-page highlighting that makes reading visually noisy.
- **Don't** use tiny gray text, weak contrast, ornamental motion, or over-polished promotional copy.
- **Don't** use colored side-stripe borders on translation or phrase sections.
