# Test Strategy, Automated Test Suite & Manual UI Test Plan
## Project: Lenny Growth Assistant

---

## 1. Automated Test Suite Overview

The test suite contains **75 automated tests** written with `pytest` and `pytest-asyncio`. It validates every critical subsystem of the application:

```
tests/
├── test_phase4_skills.py  (19 tests)  — Intent routing, Grounding validation, Ship30 essay structure & self-check loops
├── test_phase5_api.py     (14 tests)  — REST API endpoints, CRUD session persistence, chat flows, artifacts & failover
└── test_security.py       (42 tests)  — Anti-XSS sanitization, Bleach script filtering, Iframe sandbox attributes & CSP
```

---

## 2. Test Execution & Coverage Summary

### Running the Full Test Suite
```bash
cd backend
.venv/bin/pytest tests/ -v
```

### Test Results Breakdown
| Test Module | Tests | Passing | Coverage Highlights |
|-------------|-------|---------|---------------------|
| `test_phase4_skills.py` | 19 | 19 / 19 | Skill routing (`qa`, `essay`, `artifact`), citation checks, essay word length & heading contract enforcement |
| `test_phase5_api.py` | 14 | 14 / 14 | Health check, Session lifecycle (Create/Get/Patch/Delete), Multi-turn chat persistence, Artifact retrieval |
| `test_security.py` | 42 | 42 / 42 | Script stripping (`<script>`, `onerror`, `onclick`, `javascript:` URLs), Iframe `sandbox="allow-scripts"`, CSP injection |
| **Total** | **75** | **75 / 75** | **100% Pass Rate** |

---

## 3. Manual UI Test Plan

Follow this step-by-step test plan to manually verify the frontend user experience:

### Step 1: Health Bar & Initial Load
1. Open `http://localhost:3000` in the browser.
2. **Verify**: All 4 health indicators at the bottom of the sidebar are green (`🗄 DB: ok`, `🔍 Index: ok`, `🤖 Primary: ok`, `↩ Fallback: ok`).

### Step 2: Dark / Light Mode Toggle
1. Click the theme toggle button (`☀️` / `🌙`) in the top navigation bar.
2. **Verify**: The interface transitions smoothly between deep navy dark mode and soft modern slate light mode.
3. Refresh the page and **verify** the selected theme persists from `localStorage`.

### Step 3: Grounded Conversational Q&A
1. Click the suggestion card **"How do top PMs think about onboarding?"** or type a query into the input bar.
2. **Verify**:
   - The typing wave animation appears while synthesizing.
   - The response renders with markdown headings and guest citations (`[1]`, `[2]`).
   - A collapsible **"📚 8 Transcript Sources"** button is displayed.
   - Expanding the source drawer displays guest names, BM25 similarity scores, text snippets, and clickable YouTube links.

### Step 4: Virtual Sandbox — Ship 30 Essay
1. Click the suggestion card **"Write a Ship 30 essay on viral growth loops"** or select `✍️ Ship30 Essay` from the skill dropdown.
2. **Verify**:
   - The right-side **Virtual Sandbox** panel automatically slides open.
   - The essay displays an immediate bold hook, structured sections, bullet points, and concludes with `## The One Thing`.
   - The **Preview** and **Code** tabs switch between formatted text and markdown source.
   - Clicking **"📋"** copies the content to the clipboard; clicking **"⬇"** downloads the `.md` file.

### Step 5: Virtual Sandbox — HTML Application
1. Click **"Generate an HTML retention dashboard calculator"** or type `"Create an interactive HTML growth calculator"`.
2. **Verify**:
   - The right-side **Virtual Sandbox** displays an interactive HTML tool.
   - Interacting with input sliders/buttons functions seamlessly inside the isolated iframe.
   - External network calls and cross-origin DOM access are completely blocked by the CSP headers.

### Step 6: Session Management
1. Click **"＋ New Chat"** in the sidebar.
2. **Verify**: A new blank session is created.
3. Click on previous sessions in the sidebar and **verify** that prior messages, sources, and artifacts reload accurately.
4. Click the **"✕"** icon on a session to verify session deletion.
