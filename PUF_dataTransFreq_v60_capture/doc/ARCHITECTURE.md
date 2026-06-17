# 架构概述

## 数据流

```
sensor_power_control  →  transient_capture  →  capture_uart_streamer
      │                        │                      │
      │ 电源时序               │ 128 点双通道采集     │ UART ASCII 帧输出
      │ 5 模式                  │ BRAM 存储            │ 1 Mbps
      ▼                        ▼                      ▼
  传感器上/下电           CH1/CH2 数据            PC 端解析
```

## 5 采集模式

| 模式 | 行为 | 用途 |
|:---|:---|:---|
| FULL | ON@0, OFF@64 | 全窗口 |
| PCUT | ON@0, OFF@8 | 正脉冲截断 |
| NCUT | OFF@0, ON@9 | 负脉冲截断 |
| EXTR | ON(8)/OFF(9) 交替 | 极值循环 |
| FCYC | ON→OFF@32, ON@64, OFF@96 | 全周期开关 |

## UART 帧格式

```
V6.5,SID=00000,MID=0,FULL,SPWR=0,TXN=01\n
CH1,RAW,128,<128×4-hex>\n
CH2,RAW,128,<128×4-hex>\n
说明：SID 是 sample_id，5 个模式 FULL/PCUT/NCUT/EXTR/FCYC 共享同一个 SID；MID 是 sample 内模式索引 0..4。

```

## 模块清单

| 模块 | 文件 | 功能 |
|:---|:---|:---|
| Top | `transient_puf_v60_top.v` | 顶层状态机，5 模式自动循环，V6.5 sample_id/mode_idx 分组 |
| Power | `sensor_power_control.v` | 5 模式电源时序控制 |
| Capture | `transient_capture.v` | 128 点双通道采集控制 |
| UART | `capture_uart_streamer.v` | ASCII 帧组包+发送 |
| UART TX | `uart_tx.v` | 1Mbps UART 发送器 |
| ADC | `ad7606_if.v` | AD7606 接口 |
| LCD | `lcd_version_mode_display.v` | 版本+模式显示 |
| Clock | `pixel_clock_divider.v` | 200M→像素时钟分频 |
| Debounce | `button_debounce.v` | 按键消抖 |
