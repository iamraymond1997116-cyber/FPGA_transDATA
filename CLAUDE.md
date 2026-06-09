# CLAUDE.md

本文件为 Claude Code 操作此仓库的顶层指引。详细内容见下级文件。

## 一句话

FPGA 瞬态响应采集项目（Artix-7 XC7A200T），通过传感器上/下电瞬态信号提取 PUF 指纹。

## 架构全景

```
电源控制 → 传感器瞬态 → ADC 采集 → BRAM 存储 → UART 输出 → PC 解析
```

5 种采集模式（FULL / PCUT / NCUT / EXTR / FCYC）自动循环，每帧 128 点双通道。

## 核心操作

```powershell
.\.harness\tasks.ps1 check      # 环境 + lint + sim 全量检查
.\.harness\tasks.ps1 build      # Vivado 构建 bitstream
.\.harness\tasks.ps1 program    # JTAG 烧录 SRAM
.\.harness\tasks.ps1 capture    # UART 捕获
```

## 关键文件路径

| 用途 | 路径 |
|:---|:---|
| 主项目 CLAUDE.md | `PUF_dataTransFreq_v60_capture/CLAUDE.md` |
| 硬性约束规则 | `.harness/lessons.md` |
| OMC 调度规则 | `.harness/omc.md` |
| 会话启动引导 | `.harness/session_bootstrap.md` |
| 功能蓝图 | `.harness/feature_list.json` |
| 进度追踪 | `PUF_dataTransFreq_v60_capture/PROGRESS.md` |

## 约定

- RTL 改动必须先列改动点，等确认后再改
- 每次 RTL/脚本改动后出具 QA 报告到 `.harness/qa/`
- 详细模块说明、硬件 pinout、UART 帧格式见 `PUF_dataTransFreq_v60_capture/CLAUDE.md`
- 会话启动顺序：`init.ps1` → 读 PROGRESS.md → 读 lessons.md → `tasks.ps1 check`
