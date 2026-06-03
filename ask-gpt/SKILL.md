---
name: ask-gpt
description: Send a question to GPT-5.5 Pro (Extended thinking) via the ChatGPT web tab and return the reply inline. Use when the user types /ask-gpt or wants GPT's strongest reasoning to answer a hard question.
metadata:
  short-description: Ask GPT-5.5 Pro Extended via ChatGPT web
---

# /ask-gpt — query ChatGPT GPT-5.5 Pro (Extended thinking)

调用方式：`/ask-gpt <问题>`

无参数。模型固定 **GPT-5.5 Pro + Extended thinking**（最强档）。

回答全文 inline 返回给用户，不写文件。

---

## 前置：先用 ToolSearch 加载 chrome MCP 工具

一次性加载（已加载就跳过）：

```
ToolSearch select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__computer
```

---

## 完整流程（按步骤跑，不要省略）

### 步骤 1：找/开 chatgpt.com tab

调 `tabs_context_mcp`。规则：
- 已有 `https://chatgpt.com/...` 的 tab → 复用其 tabId（避免每次开新 tab 影响登录态）
- 没有 → `tabs_create_mcp` 拿新 tabId，再 `navigate` 到 `https://chatgpt.com/`，等 2 秒

把 tabId 记成 `$TAB`。

### 步骤 2：确保模型 = Pro，思考档 = Extended

用一条 `javascript_tool` 调用完成（带容错），打开 model picker → 进 Configure → 选 Pro → 把 thinking-effort combobox 切到 Extended → 关 modal。已经是这套配置则什么都不做。

```javascript
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 当前 chip 已显示 Pro 就跳过重设，但仍然进 Configure 确认 Extended
  document.querySelector('[data-testid="model-switcher-dropdown-button"]').click();
  await sleep(500);
  const cfg = document.querySelector('[data-testid="model-configure-modal"]');
  if (!cfg) return {error: 'Configure entry not found'};
  cfg.click();
  await sleep(1500);

  const modal = document.querySelector('[role="dialog"]');
  if (!modal) return {error: 'modal not opened'};

  // 选 Pro radio
  const radios = [...modal.querySelectorAll('[role="radio"]')];
  const proRadio = radios.find(r => /^Pro/.test(r.textContent.trim()));
  if (proRadio && proRadio.getAttribute('aria-checked') !== 'true') {
    proRadio.click();
    await sleep(400);
  }

  // 切 thinking-effort combobox 到 Extended
  const combos = [...modal.querySelectorAll('[role="combobox"]')];
  const thinkingCombo = combos.find(c => /Standard|Extended|Light|Heavy/.test(c.textContent));
  if (thinkingCombo && !/Extended/.test(thinkingCombo.textContent)) {
    thinkingCombo.click();
    await sleep(500);
    const lb = document.querySelector('[role="listbox"]');
    const ext = lb ? [...lb.querySelectorAll('[role="option"]')].find(o => /Extended/.test(o.textContent)) : null;
    if (ext) {
      ext.click();
      await sleep(400);
    }
  }

  // 关 modal
  document.querySelector('[data-testid="close-button"]')?.click();
  await sleep(400);

  return {
    ok: true,
    proSelected: proRadio?.getAttribute('aria-checked') === 'true' || /^Pro/.test(proRadio?.textContent || ''),
    thinking: thinkingCombo?.textContent.trim(),
  };
})()
```

返回 `{ok: true, ...}` 即可继续。如果有 error，截图 `computer screenshot` 给用户看，然后 abort。

### 步骤 3：写入 prompt 到 ProseMirror（关键 — 必须用 execCommand）

**不要用 `computer.type`**（中文 IME 会丢字）。
**不要用 `editor.innerHTML = '...'`**（ProseMirror EditorState 不会同步，结果是 send 出去 payload 是空的，服务端永远卡 thinking 状态）。

**唯一可靠的方法：`document.execCommand('insertText')`**——它派发 `beforeinput` 事件，ProseMirror 内部会 dispatchTransaction 同步 EditorState。

```javascript
((PROMPT_TEXT) => {
  const editor = document.querySelector('#prompt-textarea');
  if (!editor) return {error: 'composer not found'};
  editor.focus();
  // 清空旧内容（如有）
  document.execCommand('selectAll', false, undefined);
  document.execCommand('delete', false, undefined);
  // 插入新内容（ProseMirror 通过 beforeinput 事件接收）
  document.execCommand('insertText', false, PROMPT_TEXT);
  return {ok: true, editorText: editor.textContent.slice(0,80)};
})(`<把用户问题插进来，注意转义反引号和 \\>`)
```

把用户原始问题作为字符串字面量插进去。**记得**对反引号、反斜杠、`${}` 做转义；如果问题里有大量代码 / 特殊字符，改用 base64：

```javascript
((B64) => {
  const PROMPT_TEXT = decodeURIComponent(escape(atob(B64)));
  const editor = document.querySelector('#prompt-textarea');
  editor.focus();
  document.execCommand('selectAll', false, undefined);
  document.execCommand('delete', false, undefined);
  document.execCommand('insertText', false, PROMPT_TEXT);
  return {ok: true, len: editor.textContent.length};
})('<base64 编码的 prompt>')
```

**验证 send 是否成功的标志：**
- 步骤 4 点 send 后 5 秒内 URL 应从 `chatgpt.com/` 切到 `chatgpt.com/c/<uuid>`
- 如果一直停在 `chatgpt.com/`、`stop-button` 又一直在但没 token 输出 → 说明 ProseMirror state 没同步，payload 是空的，废 chat。刷新重发。

### 步骤 4：点 Send

```javascript
(() => {
  const btn = document.querySelector('[data-testid="send-button"]');
  if (!btn) return {error: 'send button not found'};
  if (btn.disabled) return {error: 'send button disabled (prompt empty?)'};
  btn.click();
  return {ok: true};
})()
```

### 步骤 5：轮询直到生成结束

GPT-5.5 Pro Extended 思考时间：**简单问题 1-3 分钟，复杂问题 10-20 分钟起步**（数学证明、代码审查、架构问题等）。

**每 1 分钟检查一次**——查得太勤浪费工具调用，反正 Pro 思考时间短不了。

`computer.wait` 单次最大 10 秒，所以一个轮询周期 = **6 次 `wait duration=10` + 1 次 `javascript_tool` 检查**。

```javascript
(() => ({
  streaming: !!document.querySelector('[data-testid="stop-button"]'),
  assistantCount: document.querySelectorAll('[data-message-author-role="assistant"]').length,
}))()
```

最多轮询 **20 次（20 分钟）**，超时再问用户是否继续等。

stop button 消失 → 生成结束 → 进步骤 6。

### 步骤 6：抓最后一条 assistant message 文本

**用 `textContent`，不要用 `innerText`**。Pro 模式回答区某些 CSS 会让 `innerText` 返回空字符串，`textContent` 才是可靠的。

```javascript
(() => {
  const msgs = [...document.querySelectorAll('[data-message-author-role="assistant"]')];
  const last = msgs[msgs.length - 1];
  if (!last) return {error: 'no assistant message'};
  const md = last.querySelector('.markdown') || last;
  // textContent 拿全文（含代码块 / 列表的纯文本）
  // innerText 拿带换行格式版本（但 Pro 模式可能为空）
  return {
    ok: true,
    text: md.textContent,
    text_innerText: md.innerText,  // fallback debug
    html_len: md.innerHTML.length,
  };
})()
```

**优先用 `text` 字段**。如果 `text` 包含代码块需要保留 markdown 格式，再用 `innerHTML` 做后处理。

### 步骤 7：把 `text` 直接 inline 输出给用户

格式建议：

```
GPT-5.5 Pro (Extended) 回答：

<text 全文>
```

**不要**做摘要，**不要**裁剪。用户明确要求全文 inline。

---

## 失败处理

| 失败点 | 兜底 |
|--------|------|
| 步骤 1 找不到 ChatGPT tab + 网络打不开 | 截图给用户，提示去登录 chatgpt.com |
| 步骤 2 modal 打不开 / Pro radio 缺失 | UI 改了，截图 + 报告 selector miss |
| 步骤 3 composer 拿不到 | 截图 + abort |
| 步骤 5 超时（>5 min） | 给用户当前 partial 回答 + 提示可手动等 |
| 步骤 6 没 assistant message | 截图 + 报告 |

---

## 不要做的事

- 不要写文件，不要 truncate，不要摘要
- 不要再问 "要不要更深思考"——已经是最强档
- 不要走 ai-bridge MCP（那是给 Codex/Gemini 用的）
- 不要复用旧对话，每次新 chat（直接 navigate `chatgpt.com/`）即可
