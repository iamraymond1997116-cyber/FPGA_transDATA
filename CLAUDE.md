# CLAUDE.md

本文件为 Claude Code 操作此仓库的顶层指引。详细内容见下级文件。

## 一句话

FPGA 瞬态响应 PUF 身份识别项目（Artix-7 XC7A200T V6.4）：通过采集传感器上/下电瞬态信号提取不可克隆指纹，配以 Python 数据分析流水线和专利挖掘工作区。

## 架构全景

```
硬件采集层:  电源控制 → 传感器瞬态 → ADC → BRAM → UART → PC
分析层:      logs/analysis/ 对比学习 + 识别率验证 + SCH 优化
知识产权层:  专利/ 8 个候选方案 + 研究报告/ 多维度分析
```

5 种采集模式（FULL / PCUT / NCUT / EXTR / FCYC）自动循环，每帧 128 点双通道。

## 核心操作

```powershell
.\.harness\tasks.ps1 check      # 环境 + lint + sim 全量检查
.\.harness\tasks.ps1 build      # Vivado 构建 bitstream
.\.harness\tasks.ps1 program    # JTAG 烧录 SRAM
.\.harness\tasks.ps1 capture    # UART 捕获
```

数据分析（在 `PUF_dataTransFreq_v60_capture/logs/analysis/`）：
```powershell
python scripts\capture_ascii_v60.py --port COM5   # UART 捕获与解析
python logs\analysis\contrastive_learning.py       # 对比学习可视化
python logs\analysis\identify_analysis.py          # KNN/RF 识别率分析
```

## 关键文件路径

| 用途 | 路径 |
|:---|:---|
| FPGA 采集项目 | `PUF_dataTransFreq_v60_capture/` |
| 子项目 CLAUDE.md | `PUF_dataTransFreq_v60_capture/CLAUDE.md` |
| 硬性约束规则 | `.harness/lessons.md` |
| OMC 调度规则 | `.harness/omc.md` |
| 功能说明 | `PUF_dataTransFreq_v60_capture/doc/功能说明.md` |
| 架构文档 | `PUF_dataTransFreq_v60_capture/doc/ARCHITECTURE.md` |
| 数据分析报告 | `研究报告/`（对比学习、SCH 优选、UART 评估等） |
| 专利草案 | `专利/`（8 个候选方案大纲 + 交底书） |

## 约定

- RTL 改动必须先列改动点，等确认后再改
- 每次 RTL/脚本改动后出具 QA 报告到 `.harness/qa/`
- 详细模块说明、硬件 pinout、UART 帧格式见子项目 CLAUDE.md
- 会话启动顺序：`init.ps1` → PROGRESS.md → lessons.md → `tasks.ps1 check`
- 分析方法开发参照 `研究报告/` 中的可复现报告（含 .py 和 report.md）
