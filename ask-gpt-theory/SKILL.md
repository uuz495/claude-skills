---
name: ask-gpt-theory
description: Multi-round protocol for building MATHEMATICAL THEORY by asking GPT, using the proven news_quant_research/rounds format. Each round = a folder with three files (prompt.md = the prompt Claude writes / answer.md = GPT's raw reply the user pastes in, marked STATUS: EMPTY/FILLED / summary.md = Claude's conclusions + what to ask next), all in ONE GPT session, drilling down top-down; each round's conclusions merge into a single SSOT design doc. Round 1 is BACKGROUND-ONLY (no packaged sub-questions, no own hypotheses); later rounds probe the vague / unjustified parts one cluster at a time. Every prompt asks for a DETAILED answer and insists on MATH THEORY (definitions / formulas / derivations / properties), NOT engineering implementation (no code / no build steps). This skill does NOT transport — the user carries prompts to GPT and pastes replies back. TRIGGER when the user wants to build / develop a theory or design with GPT over many rounds (e.g. "把这个理论问题打包给 GPT / 多轮问 GPT 构建这个理论 / 给 GPT 写理论提示词 / 用 rounds 那套问 GPT"). SKIP quick facts — just /ask-gpt.
metadata:
  short-description: Build math theory with GPT over many rounds — rounds/round_NN/{prompt,answer,summary} + SSOT doc, background-only round 1, math-theory-not-engineering, same session
---

# /ask-gpt-theory — 多轮向 GPT 构建数学理论（rounds 格式）

理论问题问 GPT，**不能一次把"完整问题"塞过去**。用经过验证的 **rounds 格式**（同 `news_quant_research/rounds/`）：每轮一个文件夹三件套，自顶向下逐轮下钻，每轮结论汇进一个 SSOT 设计文档。**只关心数学模型，不关心工程实现。**

这条 skill **不替 user 传**——发给 GPT、来回粘贴由 user 做。Claude 负责：写每轮 `prompt.md`、读 `answer.md`、写 `summary.md`、合并进 SSOT。

## 什么时候用

- **用**：开放式理论 / 设计 / 概念问题——逐轮把一个数学理论从框架钻到细节。
- **不用**：查事实、一次性 lookup → `/ask-gpt`。

## 每轮口径（所有轮都加）

不管第几轮，`prompt.md` 都带两句：
1. **要详细**——"请给我一份详细的 ……"，要深度、要展开推导。
2. **要数学理论、不要工程实现**——要定义 / 公式 / 推导 / 性质 / 文献依据；明说"不要代码、不要工程落地步骤"。

这是设深度 + 视角，不算"牵着证人走"。

## 目录格式

在目标 stage 文件夹下（如 `theory/recovery/`）：

```
<stage>/
├── <stage>_design.md         SSOT 设计文档（stub → 每轮结论合并进来；定稿后只看它）
└── rounds/
    └── round_NN_<topic>/
        ├── prompt.md         这一轮发 GPT 的提示词（Claude 写）
        ├── answer.md         GPT 原始回答（user 粘贴；开头标 STATUS: EMPTY / FILLED）
        └── summary.md        Claude 读完的结论 + 下一轮该问什么
```

`NN` 用两位编号：`01`、`02`、…、`10`。不要写成 `round_0(N+1)`，下一轮就是 `round_02`、`round_03` 这样递增。

全程在**同一个 GPT session** 里，上下文连续。rounds 是过程档案，定稿后只看 SSOT 设计文档。

## 文件模板

### `summary.md`（每轮至少这些分区）

```markdown
# Round NN Summary

## What GPT claimed
- ...

## Accepted into SSOT
- ...

## Plausible but unverified
- ...

## Rejected / inconsistent
- ...

## Gaps
- 定义 gap：
- 推导 gap：
- 参数/标定 gap：
- 边界/反例 gap：
- 文献/事实核验 gap：

## Next round focus
...
```

"采纳 vs 待验证 vs 否决"必须分清楚——别把首答整段糊进 SSOT。

### SSOT 设计文档骨架

```markdown
# <Stage> Design

## Problem statement
## User-given constraints
## Notation and definitions
## Assumptions
## Candidate model / theory
## Derivations and propositions
## Parameterization / calibration
## Edge cases and counterexamples
## Accepted conclusions by round
## Rejected ideas by round
## Open questions
## Verification notes / references
## Changelog
```

每次合并在 `Changelog` 写明来自哪轮，例如 `Round 03: accepted X under assumptions A1-A3; rejected Y because …`。文档里标清来源：哪条是 user 给定、哪条 Claude 推断、哪条 GPT 主张、哪条已验证、哪条待验证。

## 流程

### Round 1（背景）

1. Claude 建 `rounds/round_01_<topic>/`，写 **`prompt.md`** —— **只给背景**：领域/设定是什么、什么已定/已知、哪块空白、末尾一句开放邀请；带上"详细 + 数学理论不要工程实现"口径。**禁止**：自己的假设、倾向答案、编号子问题清单。可以要求 GPT 把回答组织清楚（按定义/候选形式化/关键假设/可推性质/失败点展开）——这种中性结构不是"想要的答案"，不算牵证人。建 **`answer.md`** 标 `STATUS: EMPTY`。
2. 凑 round-1 上下文附件：`python <theory>/audit_pack.py <stage>`（按 `<stage>/AUDIT.md` 把相关 .md 收到桌面，**每份单独**一个文件）。
3. 交付 user："把 `prompt.md` 当正文、桌面那几个 .md 当附件，发给 GPT（Pro + Extended，**同一会话**），把回答粘进 `answer.md`、STATUS 改 `FILLED`。"

### Round N（`answer.md` 变 FILLED 后）

4. Claude 读 `answer.md`，写 **`summary.md`**（按上面分区）：本轮采纳/待验证/否决 + 还剩哪些 gap（含糊/无推导/跳步/忽略约束/参数没说怎么定）+ 下一轮该问什么。把采纳内容**合并进 SSOT**，过质量门、写 Changelog。
5. 建 `round_0(N+1)_<topic>/`（即下一个两位编号），写 `prompt.md` —— **揪一簇 gap 追问**（"你说 X——为什么？推一下 / 什么假设 / 怎么处理 Y / 给显式形式"），纯文字、短，**同会话不再传附件**。建 `answer.md` STATUS: EMPTY。
6. user 发、粘回答 → 回到 4。**很多轮**（典型 5–15）直到每个 load-bearing 论断都被推导、参数有标定、没有"为什么/怎么"的洞。**别停在首答**。

每几轮跟 user 同步「已解决 vs 仍开放」。

### 质量门（合进 SSOT 前过一遍）

不要拿 GPT 首答当定稿。采纳前至少查：

- 符号定义清楚且前后一致。
- 关键命题有假设 + 推导，不是只给直觉。
- 参数、阈值、权重、先验、损失等说明了怎么定。
- 覆盖了边界 / 退化 / 反例 / 失败模式。
- 不跟 user 给定约束冲突。
- 区分"可证结论 / 建模选择 / 经验猜测 / 文献事实"。
- 文献和事实性引用需外部核验——别把 GPT 给的书目当已验证事实。

### Bridge prompt（换会话 / 上下文丢失时）

长理论构建会撑爆 GPT 会话窗口。一旦没法续同一会话，建 `round_NN_bridge/`，用 SSOT 摘要重建上下文，而不是盲目重传所有附件：

```markdown
We are continuing a multi-round theory-building discussion. Here is the current single-source-of-truth summary:

<compressed SSOT summary>

Do not restart from scratch. Continue from the following unresolved gap:
<gap>

Please answer in detail with definitions, formulas, derivations, assumptions, and failure modes. Focus on theory, not engineering implementation.
```

### 收口

满足大部分条件可收：问题/对象/符号已固定、核心假设明确、主模型有显式形式、关键性质有推导或反例边界、参数有标定策略、主要 failure modes 已列、剩余开放问题不阻碍成稿。

SSOT 设计文档定稿（stub 展开成完整设计），向 user 汇报：解决了什么、GPT 哪些采纳/否决、还剩什么开放。

## 为什么这样

- **别牵着证人走**：打包问题把 GPT 锁进你的分解、偏向你预期答案；只给背景，它才冒出你没想到的角度。
- **拷问 > 接受首答**：首答常"听着合理但手一挥"，价值在 follow-up 逼出推导/显式形式；质量门就是把这步可操作化。
- **很多轮 + 一条线**：理论清晰来自反复"为什么/怎么/推一下"，整段留在一个会话里滚上下文；真撑爆了用 bridge prompt 接，别硬扛。
- **rounds 三件套**：prompt/answer/summary 分清楚 + SSOT 合并，过程可追、定稿干净。

## 反面（别这么干）

- ❌ Round 1 甩编号子问题 + "请按以下格式输出"。
- ❌ Round 1 写进自己的假设 / 倾向答案。
- ❌ 拿首答就收工 / 把所有 gap 一口气倒给 GPT。
- ❌ 续问时重传附件 / 无谓新开会话——同一 session，附件只在 Round 1 传；真丢了上下文才用 bridge prompt。
- ❌ 让 GPT 给工程实现/代码——每轮口径都要把它拉回数学理论。
