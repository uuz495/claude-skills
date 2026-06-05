"""
chatgpt_files_orchestrator.py — 单进程端到端 ChatGPT 多文件上传

设计动机:
  之前 skill 流程横跨 chrome MCP + Bash + helper 三层, 每个 batch 都要
  MCP click → Bash run helper 来回切换, 引入两类不稳定:
    1. OS 焦点竞争: Bash 子进程退出时焦点切回 Claude Code 终端,
       下一轮 MCP click 注入的事件被 Chrome 当 untrusted 拒绝
    2. 时序竞争: helper 启动时 MCP 的 click 处理可能还没完成,
       helper 抓到的是上一轮残留对话框, 不是新弹的那个

本 orchestrator 把整套流程合进单个 Python 进程:
  - 用 Chrome DevTools Protocol (CDP via WebSocket) 直接驱动页面 click
  - 同进程内顺序调用 OS-level dispatch (pyautogui)
  - 循环 N batches 全在同一进程, 焦点不切, 时序确定

依赖:
  pip install pychrome pyperclip pyautogui psutil pywin32 websocket-client

启动 Chrome 必须开 remote debugging:
  chrome.exe --remote-debugging-port=9222 (或用户开了 DevTools)

调用方式:
  python chatgpt_files_orchestrator.py --batches batches.json --prompt-file prompt.txt

  batches.json 格式:
    [
      {"cwd": "D:\\path\\to\\dir", "names": ["a.md", "b.txt"]},
      {"cwd": "C:\\Temp", "names": ["c.log"]}
    ]

注意:
  - Chrome 必须用 --remote-debugging-port=9222 启动 (检查时如发现没有, 提示用户)
  - 不依赖 chrome MCP, 也不依赖 Bash 调度
  - 单一焦点上下文 → batch 间不会被打断
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

import psutil
import pyautogui
import pyperclip
import win32gui
import win32con
import win32process
import ctypes

try:
    import websocket  # websocket-client
except ImportError:
    print("[FAIL] pip install websocket-client", file=sys.stderr)
    sys.exit(1)


CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
SCREENSHOT_SCALE_GUESS = 0.77  # 1568/2037 — auto-detected at runtime


# ---------- CDP layer ----------

class CDPSession:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url)
        self._id = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(msg))
        while True:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self._id:
                if "error" in data:
                    raise RuntimeError(f"CDP {method} error: {data['error']}")
                return data.get("result", {})

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def find_chatgpt_target() -> str | None:
    try:
        with urllib.request.urlopen(f"http://{CDP_HOST}:{CDP_PORT}/json", timeout=3) as r:
            targets = json.loads(r.read())
    except Exception as e:
        print(f"[FAIL] cannot reach Chrome CDP at {CDP_HOST}:{CDP_PORT} — start Chrome with --remote-debugging-port=9222", file=sys.stderr)
        print(f"       err: {e}", file=sys.stderr)
        return None
    for t in targets:
        if t.get("type") == "page" and "chatgpt.com" in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    return None


def js_eval(cdp: CDPSession, expr: str) -> any:
    res = cdp.send("Runtime.evaluate", {
        "expression": f"(() => {{ const r = ({expr}); return JSON.stringify(r); }})()",
        "returnByValue": True,
    })
    val = res.get("result", {}).get("value")
    if val is None:
        return None
    try:
        return json.loads(val)
    except Exception:
        return val


def cdp_click_at_css(cdp: CDPSession, css_x: float, css_y: float) -> None:
    """Synthesize a trusted click via CDP Input.dispatchMouseEvent."""
    for typ in ("mousePressed", "mouseReleased"):
        cdp.send("Input.dispatchMouseEvent", {
            "type": typ, "x": css_x, "y": css_y,
            "button": "left", "clickCount": 1,
        })


def open_file_picker_menu(cdp: CDPSession) -> bool:
    """Click composer + button via CDP, then click 'Add photos & files' menuitem.
    Returns True if OS file dialog should now be opening.
    """
    # Step 1: click + button
    plus = js_eval(cdp, """
        (() => {
            const btn = document.querySelector('[data-testid="composer-plus-btn"]');
            if (!btn) return null;
            const r = btn.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        })()
    """)
    if not plus:
        print("[FAIL] composer plus btn not found", file=sys.stderr)
        return False
    cdp_click_at_css(cdp, plus["x"], plus["y"])
    time.sleep(0.8)

    # Verify menu opened
    opened = js_eval(cdp, "document.querySelectorAll('[role=\"menuitem\"]').length")
    if not opened:
        # retry once after longer wait (throttle case)
        time.sleep(2.0)
        cdp_click_at_css(cdp, plus["x"], plus["y"])
        time.sleep(1.2)
        opened = js_eval(cdp, "document.querySelectorAll('[role=\"menuitem\"]').length")
        if not opened:
            print("[FAIL] menu did not open after 2 attempts", file=sys.stderr)
            return False

    # Step 2: click 'Add photos & files' menuitem
    target = js_eval(cdp, """
        (() => {
            const items = [...document.querySelectorAll('[role="menuitem"]')];
            const t = items.find(e => /Add photos|上传文件|附件/.test(e.textContent));
            if (!t) return null;
            const r = t.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        })()
    """)
    if not target:
        print("[FAIL] 'Add photos & files' menuitem not found", file=sys.stderr)
        return False
    cdp_click_at_css(cdp, target["x"], target["y"])
    return True


# ---------- Win32 / OS dispatch layer ----------

def _chrome_pids() -> set[int]:
    pids = set()
    for p in psutil.process_iter(["pid", "name"]):
        try:
            n = (p.info.get("name") or "").lower()
            if n in ("chrome.exe", "msedge.exe"):
                pids.add(p.info["pid"])
        except Exception:
            pass
    return pids


def find_open_dialog(min_hwnd: int = 0, timeout: float = 8.0) -> int:
    chrome_pids = _chrome_pids()
    deadline = time.time() + timeout
    while time.time() < deadline:
        candidates = []

        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.GetClassName(hwnd) != "#32770":
                return True
            title = win32gui.GetWindowText(hwnd)
            if not any(k in title for k in ("打开", "Open", "选择文件")):
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if pid not in chrome_pids:
                return True
            if hwnd <= min_hwnd:
                return True
            candidates.append(hwnd)
            return True

        win32gui.EnumWindows(cb, None)
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0]
        time.sleep(0.2)
    return 0


def attach_focus(hwnd: int) -> bool:
    """Steal foreground via AttachThreadInput trick."""
    try:
        fg = win32gui.GetForegroundWindow()
        fg_thread, _ = win32process.GetWindowThreadProcessId(fg)
        my_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        ctypes.windll.user32.AttachThreadInput(my_thread, fg_thread, True)
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            ctypes.windll.user32.AttachThreadInput(my_thread, fg_thread, False)
        time.sleep(0.3)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def find_filename_edit(dialog: int) -> int:
    edits = []
    win32gui.EnumChildWindows(dialog, lambda h, _: (edits.append(h) if win32gui.GetClassName(h) == "Edit" else None) or True, None)
    return edits[0] if edits else 0


def find_open_button(dialog: int) -> int:
    found = []

    def cb(h, _):
        if win32gui.GetClassName(h) == "Button":
            t = win32gui.GetWindowText(h)
            if "Open" in t or "打开" in t or "&O" in t:
                found.append(h)
        return True

    win32gui.EnumChildWindows(dialog, cb, None)
    return found[0] if found else 0


def click_at(x: int, y: int) -> None:
    pyautogui.click(x, y)


def clear_paste(edit: int, text: str) -> None:
    er = win32gui.GetWindowRect(edit)
    click_at((er[0] + er[2]) // 2, (er[1] + er[3]) // 2)
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.08)
    pyautogui.press("delete")
    time.sleep(0.08)
    pyperclip.copy(text)
    time.sleep(0.12)
    pyautogui.hotkey("ctrl", "v")


def upload_batch(cwd: str, names: list[str], min_hwnd: int = 0) -> tuple[bool, int]:
    """Returns (success, dialog_hwnd_for_next_min)."""
    cwd_path = Path(cwd)
    for n in names:
        if not (cwd_path / n).is_file():
            print(f"[FAIL] missing: {cwd_path / n}", file=sys.stderr)
            return False, min_hwnd

    clip_names = " ".join(f'"{n}"' for n in names)
    if len(clip_names) > 250:
        print(f"[FAIL] names clip {len(clip_names)} > 250 — split this batch", file=sys.stderr)
        return False, min_hwnd

    hwnd = find_open_dialog(min_hwnd=min_hwnd, timeout=8.0)
    if not hwnd:
        print("[FAIL] no fresh open dialog appeared", file=sys.stderr)
        return False, min_hwnd

    if not attach_focus(hwnd):
        print(f"[WARN] attach_focus failed for hwnd={hwnd}, continuing", file=sys.stderr)

    edit = find_filename_edit(hwnd)
    if not edit:
        print("[FAIL] no filename Edit", file=sys.stderr)
        return False, hwnd

    # Step 1: cd to cwd
    clear_paste(edit, str(cwd_path))
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    if not win32gui.IsWindow(hwnd):
        print("[FAIL] dialog closed during cd", file=sys.stderr)
        return False, hwnd

    # Step 2: paste relative names + click Open
    edit = find_filename_edit(hwnd)
    if not edit:
        print("[FAIL] filename Edit gone after cd", file=sys.stderr)
        return False, hwnd

    clear_paste(edit, clip_names)
    time.sleep(0.3 + 0.15 * max(0, len(names) - 1))

    open_btn = find_open_button(hwnd)
    if not open_btn:
        print("[FAIL] Open button not found", file=sys.stderr)
        return False, hwnd
    br = win32gui.GetWindowRect(open_btn)
    click_at((br[0] + br[2]) // 2, (br[1] + br[3]) // 2)
    time.sleep(1.2)

    if win32gui.IsWindow(hwnd):
        # retry once
        click_at((br[0] + br[2]) // 2, (br[1] + br[3]) // 2)
        time.sleep(1.2)
        if win32gui.IsWindow(hwnd):
            print(f"[WARN] dialog hwnd={hwnd} still alive, may have failed silently", file=sys.stderr)
            return False, hwnd

    print(f"[OK] batch dispatched: cwd='{cwd_path.name}' names={len(names)}")
    return True, hwnd


# ---------- Orchestrator ----------

def wait_chip_count(cdp: CDPSession, expected: int, timeout: float = 30.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        n = js_eval(cdp, """
            (() => {
                const composer = document.querySelector('form');
                const text = composer ? composer.innerText : '';
                const m = text.match(/[\\w\\-]+(?:\\(\\d+\\))?\\.\\w{1,8}\\b/g) || [];
                return [...new Set(m)].length;
            })()
        """) or 0
        if n >= expected:
            return n
        time.sleep(1.0)
    return js_eval(cdp, "(() => { const composer = document.querySelector('form'); const text = composer ? composer.innerText : ''; const m = text.match(/[\\w\\-]+(?:\\(\\d+\\))?\\.\\w{1,8}\\b/g) || []; return [...new Set(m)].length; })()") or 0


def insert_prompt_and_send(cdp: CDPSession, prompt: str) -> None:
    js = """
        ((P) => {
            const editor = document.querySelector('#prompt-textarea');
            editor.focus();
            document.execCommand('selectAll', false, undefined);
            document.execCommand('delete', false, undefined);
            document.execCommand('insertText', false, P);
            return true;
        })(%s)
    """ % json.dumps(prompt)
    js_eval(cdp, js)
    time.sleep(0.5)
    js_eval(cdp, "(() => { const b = document.querySelector('[data-testid=\"send-button\"]'); if (!b || b.disabled) return false; b.click(); return true; })()")


def wait_response(cdp: CDPSession, timeout: float = 600.0) -> dict:
    deadline = time.time() + timeout
    last_textlen = 0
    stable_count = 0
    while time.time() < deadline:
        state = js_eval(cdp, """
            (() => {
                const stop = !!document.querySelector('[data-testid="stop-button"]');
                const msgs = [...document.querySelectorAll('[data-message-author-role="assistant"]')];
                const last = msgs[msgs.length-1];
                const md = last?.querySelector('.markdown') || last;
                return {hasStop: stop, msgCount: msgs.length, textLen: (md?.textContent || '').length};
            })()
        """) or {}
        if not state.get("hasStop"):
            tl = state.get("textLen", 0)
            if tl == last_textlen and tl > 0:
                stable_count += 1
                if stable_count >= 3:
                    break
            else:
                last_textlen = tl
                stable_count = 0
        time.sleep(2.0)

    return js_eval(cdp, """
        (() => {
            const msgs = [...document.querySelectorAll('[data-message-author-role="assistant"]')];
            return msgs.map(m => ({
                slug: m.getAttribute('data-message-model-slug'),
                text: (m.querySelector('.markdown') || m).textContent
            }));
        })()
    """) or []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", required=True, help="JSON file: [{cwd, names}, ...]")
    ap.add_argument("--prompt-file", required=True, help="Text file with prompt")
    ap.add_argument("--no-send", action="store_true", help="upload only, don't send prompt")
    args = ap.parse_args()

    batches = json.loads(Path(args.batches).read_text(encoding="utf-8"))
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")

    ws_url = find_chatgpt_target()
    if not ws_url:
        return 1

    cdp = CDPSession(ws_url)
    try:
        total_expected = sum(len(b["names"]) for b in batches)
        cumulative_chips = 0
        last_dialog_hwnd = 0

        for i, b in enumerate(batches, 1):
            print(f"=== Batch {i}/{len(batches)}: cwd={b['cwd']!r} names={len(b['names'])}")
            if not open_file_picker_menu(cdp):
                print(f"[FAIL] could not open file picker for batch {i}", file=sys.stderr)
                return 2

            ok, last_dialog_hwnd = upload_batch(b["cwd"], b["names"], min_hwnd=last_dialog_hwnd)
            if not ok:
                print(f"[FAIL] batch {i} upload failed", file=sys.stderr)
                return 3

            cumulative_chips += len(b["names"])
            seen = wait_chip_count(cdp, cumulative_chips, timeout=30)
            print(f"  → chips: {seen}/{cumulative_chips}")
            if seen < cumulative_chips:
                print(f"[WARN] batch {i} only {seen - (cumulative_chips - len(b['names']))}/{len(b['names'])} chips appeared", file=sys.stderr)

        if args.no_send:
            print(f"[OK] uploaded {total_expected} files (--no-send, prompt skipped)")
            return 0

        print("=== Sending prompt...")
        insert_prompt_and_send(cdp, prompt)

        print("=== Waiting for response (Pro Extended can take minutes)...")
        msgs = wait_response(cdp, timeout=600)
        for m in msgs:
            print(f"--- assistant slug={m['slug']!r}")
            print(m["text"])
            print()

        # Slug check
        slugs = [m["slug"] for m in msgs]
        if any("pro" not in (s or "") and "thinking" not in (s or "") for s in slugs):
            print(f"[WARN] silent downgrade detected: slugs={slugs}", file=sys.stderr)
        return 0
    finally:
        cdp.close()


if __name__ == "__main__":
    sys.exit(main())
