# V6.0 交接说明

## 项目情况

当前项目是一个轻量版 V6.0 采集工程，目标不是做 FFT 或分类，而是先把串口抓数做对：
- `MODE=8` 和 `MODE=64`
- 128 点双通道 RAW 数据
- UART 1 Mbps
- LCD 只显示版本号和模式
- 串口输出必须是 ASCII，方便 PC 端直接校验

## 已完成

- `xvlog` 和 `xelab` 已能通过，说明 V6.0 RTL 静态结构是通的。
- `sensor_power_control` 已改成按真实写入样本数控制断电，不再按时钟计数。
- `mode_select` 已在每次 capture start 时锁存，避免采集中途切换模式。
- ASCII 串口解析脚本 `capture_ascii_v60.py` 已能正确解析 `V6.0,MODE=8|64,SPWR=...,TXN=..` 以及两路 128 点 RAW 行。

## 当前阻塞

- 完整 Vivado bitstream 还没有跑通。
- 我这边用当前工具链直接拉 `vivado.exe` / `vivado.bat` 时，命令链路没有稳定复现成功。
- 但你已经确认过：在 `MINGW64 (Git Bash)` 里直接执行  
  `"D:\Xilinx\Vivado\2023.2\bin\vivado.bat" -version`  
  是可以返回版本信息的。

## 下一步

1. 先用 Git Bash 这条已确认可用的链路跑完整 build：
   `D:\Xilinx\Vivado\2023.2\bin\vivado.bat -mode batch -source D:\Project\FPGA_DATAtransFreq_0514\PUF_dataTransFreq_v60_capture\scripts\build_v60.tcl`
2. 生成 `PUF_dataTransFreq_v60_capture\build\transient_puf_v60_top.bit`
3. 上板后用 `capture_ascii_v60.py` 从 `COM5` 抓 ASCII 串口数据
4. 检查每帧是否满足：
   - header 正确
   - `MODE` 是 `8` 或 `64`
   - `CH1/CH2` 各 128 点
   - 全部是 ASCII 不是二进制垃圾

## 备注

- 这次收尾最重要的经验已经写进 `doc/lessons_20260605.md`。
- 目前还不能算完成，必须等到真实串口抓数验证通过。
