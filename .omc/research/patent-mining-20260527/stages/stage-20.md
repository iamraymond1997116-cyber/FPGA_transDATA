# Stage-20: 系统级专利点挖掘报告

> 分析范围: 完整 RTL 系统视角 (transient_puf_test_top.v + 子模块)
> 已有三件专利: 01_上下电瞬态响应 / 02_SCALE_SCH挑战扫描 / 03_多特征融合稳定比特量化
> 目标: 找出三件未覆盖的系统级创新点

---

## 核心发现: 4个高价值系统级专利点

---

### 专利点 A: 传感器身份认证全链路闭环系统

- **一句话描述**: 一种将"电源激励控制→ADC采集→FPGA预处理(FFT+峰值检测)→本地显示→UART输出→PC端认证"整合为全自动循环流水线的传感器物理身份认证系统，其中上下电双态采集、双通道处理和256挑战码扫描在单一状态机中按固定时序自动循环执行。

- **技术效果**: 实现无需人工干预的周期性身份采集与输出；上电/下电双态在一个完整循环内完成，确保ON/OFF特征的时间一致性；自动循环消除了人工触发带来的时序抖动；状态机内置3秒看门狗超时保护，故障自动回退IDLE。

- **证据文件**:
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v`: 主状态机 ST_IDLE→ST_POWER_CYCLE→ST_CAPTURE→ST_FFT_CH1→ST_FFT_CH2→ST_PEAK_DETECT→ST_DISPLAY→ST_WAIT_POWER_OFF→ST_CAPTURE_OFF→ST_FFT_OFF_CH1→ST_FFT_OFF_CH2→ST_PEAK_DETECT_OFF→ST_DISPLAY_OFF→ST_IDLE (line 1017-1482)
  - `PUF_dataTransFreq/rtl/sensor_power_control.v`: 受控上下电时序，POWER_OFF→POWER_ON→HOLD_ON→IDLE (line 16-98)
  - `PUF_dataTransFreq/rtl/transient_capture.v`: 256点采集+稳定点检测 (line 1-178)
  - `PUF_dataTransFreq/rtl/uart_feature_streamer.v`: 格式化UART输出，含txn_id、is_power_off、scale_sch_index等元数据 (line 1-1317)

- **与现有三件专利的关系**:
  - 专利01覆盖"上下电瞬态响应提取身份"的方法层面，但未覆盖"全链路自动循环流水线"的系统架构。
  - 专利02覆盖"SCALE_SCH挑战扫描"，但未覆盖"挑战码自动轮换+ON/OFF共用同一码字(advance_sch gating)"的硬件实现机制。
  - 专利03覆盖"多特征融合bit量化"，属于后处理算法。
  - **本专利点保护的是系统架构层面**: 将上述所有功能模块用单一状态机编排成全自动化流水线的工程实现。

- **需要补的实验**:
  - 自动循环 vs 人工触发的时序稳定性对比（循环周期抖动统计）
  - 完整循环时间测量（上电采集到下电采集到下一次上电的间隔）
  - 长时间连续运行（如1000次循环）的故障率和状态机超时触发率

- **新颖性风险**: 中等。自动采集系统在工业监测领域常见，但"专为传感器物理身份认证设计的、集成上下电双态+双通道+挑战扫描的全自动FPGA流水线"具有特定应用场景创新性。需强调身份认证目的和双态同步采集的时序耦合。

---

### 专利点 B: ON/OFF双态挑战码同步绑定机制

- **一句话描述**: 一种在传感器身份认证系统中使上电响应和下电响应共用同一挑战码字的硬件绑定方法，通过`advance_sch`门控信号控制挑战码仅在ON态递增、在OFF态保持，确保ON/OFF响应对在挑战维度上的严格对应关系。

- **技术效果**: 消除ON/OFF使用不同挑战码带来的特征空间错位；使ON/OFF联合特征在挑战维度上可直接对比和融合；减少挑战码搜索空间（256个ON/OFF对而非256×256组合）；为ON/OFF一致性校验提供硬件基础。

- **证据文件**:
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 548-549: `assign fft_advance_sch = !fft_is_power_off; // 1=ON(advance), 0=OFF(keep)`
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 591: `reg fft_is_power_off = 1'b0;`
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 1247: ON态 `fft_is_power_off <= 1'b0` (advance=1, SCH递增)
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 1373: OFF态 `fft_is_power_off <= 1'b1` (advance=0, SCH保持)
  - `PUF_dataTransFreq/rtl/fft_256.v` line 9: `advance_sch`输入端口定义
  - `PUF_dataTransFreq/rtl/fft_256.v` line 146-151: `if (advance_sch) scale_counter <= scale_counter + 1`

- **与现有三件专利的关系**:
  - 专利01提到"上电响应和下电响应共同参与身份判决"，但未涉及"挑战码绑定"机制。
  - 专利02提到"ON/OFF共challenge"概念（从属权利要求），但仅作为文字描述，未披露硬件实现细节。
  - **本专利点保护的是具体硬件机制**: `advance_sch`门控+`fft_is_power_off`状态寄存器的电路实现，以及ON/OFF在同一循环中挑战码同步绑定的时序设计。

- **需要补的实验**:
  - ON/OFF共用挑战码 vs 独立挑战码的认证准确率对比
  - 不同挑战码下ON/OFF响应的相关系数分布
  - 绑定机制对模板压缩率的影响（联合模板 vs 独立模板）

- **新颖性风险**: 较低。这是具体的电路实现创新，且V5.6版本才引入（`advance_sch` gate）。现有文献中未见将FFT配置挑战码与上下电状态绑定的硬件设计。

---

### 专利点 C: 带校准补偿的传感器瞬态身份采集系统

- **一句话描述**: 一种在传感器物理身份认证系统中集成两点电压校准（零点和参考点）的采集前端，通过q16.8定点增益系数对ADC原始数据进行校准后再送入身份特征提取链路的装置和方法。

- **技术效果**: 消除ADC零偏和增益漂移对身份特征稳定性的影响；校准后的频谱特征具有更高的类内一致性；使不同板卡/不同ADC通道之间的身份模板可迁移；为长期漂移补偿提供硬件基础。

- **证据文件**:
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 34-36: 校准参数定义 `CALIBRATION_GAIN_SHIFT=16`, `CALIBRATION_TARGET_100UV=25000`, `CALIBRATION_CHANNEL_MASK=8'b0000_0011`
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 859-998: 校准状态机（2'd0等待按键→2'd1采集→2'd2计算增益→2'd3完成）
  - `PUF_dataTransFreq/rtl/calibration_capture.v`: 1024点平均采集模块
  - `PUF_dataTransFreq/rtl/channel_voltage_calibration.v`: q16.8定点校准公式 `Vcal = (Vraw - Vzero) * gain >> 16`
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 447-461: CH1/CH2校准应用实例化

- **与现有三件专利的关系**:
  - 三件专利均未提及校准系统。专利01的从属权利要求提到"结合温度、压力、时间漂移数据"，但属于后处理补偿，非采集前端校准。
  - **本专利点是独立的系统级创新**: 将工业级ADC校准技术与传感器身份认证场景结合，解决"采集链路漂移导致身份特征不稳定"的问题。

- **需要补的实验**:
  - 校准前/后同一传感器的类内方差对比
  - 不同FPGA板卡（不同ADC零偏）上同一传感器的特征一致性
  - 校准后长时间漂移（如24小时）下的身份特征稳定性
  - 校准对认证准确率（FAR/FRR）的定量提升

- **新颖性风险**: 较低。ADC两点校准是通用技术，但"将ADC校准集成到传感器物理身份认证采集链中，并以校准后数据作为身份特征提取输入"的特定应用组合具有创新性。关键在于强调校准对身份特征稳定性的技术效果。

---

### 专利点 D: 状态机全生命周期调试与故障自恢复架构

- **一句话描述**: 一种在传感器身份认证FPGA系统中实现的状态机全生命周期监控架构，包括状态转移调试事件码、3秒超时看门狗、11类操作状态超时错误码、传感器电源控制调试事件码，以及通过UART将完整状态日志实时输出的机制。

- **技术效果**: 实现身份认证流水线的可观测性；任何状态卡死3秒内自动复位并输出错误码；传感器电源控制异常可被独立追踪；PC端可通过UART日志重建完整执行时序，便于故障定位和质量审计。

- **证据文件**:
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 179-183: debug_event信号定义
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 1015: `STATE_TIMEOUT_LIMIT = ONE_SECOND_COUNT * 3`
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 1153-1193: 状态超时看门狗+11类错误码
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 1157-1174: 14类状态转移调试事件码（4'd1~4'd14）
  - `PUF_dataTransFreq/rtl/sensor_power_control.v` line 13: `debug_event_code`输出
  - `PUF_dataTransFreq/rtl/sensor_power_control.v` line 55,64,72,83: 4类电源状态转移事件
  - `PUF_dataTransFreq/rtl/uart_feature_streamer.v` line 988-1006: STATE_LOG输出格式 `ST,X,Y,ZZ\n`
  - `PUF_dataTransFreq/rtl/transient_puf_test_top.v` line 1507-1512: error_led_controller实例化

- **与现有三件专利的关系**:
  - 三件专利均完全未涉及系统可靠性、可观测性和故障恢复。
  - **本专利点是纯系统级创新**: 不直接产生身份特征，但保障身份认证系统在工程部署中的可靠性和可维护性。
  - 可作为第一件主案的从属权利要求（"如权利要求X所述的系统，还包括..."），也可独立申请为"物理身份认证系统的可靠性架构"。

- **需要补的实验**:
  - 故意注入故障（如断开传感器电源线）后系统的超时恢复时间
  - 长时间运行中状态机超时触发频率统计
  - UART日志完整性与状态重建准确率
  - 错误码与实际问题的一一对应关系验证

- **新颖性风险**: 中等偏高。看门狗和状态调试是嵌入式通用技术，但"专为物理身份认证流水线设计的、覆盖14类状态转移+11类超时错误+4类电源事件的全生命周期监控"具有场景特定性。建议作为从属权利要求而非独立申请。

---

## 补充候选点（中低优先级）

| 候选点 | 描述 | 与三件专利的关系 | 建议 |
|:---|:---|:---|:---|
| 峰值历史缓冲区 | 16条目循环缓冲，LCD显示最近16次采集的峰值变化趋势 | 未覆盖 | 工程实用性强，但独立创造性偏弱，放入系统专利从属 |
| 双BRAM隔离存储 | ON/OFF频谱分别存储于独立BRAM，通过`fft_is_power_off`选择写入地址 | 未覆盖 | 属于ON/OFF绑定机制的实现细节，合并到专利B |
| 二进制UART帧协议 | A5 5A魔术字+版本+帧类型+txn_id+payload_len+SCH元数据+512字节频谱 | 未覆盖 | 通信协议层面，可作为系统专利从属 |
| 校准/运行模式LCD复用 | 同一LCD接口通过`calibration_active`信号切换校准显示和频谱显示 | 未覆盖 | 工程优化，创造性不足 |

---

## 总结与建议

| 优先级 | 专利点 | 建议定位 | 独立创造性 |
|:---:|:---|:---|:---:|
| **P0** | A: 全链路闭环系统 | **独立申请**或第一件主案的系统权利要求扩展 | 高 |
| **P1** | B: ON/OFF挑战码绑定 | **独立申请**或第二件的从属权利要求 | 中高 |
| **P1** | C: 校准补偿采集系统 | **独立申请**或第一件主案的从属 | 中 |
| **P2** | D: 状态机监控架构 | 第一件主案的从属权利要求 | 中 |

**关键策略**: 三件已有专利覆盖"方法"（怎么做身份提取），但缺少"系统"（用什么装置自动完成）。专利A填补了这个空白，将本项目从"算法方案"升级为"完整装置+系统"。专利B和C是具体硬件机制，可作为独立申请或并入主案的权利要求体系。

