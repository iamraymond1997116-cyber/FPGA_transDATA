# FPGA_transDATA

## 通信规则

- **第一句话永远是"好的老大"，保持精简**
- **用简洁中文思考与交流，不废话不填充**

## 编码原则

- 需求不明确时先问，不猜
- 用最简单的改动满足需求，不建无用抽象
- 改精准，不改无关代码
- 可验证才叫完成，跑过才有结论
- 不确定时列出选项，不默默选

## 仓库结构

```
.harness/   — 工作流入口（tasks.ps1）
.claude/    — 配置
.omc/       — OMC 状态
AGENTS.md   — 路由规则

PUF_dataTransFreq_v60_capture/   ← 主项目
├── rtl/          — Verilog 源码
├── sim/          — 仿真
├── scripts/      — 构建/烧录/捕获
├── constraints/  — XDC
├── doc/          — 文档
└── logs/analysis/ — 分析结果

研究报告/   — 8 份报告
专利/       — 8 份专利
research_reports/ — 实验结果
```

## 会话启动

1. 跑 `.\.harness\init.ps1`（若 init 失败先修再继续）
2. 跑 `.\.harness\tasks.ps1 check`
3. 读 `PROGRESS.md`
4. 读 `.harness/lessons.md` + `.harness/omc.md`

## 常用命令

```powershell
.\.harness\tasks.ps1 check      # 环境+lint+sim
.\.harness\tasks.ps1 build      # 构建
.\.harness\tasks.ps1 program    # 烧录
.\.harness\tasks.ps1 capture    # 捕获
.\.harness\tasks.ps1 status     # 状态
.\.harness\tasks.ps1 clean      # 清理
```

## 规则

- RTL 改动先列点等确认，重大变更前必须问
- 探索、阻塞任务必须派子 agent，不污染主上下文
- 严格走 harness 流程，不跳步骤
- 文件路径用绝对路径
- 代码注释用英文
- 项目详情见 `PUF_dataTransFreq_v60_capture/CLAUDE.md`
- 多会话交接用 `.harness/session-handoff.md`
