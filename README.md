# Claude Code Skills — ask-gpt 系列 + GPT 协作工作流

一组让 **Claude Code** 与 **ChatGPT (GPT-5.5 Pro + Extended thinking)** 协作的 skill：浏览器自动提问、带文件提问、多轮构建数学理论、以及把一条任务链打包给 GPT 做对抗式审计。

| Skill | 用途 | 调用 |
|-------|------|------|
| `ask-gpt` | 纯文字提问，GPT 回答全文 inline 返回 | `/ask-gpt <问题>` |
| `ask-gpt-files` | 带文件上传后提问（代码审查、文档分析等） | `/ask-gpt-files <file1> <file2> ... -- <prompt>` |
| `ask-gpt-theory` | 多轮（rounds 格式）向 GPT 构建数学理论，prompt/answer/summary 三文件闭环 | `/ask-gpt-theory <主题>` |
| `claude-gpt-audit-pack` | 把整条任务链打包成审计包，交给外部 GPT 对抗式审查 | `/claude-gpt-audit-pack` |

> `ask-gpt-theory` 与 `claude-gpt-audit-pack` 是**纯 prompt skill**（只有 SKILL.md，无运行时依赖），拷进去即可用。
> `ask-gpt` / `ask-gpt-files` 需要浏览器自动化运行环境，见下方「运行前置依赖」。

---

## 安装

skill 本质就是 `~/.claude/skills/<名字>/SKILL.md`。把需要的文件夹拷到你的 Claude 配置目录即可：

- **Windows**: `C:\Users\<你的用户名>\.claude\skills\`
- **macOS / Linux**: `~/.claude/skills/`

```bash
git clone <this-repo-url>
# Windows (PowerShell)
Copy-Item -Recurse claude-skills\ask-gpt               $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse claude-skills\ask-gpt-files         $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse claude-skills\ask-gpt-theory        $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse claude-skills\claude-gpt-audit-pack $env:USERPROFILE\.claude\skills\
# macOS / Linux
cp -r claude-skills/ask-gpt               ~/.claude/skills/
cp -r claude-skills/ask-gpt-files         ~/.claude/skills/
cp -r claude-skills/ask-gpt-theory        ~/.claude/skills/
cp -r claude-skills/claude-gpt-audit-pack ~/.claude/skills/
```

重开 Claude Code，对应 `/<skill 名>` 即可用。

---

## 运行前置依赖（重要）

`ask-gpt` / `ask-gpt-files` 的 SKILL.md 只是「操作说明 + 几段 JS」，真正能跑还需要这套运行环境。**文件拷过去 ≠ 能用**。（`ask-gpt-theory`、`claude-gpt-audit-pack` 无此问题。）

### `ask-gpt`（依赖较少）

1. **Claude-in-Chrome MCP** 已安装并连上 —— skill 第一步用 `ToolSearch` 加载 `mcp__claude-in-chrome__*` 工具组，没这个 MCP 整个流程起步即断。
2. 浏览器里有一个**已登录 chatgpt.com** 的会话。
3. ChatGPT 账号为**付费 Pro**（能选 GPT-5.5 Pro + Extended），否则选模型步骤会失败或被静默降级。

### `ask-gpt-files`（依赖更多，Windows 专属）

在 `ask-gpt` 的基础上，还需要：

4. 两个 Python 脚本 —— **已随本仓库提供**，位于 `ask-gpt-files/` 目录内：
   - `chatgpt_files_orchestrator.py`（orchestrator 路径，§A）
   - `file_picker_helper_v3.py`（MCP+helper 路径，§B）

   SKILL.md 里写死的路径是 `D:/桌面/ai-bridge/`。把这两个脚本放到该目录，或自行放别处后把 SKILL.md 里的路径改成你本地的实际路径。
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
├── ask-gpt-files/
│   ├── SKILL.md
│   ├── chatgpt_files_orchestrator.py
│   └── file_picker_helper_v3.py
├── ask-gpt-theory/
│   └── SKILL.md
└── claude-gpt-audit-pack/
    └── SKILL.md
```
