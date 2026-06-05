"""
file_picker_helper_v3.py — relative-path 优化版

v2 限制: Windows Open dialog filename Edit 上限 ~259 chars
        13 个绝对中文路径 (avg 85 chars) → 必须拆 5 batch

v3 思路: 先把对话框 cwd 切到公共父目录 (绝对路径粘贴 + Enter 自动导航),
        再用相对路径粘贴文件名集合 → clip 长度暴跌, 多数场景一批塞满.

调用方式:
  python file_picker_helper_v3.py --cwd "<abs_dir>" -- "<relname1>" "<relname2>" ...

流程:
  1. _focus_dialog (找 chrome.exe 的 #32770 对话框)
  2. OS-click filename Edit → 强焦点
  3. 清空 (Ctrl+A + Delete)
  4. 粘贴 cwd 绝对路径 + Enter → 对话框 cd
  5. 等 0.8s (cd 渲染)
  6. 重新 OS-click filename Edit (cd 后焦点可能漂)
  7. 清空 + 粘贴相对文件名 clip
  8. OS-click Open 按钮 (中文标题 Enter 不可靠)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psutil
import pyautogui
import pyperclip
import win32gui
import win32con
import win32process


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


def _find_open_dialog(min_hwnd: int = 0) -> int:
    """min_hwnd: 只返回 hwnd > min_hwnd 的对话框 (用于跳过残留)."""
    chrome_pids = _chrome_pids()
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
    if not candidates:
        return 0
    candidates.sort(reverse=True)
    return candidates[0]


def _focus_dialog(timeout_sec: float = 6.0, min_hwnd: int = 0) -> int:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        hwnd = _find_open_dialog(min_hwnd)
        if hwnd:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                if win32gui.GetForegroundWindow() == hwnd:
                    return hwnd
            except Exception:
                pass
        time.sleep(0.2)
    return 0


def _find_filename_edit(dialog_hwnd: int) -> int:
    edits = []
    def cb(h, _):
        if win32gui.GetClassName(h) == "Edit":
            edits.append(h)
        return True
    win32gui.EnumChildWindows(dialog_hwnd, cb, None)
    return edits[0] if edits else 0


def _find_open_button(dialog_hwnd: int) -> int:
    found = []
    def cb(h, _):
        cls = win32gui.GetClassName(h)
        text = win32gui.GetWindowText(h)
        if cls == "Button" and ("Open" in text or "打开" in text or "&O" in text):
            found.append(h)
        return True
    win32gui.EnumChildWindows(dialog_hwnd, cb, None)
    return found[0] if found else 0


def _clear_and_paste_to_edit(edit_hwnd: int, text: str) -> None:
    """OS-click edit center, clear, paste."""
    er = win32gui.GetWindowRect(edit_hwnd)
    pyautogui.click((er[0] + er[2]) // 2, (er[1] + er[3]) // 2)
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.08)
    pyautogui.press("delete")
    time.sleep(0.08)
    pyperclip.copy(text)
    time.sleep(0.12)
    pyautogui.hotkey("ctrl", "v")


def upload_with_cwd(cwd: str, names: list[str]) -> int:
    if not names:
        print("[FAIL] no names given", file=sys.stderr)
        return 1

    cwd_path = Path(cwd)
    if not cwd_path.is_dir():
        print(f"[FAIL] cwd not a dir: {cwd}", file=sys.stderr)
        return 1
    for n in names:
        full = cwd_path / n
        if not full.is_file():
            print(f"[FAIL] not a file: {full}", file=sys.stderr)
            return 1

    clip_names = " ".join(f'"{n}"' for n in names)
    if len(clip_names) > 250:
        print(f"[WARN] names clip {len(clip_names)} chars > 250, may truncate", file=sys.stderr)

    time.sleep(0.5)
    hwnd = _focus_dialog()
    if not hwnd:
        print("[FAIL] no open dialog within 6s", file=sys.stderr)
        return 3

    edit = _find_filename_edit(hwnd)
    if not edit:
        print("[FAIL] no filename Edit child", file=sys.stderr)
        return 4

    # Step 1: navigate dialog to cwd by pasting absolute dir + Enter
    _clear_and_paste_to_edit(edit, str(cwd_path))
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.9)  # let dialog cd

    # Sanity: dialog should still be alive (cd doesn't close it)
    if not win32gui.IsWindow(hwnd):
        print("[FAIL] dialog closed during cd step", file=sys.stderr)
        return 6

    # Step 2: re-focus filename edit (focus may have drifted to file list after cd)
    edit = _find_filename_edit(hwnd)
    if not edit:
        print("[FAIL] filename Edit gone after cd", file=sys.stderr)
        return 7

    _clear_and_paste_to_edit(edit, clip_names)
    settle = 0.3 + 0.15 * max(0, len(names) - 1)
    settle = min(settle, 3.0)
    time.sleep(settle)

    # Step 3: OS-click Open button
    open_btn = _find_open_button(hwnd)
    if open_btn:
        br = win32gui.GetWindowRect(open_btn)
        pyautogui.click((br[0] + br[2]) // 2, (br[1] + br[3]) // 2)
    else:
        pyautogui.press("enter")
    time.sleep(0.9)

    if win32gui.IsWindow(hwnd):
        print(f"[WARN] dialog hwnd={hwnd} still alive after Open click", file=sys.stderr)
        return 5

    print(f"[OK] dispatched {len(names)} file(s) via cwd '{cwd_path.name}', clip {len(clip_names)} chars")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", required=True, help="absolute directory to cd to")
    ap.add_argument("names", nargs="+", help="relative file names under cwd")
    args = ap.parse_args()
    return upload_with_cwd(args.cwd, args.names)


if __name__ == "__main__":
    sys.exit(main())
