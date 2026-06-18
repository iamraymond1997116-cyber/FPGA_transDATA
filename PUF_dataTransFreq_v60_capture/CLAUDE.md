# CLAUDE.md — PUF_dataTransFreq_v60_capture V6.5


## 项目概述

V6.5 多模式瞬态采集，传感器 PUF 指纹提取。
5 种采集模式：FULL / PCUT / NCUT / EXTR / FCYC，自动循环。
主链路：`sensor_power_control → transient_capture → capture_uart_streamer`

### 关键架构

- **顶层**：`rtl/transient_puf_v60_top.v` — V6.5，5 模式状态机 + sample_id/mode_idx
- **电源**：`rtl/sensor_power_control.v` — 5 模式电源时序
- **采集**：`rtl/transient_capture.v` — 128 点双通道
- **UART**：`rtl/capture_uart_streamer.v` — ASCII 帧，1 Mbps
- **ADC**：`rtl/ad7606_if.v` — AD7606 接口
- **LCD**：`rtl/lcd_version_mode_display.v` — 最小化状态显示

### UART 帧格式
```
V6.5,SID=00000,MID=0,FULL,SPWR=0,TXN=01\n
CH1,RAW,128,<128×4-hex>\n
CH2,RAW,128,<128×4-hex>\n
```

> **数据 & 采集文档**（`doc/数据采样/`）：
> - [DATA_FORMAT.md](doc/数据采样/DATA_FORMAT.md) — 字段/shape/命名规范（写分析代码读这里）
> - [CAPTURE_PROTOCOL.md](doc/数据采样/CAPTURE_PROTOCOL.md) — 采集流程、质量校验、黄金分析路径（采数据/分析数据读这里）

### 硬件规格
- FPGA：XC7A200T-2FBG484 (Artix-7)
- 开发板：ALINX AX7203 / AX7203B
- 系统时钟：200 MHz 差分 (LVDS_25)
- 传感器：惠斯通电桥压敏传感器，负载阻抗 9.5 kΩ
- ADC：AN706 (AD7606)，200kSPS，16 位有符号，±5V 双极性
- UART (CP2102)：N15(TXD)/P20(RXD)，1 Mbps/8N1
- LCD：AN430，480×272，RGB888
- 传感器电源：1=关，0=开 (PMOS 控制)
- LED1=错误，LED2=活跃，LED3/LED4=状态

## 会话启动

1. 读 `PROGRESS.md` — 当前状态和下一步
2. 读 `.harness/lessons.md` — 硬性约束
3. 读 `.harness/omc.md` — OMC 调度规则
4. 跑 `.\.harness\tasks.ps1 check` — 健康检查 (env + lint + sim)

## 常用命令

全部通过 `.\.harness\tasks.ps1 <cmd>`：
- `check` — env → lint → sim（完整健康检查）
- `build` — Vivado 完整构建 (~10-15 分钟)
- `program` — JTAG SRAM 烧录
- `capture -Port COM5` — UART 捕获
- `clean` — 清理生成文件

## 关键规则（完整列表见 .harness/lessons.md）

- RTL 改动：先列出改动点，等用户批准
- Build/capture/flash：委托子 agent，绝不阻塞
- 每次 RTL/脚本改动后必须出 QA 报告
- Vivado/Verilator 路径硬编码，不依赖 PATH
- 模块握手：显式两阶段 (req→ack→done)
- 仅限 Verilog-2001，RTL 中不用 SystemVerilog
- **TDD**：先写 tb → 跑 sim 看它挂 → 改 RTL → 跑 sim 看它过
