---
name: ask-gpt-files
description: Send files + a question to ChatGPT (GPT-5.5 Pro Extended if available, else Thinking) via user's daily Chrome. Two paths — orchestrator (preferred, single-process CDP + OS dispatch) or chrome MCP + helper hybrid (fallback). Avoids silent downgrade.
metadata:
  short-description: Ask GPT (Pro Extended preferred) with file uploads — orchestrator path preferred, MCP+helper fallback
---

# /ask-gpt-files — query ChatGPT with file uploads

Invocation:

```
/ask-gpt-files <file1> <file2> ... -- <prompt>
```

Examples:
```
/ask-gpt-files D:/path/x/a.md D:/path/x/b.py -- review these files
/ask-gpt-files D:/path/MM_ARCHITECTURE.md -- what race conditions does this design have?
```

Model: **prefer GPT-5.5 Pro + Extended thinking**, fall back to Thinking if Pro quota is exhausted. Reply is returned inline in full.

---

## Path selection

| File count | Recommended path | Rationale |
|---|---|---|
| 1-3 small files, single-batch path string ≤ 250 chars | **MCP + helper path** (§B) | Uses user's daily Chrome (no CDP flag needed), simple |
| ≥ 4 files / path string > 250 chars / real phase audit scenario | **Orchestrator path** (§A) | Single-process focus stays put, multi-batch stable, cwd-nav auto-batches |

> Empirical 2026-04: Windows file-open dialog filename Edit field has a ~259 char hard limit. 13 absolute Chinese paths totalling ~981 chars overflow → input truncated → Enter rejected. The orchestrator solves this via cwd-navigation: paste an absolute directory + Enter (dialog `cd`), then paste relative filenames. Per-file clip cost drops from ~85 to ~25 chars, so most phase audits fit in one batch per directory.

---

# §A. Orchestrator path (preferred for multi-file)

**Script**: `D:/桌面/ai-bridge/chatgpt_files_orchestrator.py`

## A.1 Prerequisites

- User must launch Chrome with `--remote-debugging-port=9222` (or have DevTools open exposing the same port)
- A ChatGPT tab must already be open (script auto-discovers it)
- Do not touch mouse/keyboard while it runs (pyautogui is focus-sensitive)
- Dependencies: `pip install pychrome pyperclip pyautogui psutil pywin32 websocket-client`

> The previous SKILL warned "do not add `--remote-debugging-port` to Chrome" based on stale info about Chrome 119+ triggering Google re-login. **Empirical 2026-04: a normal user Chrome profile with the 9222 flag retains ChatGPT login state**. The thing to still avoid is launching Chrome via patchright / zendriver / Playwright — those get flagged and silently downgraded by ChatGPT.

## A.2 Batch construction

The orchestrator takes a `batches.json` describing each batch's `cwd` + `names`:

```json
[
  {"cwd": "<abs_dir_1>", "names": ["rel1.md", "rel2.txt"]},
  {"cwd": "<abs_dir_2>", "names": ["rel3.log"]}
]
```

Constraint: `" ".join(f'"{n}"' for n in names)` length ≤ 250 chars per batch.

**Bucketing strategy**:
1. Group target absolute paths by `dirname` → file list
2. Within each directory: accumulate `f'"{name}"' + " "` length, split at >250
3. Multiple batches sharing the same directory all use the same cwd

Capacity estimate (Chinese paths share ~30 char common prefix): ~25 chars per filename + quote + space → ~28 chars/file → about 8-9 files per batch.

**Real example** (PY1 phase audit, 13 files, verified end-to-end):
```json
[
  {"cwd": "D:\\桌面\\Polymarket\\scripts\\polymarket-engine\\tests\\mm_scenarios", "names": ["building_blocks.md", "evil_architecture.md", "HANDOFF_PHASE_PY1_TO_TEAM.md", "s01_cold_start_static.md", "s02_analysis.md", "run_s01.sh", "run_s02.sh", "PHASE_PY1_VERIFICATION.md"]},
  {"cwd": "D:\\桌面\\Polymarket\\scripts\\polymarket-engine", "names": ["MM_ARCHITECTURE.md", "MM_BATCHES.md"]},
  {"cwd": "D:\\桌面\\Polymarket\\scripts\\polymarket-engine\\target\\ai", "names": ["rust_sources_bundle.txt"]},
  {"cwd": "C:\\Users\\32956\\AppData\\Local\\Temp", "names": ["phase_PY1_diff.patch", "s05_raw_head.log"]}
]
```

## A.3 Invocation

```bash
python "D:/桌面/ai-bridge/chatgpt_files_orchestrator.py" \
  --batches /tmp/py1_batches.json \
  --prompt-file /tmp/py1_prompt.txt
```

Optional `--no-send`: upload only, do not send the prompt (lets the user manually review attachments in the ChatGPT UI).

## A.4 Internal flow (one process)

1. Open WebSocket to CDP via `http://127.0.0.1:9222/json` and find the chatgpt.com tab
2. For each batch:
   a. CDP `Input.dispatchMouseEvent` clicks the + button (CSS coords, no screenshot scaling needed)
   b. Wait 0.8s, query whether menu opened; retry once if not
   c. CDP click on "Add photos & files" menuitem
   d. Win32 wait for a new `#32770` dialog (`min_hwnd` strictly greater than previous batch's, prevents grabbing stale dialogs)
   e. AttachThreadInput steals foreground (works around `SetForegroundWindow` access-denied)
   f. OS-click filename Edit center → forces keyboard focus on the Edit
   g. Clear + paste cwd absolute path + Enter (dialog navigates)
   h. Wait 1.0s, re-query filename Edit (focus drifts after cd)
   i. Clear + paste relative-name clip
   j. OS-click Open button (`打开(&O)` / `Open`); retry once on failure
3. After all batches: chip watermark check — JS-count chips ≥ cumulative expected
4. CDP `execCommand insertText` writes the prompt
5. CDP click on `[data-testid="send-button"]`
6. Poll until stop-button absent and textLen stable for 3 samples
7. JS-grab all assistant messages + slug; warn if slug lacks `pro`/`thinking` (silent downgrade detected)

## A.5 Inline output

```
GPT-5.5 Pro/Thinking (Extended) + files [N total, K batches] reply:

<full text>

[INFO] model slug: <slug>
```

**WARN** when slug is `gpt-5-3` / `gpt-4o-mini`: silent downgrade has occurred (empirically observed in the 13-file + large-attachment scenario, slug came back as `gpt-5-3`).

---

# §B. MCP + helper path (fallback for 1-3 simple files)

Uses the user's **daily Chrome** (operated through the Chrome MCP Extension API), and only drops to pyautogui at the OS file dialog step. **For multi-file / high-DPR / long-path scenarios use §A instead.**

**Prerequisites:**
- User's daily Chrome must be running with the Claude extension online
- Do not touch mouse/keyboard while pyautogui runs
- Helper: `D:/桌面/ai-bridge/file_picker_helper_v3.py` (**v3 is required**, v1 / v2 are deprecated)

## B.0 ToolSearch loading

```
ToolSearch select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__find,mcp__claude-in-chrome__browser_batch
```

## B.1 Parse input + locate/open tab

Same as before: split file list + prompt, validate paths exist; reuse existing chatgpt tab via `tabs_context_mcp`, otherwise `tabs_create_mcp` + `navigate`.

## B.2 Set Pro Extended (with fallback + persistence detection)

**First check the persisted badge**: if the composer already shows an "Extended Pro" / "Extended Thinking" badge, skip the entire setup flow:

```javascript
(() => {
  const badge = document.querySelector('form')?.innerText.match(/Extended\s*(Pro|Thinking)/);
  return {alreadySet: badge?.[0] || null};
})()
```

Otherwise run the model-selection JS (open dropdown → pick Pro → Configure → pick Extended → close modal; if Pro is missing, fall back to Thinking).

```javascript
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const picker = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
  if (!picker) return {error: 'picker not found'};
  picker.click();
  await sleep(500);

  let target = document.querySelector('[data-testid="model-switcher-gpt-5-5-pro"]');
  let modeName = 'Pro';
  if (!target) {
    target = document.querySelector('[data-testid="model-switcher-gpt-5-5-thinking"]');
    modeName = 'Thinking';
  }
  if (!target) { document.body.click(); return {error: 'no Pro nor Thinking available'}; }
  target.click();
  await sleep(800);

  picker.click();
  await sleep(500);
  const cfg = document.querySelector('[data-testid="model-configure-modal"]');
  if (cfg) {
    cfg.click();
    await sleep(1500);
    const modal = document.querySelector('[role="dialog"]');
    if (modal) {
      const radios = [...modal.querySelectorAll('[role="radio"]')];
      const r = radios.find(x => x.textContent.trim().startsWith(modeName) || (modeName==='Pro' && x.textContent.trim().startsWith('专业')));
      if (r && r.getAttribute('aria-checked') !== 'true') { r.click(); await sleep(400); }
      const combos = [...modal.querySelectorAll('[role="combobox"]')];
      const tc = combos.find(c => /Standard|Extended|标准|扩展|延展/.test(c.textContent));
      if (tc && !/Extended|扩展|延展/.test(tc.textContent)) {
        tc.click(); await sleep(500);
        const lb = document.querySelector('[role="listbox"]');
        const opt = lb ? [...lb.querySelectorAll('[role="option"]')].find(o => /Extended|扩展|延展/.test(o.textContent)) : null;
        if (opt) { opt.click(); await sleep(400); }
      }
      document.querySelector('[data-testid="close-button"]')?.click();
      await sleep(500);
    }
  }
  return {ok: true, mode: modeName};
})()
```

Report to the user whether the run is on Pro or fell back to Thinking.

## B.3 Trigger the OS file dialog (**Ctrl+U is no longer usable**)

> **Empirical 2026-04**: ChatGPT's Ctrl+U binding has been removed. chrome MCP `computer.key ctrl+u` is a synthesized event that ChatGPT does not treat as a user gesture; OS-level pyautogui ctrl+u is intercepted by Chrome as "View Source" and opens a `view-source:` tab. **You must click the + button followed by the secondary menuitem.**

```
1. JS-query the + button (data-testid=composer-plus-btn) bounding-rect center
2. Translate the CSS coord into screenshot space:
     mcpX = CSS_X * (1568 / window.innerWidth)
   (Chrome MCP uses screenshot-pixel space, not CSS px, on high-DPR displays)
3. computer.left_click coordinate=[mcpX, mcpY]   (do NOT use ref=ref_X — high-DPR ref click only fires hover)
4. wait 1-1.5s
5. JS-query the [role="menuitem"] whose text starts with "Add photos & files", get its bounding-rect center → translate the same way
6. computer.left_click coordinate=[mcpX, mcpY]
```

**Things that absolutely do not work (all verified failing):**
- ❌ Ctrl+U in any form (synthetic and OS-level both fail)
- ❌ JS `.click()` on a hidden file input — Chrome user-gesture restriction
- ❌ JS `.click()` on the secondary menuitem — dialog opens but Chrome does not bind it to the hidden file input → 0 chips
- ❌ chrome MCP `left_click ref=ref_X` on DPR > 1 displays — only fires the hover tooltip, never a real click
- ❌ Caching the + button coords — its y-coordinate drifts as chip count grows; re-query before every menu open
- ❌ Burst clicks — ChatGPT throttles them; if the menu fails to open, wait 5-10s and retry once

## B.4 Multi-file batching (v3 helper, cwd-nav mode)

> Windows file-open dialog filename Edit has a ~259 char limit. v1 helper used absolute paths and 13 Chinese paths overflowed (~981 chars). v3 helper compresses each batch to ~170 chars by `cd`-ing the dialog to a directory and pasting relative filenames.

**4a. Compute batches**: group all paths by dirname; within each group keep `" ".join(f'"{n}"' for n in names)` ≤ 250 chars.

**4b. First batch**: trigger the dialog (§B.3 flow), then immediately invoke the v3 helper:
```bash
python "D:/桌面/ai-bridge/file_picker_helper_v3.py" \
  --cwd "<abs_dir>" \
  <relname1> <relname2> ...
```

Internal flow of helper v3:
1. Find the Chrome `#32770` dialog (PID-filtered to chrome.exe)
2. SetForegroundWindow + verify foreground
3. **OS-click filename Edit center** (mandatory, otherwise paste lands in the file list rather than the field)
4. Ctrl+A + Delete to clear (defensive against residue)
5. Paste cwd absolute path + Enter → dialog navigates to that directory
6. Re-locate filename Edit (focus drifts after cd)
7. Paste the relative-name clip
8. **OS-click Open button** (`打开(&O)` / `Open`, rect center) — do not rely on Enter (Chinese-titled dialogs occasionally ignore it)

Success line: `[OK] dispatched N file(s) via cwd '<dirname>', clip <X> chars`.

**4c. Wait 5-10s + chip watermark check**:

```javascript
((basenames) => {
  const composer = document.querySelector('form');
  const text = composer?.innerText || '';
  const result = {};
  for (const bn of basenames) {
    const stem = bn.replace(/\.\w+$/, '');
    result[bn] = text.includes(stem);
  }
  return {result, allChips: [...new Set(text.match(/[\w\-]+(?:\(\d+\))?\.\w{1,8}\b/g) || [])]};
})([...basenames])
```

ChatGPT renames duplicates to `xxx(1).md`, so match by stem (filename without extension).

**4d. Next batch**: re-run §B.3 flow to open a fresh dialog, then call v3 helper with the next cwd + names.

**4e. Failure handling**:
- helper exit code 5 (dialog still alive after Open click): re-trigger the menu and rerun the batch
- helper exit code 3 (no dialog within 6s): the menu click did not land, go back to §B.3
- After 3 retry rounds with files still missing → tell the user which ones were lost

## B.5 Insert prompt + send (same as orchestrator)

`document.execCommand('insertText', ...)` against the ProseMirror editor, then click the send-button. The URL must switch to `chatgpt.com/c/<uuid>` within 5s; otherwise the ProseMirror state did not sync — resend.

## B.6 Polling + reply extraction + slug validation

Every minute check stop-button + textLen. Stop-button gone AND textLen unchanged across 3 samples → done.

```javascript
(() => {
  const msgs = [...document.querySelectorAll('[data-message-author-role="assistant"]')];
  // Pro Extended occasionally emits two messages (preface + actual answer); grab them all
  return msgs.map(m => ({
    slug: m.getAttribute('data-message-model-slug'),
    text: (m.querySelector('.markdown') || m).textContent
  }));
})()
```

slug must contain `pro` or `thinking`. `gpt-5-3` / `gpt-4o-mini` → silent downgrade WARN (verified in multi-file large-attachment scenarios).

---

## Failure handling table

| Failure | Action |
|---|---|
| File missing / path with spaces not quoted | Fail at validation, ask user to fix |
| chrome MCP extension offline | Tell user Chrome is closed or extension is offline |
| `--remote-debugging-port=9222` not enabled (orchestrator path) | Fail and ask user to relaunch Chrome with the flag |
| Menu does not open after + click (throttled) | Wait 5-10s and retry once; still nothing → fail |
| Helper reports `no open dialog found within 6s` | Secondary menu click did not land / multiple `#32770` competing. Helper PID-filters to chrome.exe; if it still cannot find one the dialog truly did not open |
| Helper reports `dialog still alive after Open click` | Open-button click coord wrong (DPI-awareness issue) / Edit was empty. Re-trigger a fresh menu and rerun this batch |
| Chip not visible within 30s | File too large or network slow; wait longer or check whether the file type is supported |
| URL not switched to `/c/<id>` within 5s | ProseMirror payload empty, refresh and resend |
| ChatGPT shows "Something went wrong" | OpenAI server-side issue, **never click ChatGPT's retry button** (it rewrites the URL to `?prompt=...` and strips all attachments). Restart `/ask-gpt-files` from step 1 |
| slug missing `pro` / `thinking` | Silent downgrade; account or network flagged. **Notify the user** but do not auto-retry — a retry hits the same flag |
| Pro Extended emits preface + actual answer (2 messages) | When extracting the reply, concatenate all assistant messages, or pick the last non-empty one |
| Thinking timeout > 20 minutes | Ask user whether to keep waiting or abort |

---

## Things not to do

- **Do not launch Chrome via patchright / zendriver / Playwright** — gets flagged and downgraded by ChatGPT
- **Do not stuff file contents into the prompt** — context overflow defeats the point of file upload
- **Do not use Ctrl+U** — broken, see §B.3
- **Do not cache + button or menuitem coordinates** — they drift as chip count changes
- **Do not invoke helper v1 / v2** — deprecated; always use v3
- **Do not let other windows steal focus while pyautogui runs** — focus chaos
- **Do not summarize / truncate the reply** — return the full text inline
