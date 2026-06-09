# FPGA_transDATA

PUF 瞬态采集 V6.3。项目代码在 `PUF_dataTransFreq_v60_capture/`。

## 技术栈

| 层级 | 技术 |
|:---|:---|
| HDL | Verilog-2001 |
| 综合 | Vivado 2023.2 |
| FPGA | XC7A200T-2FBG484 |
| ADC | AN706 (AD7606)，200kSPS，16位 |
| LCD | AN430，480×272 |
| UART | 1 Mbps，8N1 |
| 仿真 | Verilator / Vivado xsim |
| 脚本 | PowerShell 5.1 / Tcl / Python |

## 工作流

1. 读 `PROGRESS.md` + `.harness/lessons.md`
2. RTL 改动先列点，等确认
3. 改完跑 `check` + QA → 授权 → build/program
4. 收工：git 提交 + 更新 PROGRESS.md

## 收工流程

1. git 提交核心改动，临时文件不提交
2. 更新 PROGRESS.md（当前任务、阻塞、下一步）
3. 如有纠正，更新 `.harness/lessons.md`
4. 跑 `tasks.ps1 check` 确认健康

## 规则来源

| 找什么 | 去哪找 |
|:---|:---|
| 常用命令、QA 流程 | `CLAUDE.md` |
| 硬性规则 | `.harness/lessons.md` |
| OMC 调度 | `.harness/omc.md` |
| 当前状态 | `PROGRESS.md` |
| 功能蓝图 | `.harness/feature_list.json` |
