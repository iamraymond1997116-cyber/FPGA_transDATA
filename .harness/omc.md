# OMC 项目扩展 — FPGA_transDATA V6.4

项目级 oh-my-claudecode 调度规则。

## 用户授权模式

每次用户提出具体需求后，主 agent 必须立即询问授权模式：

```
A. 手动确认 — 每步等你说"好"我才继续（默认）
B. 自主执行 — check/QA/build 自动推进，关键节点汇报 (/yolo)
C. 完全自主 — /ralph，循环迭代直到完成或出错
```

| 模式 | check | QA | build | program | capture |
|:---|:---|:---|:---|:---|:---|
| A 手动 | 等确认 | 等确认 | 等确认 | 等确认 | 等确认 |
| B 自主 | 自动 | 自动 | 自动 | 等确认 | 等确认 |
| C 完全 | 自动 | 自动 | 自动 | 自动 | 自动 |

## QA 流程

RTL/脚本改动完成后：
1. 跑 `.\.harness\tasks.ps1 check` 全绿
2. 派 `code-reviewer` 做 RTL 审查 + `verifier` 收集证据
3. 填 QA 报告到 `.harness/qa/QA_REPORT_<日期>_<topic>.md`
4. 呈递用户确认 → 授权后才允许 build/program

## 子 agent 委派规则

### 小任务（直接做）

小任务自己做，不派子 agent：
- 改 1-2 行代码
- 读 <50 行文件
- 跑单个命令
- 查简单事实

### 阻塞/长任务（必须派子 agent）

| 任务 | 子 agent | 方式 |
|:---|:---|:---|
| build (>10 min) | executor | 后台 |
| program | executor | 后台 |
| 大文件分析 (>400 行 RTL) | explore | 前台 |
| 跨文件搜索 | explore | 前台 |
| 三重审查 (B/C 模式) | code-reviewer + verifier + critic | 并行 |

### 规则

- 一代理一任务
- 后台任务用 `run_in_background`
- 等待期间做其他独立工作（不能干等）
- 返回摘要，不要原始输出全文
