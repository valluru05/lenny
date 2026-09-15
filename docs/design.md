# Design System & UI/UX Specification
## Project: Lenny Growth Assistant

---

## 1. UI/UX Principles

1. **Information Density with Zero Clutter**:
   High-density product intelligence displayed using clear hierarchical typography, expandable source drawers, and modular panel dividers.
2. **Glassmorphism & Ambient Depth**:
   Subtle multi-layer blur backdrops (`backdrop-filter: blur(16px)`), luminous radial ambient mesh glows, and rounded cards (`--radius-lg: 18px`).
3. **Fluid Micro-Animations**:
   Physics-based spring transitions (`cubic-bezier(0.16, 1, 0.3, 1)`), wave typing indicators, pulse status badges, and smooth sliding sidebars.
4. **Dual-Theme Parity**:
   First-class support for both high-contrast Dark Mode and soft modern Light Mode with seamless switching and zero UI flickers.

---

## 2. Color System & Design Tokens

### 2.1 Dark Palette (Default)
| Token | Value | Purpose |
|-------|-------|---------|
| `--bg-app` | `#080c14` | Global viewport canvas |
| `--bg-sidebar` | `rgba(13, 18, 30, 0.85)` | Sidebar & header frosted glass |
| `--bg-card` | `rgba(21, 29, 46, 0.7)` | Suggestion cards & message bubbles |
| `--accent` | `#38bdf8` | Sky-blue primary brand accent |
| `--accent-glow` | `rgba(56, 189, 248, 0.25)` | Button & indicator glow shadow |
| `--purple-accent` | `#a855f7` | Logo gradient & badge highlight |
| `--text-primary` | `#f8fafc` | Main headings & body copy |
| `--text-secondary` | `#94a3b8` | Subtitles, labels, and captions |
| `--text-muted` | `#64748b` | Timestamps & hints |

### 2.2 Light Palette
| Token | Value | Purpose |
|-------|-------|---------|
| `--bg-app` | `#f1f5f9` | Light slate viewport background |
| `--bg-sidebar` | `rgba(255, 255, 255, 0.9)` | Sidebar frosted card background |
| `--bg-card` | `rgba(255, 255, 255, 0.85)` | Elevated white cards |
| `--accent` | `#0284c7` | Deep electric blue |
| `--text-primary` | `#0f172a` | Dark slate high-contrast text |
| `--text-secondary` | `#334155` | Secondary body text |

---

## 3. Information Architecture & Layout

```
+──────────────────────────────────────────────────────────────────────────────────────────+
|                                    Top Navigation Bar                                    |
| [Chat Title & Knowledge Subtitle]              [Fallback Warn]  [Provider Badge] [Theme] |
+───────────────────────+─────────────────────────────────────────+────────────────────────+
|        Sidebar        |             Chat Area                   |  Virtual Sandbox Panel |
|                       |                                         |                        |
| • Logo & Live Pulse   | • Hero Suggestion Cards (Empty State)   | • Sandbox Title & Badge|
| • + New Chat Button   | • User Messages (Gradient Bubble)       | • Preview / Code Tabs  |
| • Session History List| • Assistant Messages (Grounded Copy)    | • Copy & Download Btns |
|                       | • Collapsible Source Drawer             | • Iframe Sandbox /     |
|                       | • Artifact Action Banner                |   Rich Markdown View   |
| ───────────────────── | ─────────────────────────────────────── |                        |
| • System Health Strip | • Auto-Expanding Input Bar              |                        |
|   (DB, BM25, LLM, Fallback)|   (Skill Selector + Send Button)  |                        |
+───────────────────────+─────────────────────────────────────────+────────────────────────+
```

---

## 4. Key Interaction States

### 4.1 Empty / Hero State
- Displays 4 quick-start interactive suggestion cards covering Onboarding, Product-Market Fit, Ship30 Essays, and Interactive Artifacts.
- Single-click on any card immediately dispatches the prompt and initializes a titled session.

### 4.2 Message Generation & Streaming
- **Sending State**: Send button disables with metallic shimmer; typing wave indicator animates with staggered vertical dots.
- **Auto-Title**: Automatically updates session title in sidebar from the first user turn.
- **Provider Badge**: Indicates model name (`gemma3:4b`), runtime latency in ms, and fallback status.

### 4.3 Virtual Sandbox Drawer
- Auto-expands on the right (`width: min(580px, 48vw)`) upon completion of any HTML application or Ship30 essay.
- **Preview Tab**: Renders active live HTML with CSS/JS or formatted markdown document.
- **Code Tab**: Syntax-formatted monospace view with copy-to-clipboard and file download triggers.

---

## 5. Responsive Behavior & Breakpoints

- **Desktop (`> 1200px`)**: Full three-column view (Sidebar, Chat, Open Sandbox).
- **Tablet (`768px – 1200px`)**: Suggestion cards adjust to 2x2 grid; Sandbox overlays flexibly.
- **Mobile (`< 768px`)**: Single-column stack, collapsible sidebar drawer, responsive suggestion chips.

---

## 6. Accessibility (a11y) & Usability Considerations

- **Color Contrast**: Complies with WCAG AA standards (`> 4.5:1` contrast ratio for both themes).
- **Keyboard Navigation**:
  - `Enter`: Submit message.
  - `Shift + Enter`: Insert multiline newline.
  - `Escape`: Dismiss open modal dialogs.
- **Screen Readers**: Accessible ARIA labels on all icon buttons (`btn-theme-toggle`, `btn-send`, `btn-new-chat`).
