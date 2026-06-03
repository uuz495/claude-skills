# Claude Code Skills — ask-gpt / ask-gpt-files

两个让 **Claude Code** 通过浏览器调用 **ChatGPT (GPT-5.5 Pro + Extended thinking)** 的 skill。

| Skill | 用途 | 调用 |
|-------|------|------|
| `ask-gpt` | 纯文字提问，GPT 回答全文 inline 返回 | `/ask-gpt <问题>` |
| `ask-gpt-files` | 带文件上传后提问（代码审查、文档分析等） | `/ask-gpt-files <file1> <file2> ... -- <prompt>` |

---

## 安装

skill 本质就是 `~/.claude/skills/<名字>/SKILL.md`。把需要的文件夹拷到你的 Claude 配置目录即可：

- **Windows**: `C:\Users\<你的用户名>\.claude\skills\`
- **macOS / Linux**: `~/.claude/skills/`

```bash
git clone <this-repo-url>
# Windows (PowerShell)
Copy-Item -Recurse claude-skills\ask-gpt        $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse claude-skills\ask-gpt-files  $env:USERPROFILE\.claude\skills\
# macOS / Linux
cp -r claude-skills/ask-gpt        ~/.claude/skills/
cp -r claude-skills/ask-gpt-files  ~/.claude/skills/
```

重开 Claude Code，`/ask-gpt`、`/ask-gpt-files` 即可用。

---

## 运行前置依赖（重要）

SKILL.md 只是「操作说明 + 几段 JS」，真正能跑还需要这套运行环境。**文件拷过去 ≠ 能用**。

### `ask-gpt`（依赖较少）

1. **Claude-in-Chrome MCP** 已安装并连上 —— skill 第一步用 `ToolSearch` 加载 `mcp__claude-in-chrome__*` 工具组，没这个 MCP 整个流程起步即断。
2. 浏览器里有一个**已登录 chatgpt.com** 的会话。
3. ChatGPT 账号为**付费 Pro**（能选 GPT-5.5 Pro + Extended），否则选模型步骤会失败或被静默降级。

### `ask-gpt-files`（依赖更多，Windows 专属）

在 `ask-gpt` 的基础上，还需要：

4. 两个本地 Python 脚本 —— **本仓库未包含，需自备**：
   - `chatgpt_files_orchestrator.py`（orchestrator 路径，§A）
   - `file_picker_helper_v3.py`（MCP+helper 路径，§B）

   SKILL.md 里写死的路径是 `D:/桌面/ai-bridge/`，自行放置后请改成你本地的实际路径。
5. Python 依赖：`pip install pychrome pyperclip pyautogui psutil pywin32 websocket-client`
6. orchestrator 路径需 Chrome 以 `--remote-debugging-port=9222` 启动。
7. **仅 Windows** —— 用到 Win32 文件对话框操作 + pyautogui，macOS/Linux 不可用。

---

## 已知脆弱点

- SKILL.md 里的 DOM 选择器（如 `data-testid="model-switcher-dropdown-button"`）绑当前 ChatGPT 网页 UI，**OpenAI 改版就会失效**，届时需更新选择器。
- ChatGPT 对自动化敏感：**不要用 patchright / zendriver / Playwright 启动 Chrome**，会被标记并静默降级到弱模型（slug 变 `gpt-5-3` / `gpt-4o-mini`）。

---

## 文件结构

```
claude-skills/
├── README.md
├── ask-gpt/
│   └── SKILL.md
└── ask-gpt-files/
    └── SKILL.md
```
