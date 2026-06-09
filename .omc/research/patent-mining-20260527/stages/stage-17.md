# Stage-17: FPGA资源优化策略专利挖掘报告

> 分析日期: 2026-05-27
> 分析范围: PUF_dataTransFreq/rtl/transient_puf_test_top.v, fft_256.v, constraints/transient_puf_test.xdc, build/timing_summary.rpt, build/utilization.rpt
> 已有专利族: 01_上下电瞬态响应传感器身份提取, 02_SCALE_SCH挑战扫描响应图谱生成, 03_多特征融合稳定比特量化

---

## 一、RTL关键资源特征提取

### 1.1 BRAM组织

| BRAM实例 | 深度 | 位宽 | 用途 | 备注 |
|:---|:---|:---|:---|:---|
| capture_bram_ch1 | 256 | 16-bit | 采集缓存 | 双通道共享写端口，单读端口 |
| capture_bram_ch2 | 256 | 16-bit | 采集缓存 | 同上 |
| fft_bram_ch1 | 128 | 32-bit | FFT结果(ON) | 仅存储半谱(0-Fs/2) |
| fft_bram_ch2 | 128 | 32-bit | FFT结果(ON) | 同上 |
| off_fft_bram_ch1 | 128 | 32-bit | FFT结果(OFF) | 与ON结果分离存储 |
| off_fft_bram_ch2 | 128 | 32-bit | FFT结果(OFF) | 与ON结果分离存储 |

**关键发现**: 实际综合后仅使用 **4个RAMB18E1** (0.55%可用BRAM)，说明大量存储被推断为分布式RAM(LUTRAM)。

### 1.2 状态机架构

主状态机 14 个状态，覆盖完整流程:
```
CALIBRATION -> IDLE -> POWER_CYCLE -> CAPTURE -> FFT_CH1 -> FFT_CH2 -> PEAK_DETECT -> DISPLAY
  -> WAIT_POWER_OFF -> CAPTURE_OFF -> FFT_OFF_CH1 -> FFT_OFF_CH2 -> PEAK_DETECT_OFF -> DISPLAY_OFF -> IDLE
```

- 单一时钟域: pixel_clk (9.09MHz, 由200MHz分频/22)
- 200MHz仅用于IBUFDS输入和时钟分频
- 所有数据处理在9.09MHz下完成

### 1.3 FFT配置

| 参数 | 值 | 说明 |
|:---|:---|:---|
| FFT点数 | 256 | Xilinx FFT v9.1 Pipelined Streaming I/O |
| 输出bin | 128 | 仅保留0~Fs/2半谱 |
| 输入位宽 | 16-bit | 有符号定点 |
| 输出位宽 | 32-bit | 幅度平方(实部^2+虚部^2) |
| SCALE_SCH | 8-bit计数器 | 256值自动轮换 |
| advance_sch | 1-bit门控 | ON时递增，OFF时保持 |

### 1.4 时序与资源报告

**时序** (build/timing_summary.rpt):
- sys_clk_200m: WNS=3.255ns, 满足5ns周期要求
- pixel_clk: WNS=85.289ns, 大幅满足110ns周期要求
- 跨时钟域: pixel_clk->sys_clk_200m WNS=3.217ns

**资源利用率** (build/utilization.rpt):
- Slice LUTs: 18,020 / 133,800 (13.47%)
- Slice Registers: 21,978 / 269,200 (8.16%)
- Block RAM: 4 RAMB18E1 / 730 (0.55%)
- DSP48E1: 46 / 740 (6.22%)
- 分布式RAM: 1,118 LUT + 867 SRL16E

---

## 二、专利点挖掘

### 专利点1: BRAM分时复用与ON/OFF状态共享缓存架构

- **一句话描述**: 在单一时钟域下，通过状态机时序控制使同一组BRAM在传感器上电采集阶段和下电采集阶段分别缓存数据，配合FFT结果BRAM的ON/OFF分离存储，实现双态身份特征提取的最小BRAM占用。

- **技术效果**: 
  - 采集BRAM仅需256x16x2 = 8,192 bit，即可支持上下电两次256点采集
  - FFT结果BRAM通过`fft_is_power_off`标志分时写入ON/OFF两组128x32存储
  - 相比独立双份存储，BRAM用量减少约50%
  - 实际综合仅消耗4个RAMB18E1(0.55%)，剩余BRAM资源可用于扩展

- **证据文件**:
  - `transient_puf_test_top.v` L493-504: capture_bram_ch1/ch2声明与读写
  - `transient_puf_test_top.v` L584-605: fft_bram/off_fft_bram声明与`fft_is_power_off`门控写入
  - `transient_puf_test_top.v` L1246-1247, L1372-1373: 状态机设置`fft_is_power_off`标志
  - `utilization.rpt`: Block RAM Tile仅2个(4 RAMB18E1)

- **与现有三件专利的关系**:
  - 01_上下电瞬态响应: 可作为从属权利要求，强调"上下电共享缓存的最小资源实现"
  - 02_SCALE_SCH挑战扫描: 独立，但可结合——在共享缓存架构上实现256次挑战扫描
  - 03_多特征融合: 弱相关

- **需要补的实验**:
  - 证明BRAM分时复用不会引入数据污染(上下电数据隔离性)
  - 量化BRAM节省带来的功耗/面积收益
  - 对比独立双份存储与共享存储的认证准确率差异

- **新颖性风险**: **中低**
  - FPGA BRAM分时复用是通用技术，但"传感器上下电双态身份认证场景下的BRAM共享缓存"未见专门报道
  - 需强调与传感器瞬态PUF的特定结合，而非泛泛的BRAM TDM

---

### 专利点2: 定点FFT+SCALE_SCH轮换的低成本挑战扫描实现

- **一句话描述**: 在资源受限FPGA上，利用定点FFT IP的SCALE_SCH配置参数作为8-bit挑战输入，通过单一计数器自动轮换256个挑战码字，配合`advance_sch`门控实现ON/OFF同挑战码字采集，以最小逻辑开销生成传感器瞬态响应的多视角频谱图谱。

- **技术效果**:
  - 仅需8-bit计数器+组合映射逻辑即可生成256个SCALE_SCH配置
  - `advance_sch`门控使ON/OFF共用同一挑战码字，保证双态可比性
  - 定点运算避免浮点IP的高资源消耗(无浮点DSP占用)
  - 单次挑战扫描周期~50ms(fast scan)，256次完整扫描~12.8s
  - 实际仅使用46个DSP48E1(6.22%)，主要为FFT IP内部乘法器

- **证据文件**:
  - `fft_256.v` L36-42: 8-bit SCALE_SCH计数器与4组映射
  - `fft_256.v` L146-151: `advance_sch`门控逻辑
  - `transient_puf_test_top.v` L544-549: `advance_sch`信号连接
  - `transient_puf_test_top.v` L1219: fast scan模式50ms周期

- **与现有三件专利的关系**:
  - 02_SCALE_SCH挑战扫描: **核心重叠**——该专利点应作为02的**从属权利要求**或**实施例细化**
  - 01_上下电瞬态响应: 可作为从属，强调"低成本挑战扫描增强上下电特征区分度"
  - 03_多特征融合: 弱相关

- **需要补的实验**:
  - 256个SCALE_SCH码字中筛选最优子集的算法和结果
  - 不同挑战数量下的认证性能曲线(ROC/AUC)
  - 与单一FFT配置相比，挑战扫描是否显著提升类间分离度
  - 定点FFT vs 浮点FFT在特征区分度上的差距(如有)

- **新颖性风险**: **中**
  - SCALE_SCH是Xilinx FFT IP的标准配置参数，主张参数本身新颖不可行
  - 但"将SCALE_SCH作为挑战参数用于传感器瞬态身份图谱生成"的特定应用场景具有创造性空间
  - 关键在于权利要求写法：不主张参数新颖，而主张"定点非线性观测配置作为挑战输入的传感器身份图谱生成方法"

---

### 专利点3: 单状态机统一控制采集-FFT-显示-UART全流程的低功耗架构

- **一句话描述**: 使用单一14状态主状态机在9.09MHz低时钟域下统一控制传感器电源时序、ADC采集、双通道FFT处理、峰值检测、LCD显示和UART数据输出，通过200MHz仅用于时钟输入分频，实现数据处理全链路的低动态功耗运行。

- **技术效果**:
  - 单一时钟域消除跨时钟域同步开销和亚稳态风险
  - 9.09MHz像素时钟下所有数据处理(FFT、峰值检测、UART、LCD)同步完成
  - 200MHz仅驱动IBUFDS和分频器，动态功耗集中在低频域
  - 状态机内置3秒超时看门狗，异常状态自动复位
  - 自动触发周期：fast scan~50ms，正常模式~2s

- **证据文件**:
  - `transient_puf_test_top.v` L1006-1482: 主状态机完整实现
  - `transient_puf_test_top.v` L1153-1193: 状态超时看门狗
  - `transient_puf_test_top.v` L336-351: 200MHz->9.09MHz分频
  - `constraints/transient_puf_test.xdc` L108-109: 时钟约束
  - `timing_summary.rpt`: pixel_clk WNS=85.289ns(大幅松弛)

- **与现有三件专利的关系**:
  - 01_上下电瞬态响应: 可作为从属权利要求，强调"低功耗单时钟域状态机控制"
  - 02/03: 弱相关

- **需要补的实验**:
  - 功耗测量：9.09MHz域 vs 200MHz全速运行的动态功耗对比
  - 证明单时钟域设计在资源/功耗上优于多时钟域方案
  - 状态机超时机制的有效性验证(异常注入测试)

- **新颖性风险**: **中高**
  - 单状态机控制多模块是FPGA设计常规做法
  - 低功耗通过降频实现也是通用手段
  - 创造性在于"传感器身份认证全链路"的特定组合，需强调与传感器瞬态PUF的绑定

---

### 专利点4: 200MHz系统时钟下的时序裕量利用与扩展空间

- **一句话描述**: 在Artix-7 FPGA上，200MHz系统时钟经22分频得到9.09MHz数据处理时钟，时序报告表明pixel_clk域具有85ns+的极大建立时间裕量，该裕量可用于未来功能扩展(更高采样率、更多FFT点数、额外挑战参数)而不需更换FPGA器件。

- **技术效果**:
  - pixel_clk WNS=85.289ns，意味着时钟可提升至~18MHz仍有裕量
  - sys_clk_200m WNS=3.255ns，200MHz稳定运行
  - 当前设计仅使用13.47% LUT、8.16% FF、0.55% BRAM、6.22% DSP
  - 资源余量支持：512点FFT、更多通道、更复杂特征提取

- **证据文件**:
  - `timing_summary.rpt`: WNS=85.289ns(pixel_clk), WNS=3.255ns(sys_clk_200m)
  - `utilization.rpt`: 各资源利用率数据
  - `transient_puf_test_top.v` L346-351: 分频器参数HALF_DIVIDE=11

- **与现有三件专利的关系**:
  - 可作为三件专利共同的**从属权利要求**，强调"在资源受限FPGA上的可扩展实现"
  - 特别适合支撑"低成本/低功耗架构"的主张

- **需要补的实验**:
  - 实际功耗测量报告(静态/动态)
  - 资源扩展模拟：512点FFT、4通道、更多挑战参数的资源预估
  - 温度/电压变化下的时序裕量保持性

- **新颖性风险**: **高**
  - 时序裕量和资源利用率是设计结果，本身不构成发明
  - 仅适合作为专利的**辅助证据**，证明技术方案的可扩展性和工程可行性
  - 不建议作为独立专利点

---

### 专利点5: 在资源受限FPGA上实现传感器身份认证的低功耗/低成本架构(综合专利点)

- **一句话描述**: 一种在低成本Artix-7 FPGA上实现传感器物理身份认证的系统架构，通过BRAM分时复用、定点FFT挑战扫描、单时钟域状态机统一控制和200MHz/9.09MHz双频时钟设计，在仅消耗~13% LUT、~8% FF、~0.5% BRAM、~6% DSP的条件下完成双通道256点采集、FFT变换、峰值检测、LCD显示和UART回传的全流程。

- **技术效果**:
  - 总资源占用极低，同一FPGA可同时支持多传感器或扩展功能
  - 低时钟域运行降低动态功耗，适合电池供电或能量采集场景
  - 无需外部处理器，纯FPGA端完成采集到特征输出
  - 模块化设计：电源控制、采集、FFT、峰值检测、UART、LCD各模块可独立替换

- **证据文件**:
  - 全部RTL文件 + utilization.rpt + timing_summary.rpt
  - `transient_puf_test_top.v`: 顶层模块实例化所有子模块
  - `sensor_power_control.v`: 电源时序控制(~5ms断电/50ms保持)
  - `transient_capture.v`: 256点采集+稳定点检测

- **与现有三件专利的关系**:
  - 可作为**01主案的强从属权利要求**，强调"资源受限FPGA上的低成本实现"
  - 也可作为**独立专利点**——如果检索证明"传感器身份认证的FPGA低资源实现"未被专门覆盖

- **需要补的实验**:
  - 完整功耗报告(静态电流、动态电流、各模块占比)
  - 与MCU+ADC方案的对比(成本、功耗、性能)
  - 多传感器并行认证的扩展性验证
  - 与其他FPGA平台(Spartan-7、Cyclone V)的移植验证

- **新颖性风险**: **中**
  - 资源受限FPGA上的信号处理是成熟领域
  - 但"传感器物理身份认证"这一特定应用在FPGA上的低资源实现方案未见专门报道
  - 关键在于强调"身份认证"而非"信号处理"的应用场景差异

---

## 三、风险评估矩阵

| 专利点 | 新颖性风险 | 创造性风险 | 与现有三案关系 | 建议处理 |
|:---|:---:|:---:|:---|:---|
| 1. BRAM分时复用 | 中低 | 中 | 01从属 | 并入01主案从属权利要求 |
| 2. 定点FFT+SCALE_SCH低成本实现 | 中 | 中 | 02核心重叠 | 并入02案，细化实施例 |
| 3. 单状态机统一控制低功耗架构 | 中高 | 中高 | 01从属 | 并入01从属，或暂缓 |
| 4. 时序裕量与扩展空间 | 高 | 高 | 三案辅助 | 不作为独立专利点 |
| 5. 综合低功耗/低成本架构 | 中 | 中 | 01强从属/独立 | 视检索结果决定是否独立申请 |

---

## 四、建议行动

1. **短期(2周内)**:
   - 将专利点1和专利点3作为01主案的从属权利要求补充
   - 将专利点2作为02案的核心实施例细化
   - 专利点4仅作为技术效果证据，不主张权利

2. **中期(1个月内)**:
   - 补充功耗测量实验(专利点5的关键证据)
   - 做BRAM分时复用的数据隔离性验证
   - 检索"sensor authentication FPGA low resource"专利，评估专利点5独立申请可行性

3. **长期(专利申请前)**:
   - 若专利点5检索结果有利，考虑作为第四件专利独立申请
   - 否则全部并入01/02案作为从属权利要求

---

## 五、外部检索参考

- [US 11,671,100 B2](https://faculty.eng.ufl.edu/swarup/wp-content/uploads/sites/689/2026/02/US-11671100-B2-Patent-Public-Search-_-USPTO.pdf) - FPGA PUF (2023)
- [Sensors 2024, 24, 7747](https://www.mdpi.com/1424-8220/24/23/7747) - RO-Based PUF on FPGA for Sensor Authentication
- [Electronics 2025, 14, 1415](https://www.mdpi.com/2079-9292/14/19/3894) - FPGA in Network Security Survey
- [CN113626756A](https://eureka.patsnap.com/patent-CN113626756A) - Fixed-point FFT quantization by neural network (2021)

---

*报告生成: 2026-05-27 | 基于 RTL v5.7, Vivado 2023.2, Artix-7 xc7a200tfbg484-2*
