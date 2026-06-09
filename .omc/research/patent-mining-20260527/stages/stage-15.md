# Stage-15: 数据完整性校验方法专利挖掘报告

> 扫描日期: 2026-05-27
> 扫描文件:
> - `rtl/uart_feature_streamer.v` — UART帧结构与传输协议
> - `rtl/transient_puf_test_top.v` — 顶层状态机与UART请求队列
> - `rtl/fft_256.v` — SCALE_SCH自动轮换与advance_sch门控
> - `scripts/check_capture_integrity.py` — CSV完整性检查
> - `scripts/verify_uart_format.py` — UART格式数值验证
> - `scripts/capture_binary.py` — 二进制帧捕获与resync
> - `scripts/capture_sensor.py` — 带SCALE_SCH追踪的采集
> - `scripts/capture_uart.ps1` — PowerShell UART捕获（前缀过滤）
> - `scripts/analyze_500_baseline_and_drift.py` — 基线分析中的完整性检测
> - `PROGRESS.md` — B2-6 replacement note, integrity re-check记录
> - `.harness/tasks.ps1` — 自动验证hook（check命令中的AUTO-HOOK）
> 已有专利: 3件（主案01 + CRP挑战响应02 + 多域融合03）
> 分析目标: 识别数据完整性校验方面被现有三件专利遗漏的专利点

---

## 技术背景

本系统的数据采集链路涉及多个环节，每个环节都可能产生数据丢失或损坏：

1. **FPGA端**: 256个SCALE_SCH码字逐个扫描，每个码字产生ON/OFF双态 x CH1/CH2双通道 = 4条频谱记录，每条128个FFT bin
2. **UART传输**: ASCII模式逐字符发送长帧（SPECTRUM帧781字符），二进制模式14字节头+512字节负载，波特率921600
3. **PC端捕获**: 串口读取、CSV写入、文件系统操作
4. **后处理**: 从CSV加载到numpy tensor，进行完整性校验

**实际发生过的完整性问题**:
- B2-6_014因不完整被重新采集（PROGRESS.md第46-50行）
- 2026-05-21对500份CSV进行integrity re-check，确认全部完整
- `capture_binary.py`实现了resync机制（Magic字节同步恢复）和discarded_frames计数
- `uart_feature_streamer.v`第1025行/1063行预留了checksum字段（`8'h00 // reserved for future checksum/flags extension`）

---

## 专利点列表

### 专利点1: 基于挑战-响应参数索引的多维数据完整性校验方法

- **一句话描述**: 在传感器物理身份认证系统中，利用挑战参数（SCALE_SCH索引）作为天然的数据完整性锚点，在PC端对采集到的多维响应图谱进行结构化完整性校验——验证每个挑战码字是否均包含完整的双通道双态频谱记录，从而检测UART传输丢帧、文件写入中断或FPGA状态机异常导致的缺失数据。

- **技术效果**:
  - 将256个SCALE_SCH索引（0-255）作为"预期存在"的锚点列表，每个锚点要求4条line_type（SPECTRUM_CH1/CH2、OFF_SPECTRUM_CH1/CH2），形成256x4=1024条记录的完整性矩阵
  - 校验不依赖额外校验和或CRC，而是利用挑战-响应协议本身的结构化特性（每个挑战必须有且仅有一个响应）进行完整性推断
  - 可精确定位缺失的具体挑战索引和缺失的line_type（如"SCH=137缺失OFF_SPECTRUM_CH2"），便于诊断是FPGA端OFF采集失败还是UART传输丢帧
  - 与`check_capture_integrity.py`实现对应：遍历sch_map，对每个sch检查have == LINE_TYPES（第28-31行）
  - B2-6_014的replacement流程证明了该方法在工程实践中的必要性：不完整文件被检测出后，在同条件下重新采集并替换

- **证据文件**:
  - `scripts/check_capture_integrity.py` 第1-73行（完整实现）
  - `scripts/analyze_500_baseline_and_drift.py` 第55-98行（`load_capture`函数中的`missing`检测、`complete`标志、`txn_gaps`计数）
  - `PROGRESS.md` 第25行（"Integrity re-check on 2026-05-21 found all current 500 CSV files contain complete 256 sch x 4 line_type records"）
  - `PROGRESS.md` 第46-50行（B2-6 replacement note，证明不完整检测的实际应用）

- **与现有三件专利的关系**:
  - **01_上下电瞬态响应传感器身份提取**: 本专利点可作为其从属权利要求，限定"数据完整性校验模块"的具体实现方式——利用挑战参数索引进行结构化完整性校验
  - **02_SCALE_SCH挑战扫描响应图谱生成**: 直接依赖02专利的挑战-响应结构。02专利定义了SCALE_SCH作为挑战，本专利点利用该挑战索引作为完整性锚点，是02专利在工程实现层面的自然延伸
  - **03_多特征融合稳定比特量化**: 03专利假设输入数据完整。本专利点确保输入数据的完整性，是03专利前置的数据质量保证步骤

- **需要补的实验**:
  - 量化完整性校验的漏检率和误检率：故意删除/篡改CSV中的若干条记录，验证检测率
  - 测量完整性校验的计算开销（500文件批量校验耗时）
  - 验证txn_gaps检测对FPGA状态机超时（timeout_error_code）的敏感性
  - 对比"挑战索引锚点校验" vs "传统CRC校验"在检测特定类型错误（如整帧丢失 vs 单bit翻转）上的差异

- **新颖性风险**:
  - **中低**。通用数据完整性校验（CRC、校验和、序列号）是公知技术。但"利用挑战-响应参数索引作为完整性锚点"这一特定组合具有新颖性——它将密码学/认证领域的挑战-响应结构与数据完整性校验结合，利用了"每个挑战必须有响应"这一语义约束。
  - **规避建议**: 权利要求中明确限定"挑战参数索引"和"双通道双态频谱记录"的组合，绑定传感器身份认证场景，避免被通用数据校验专利覆盖。

---

### 专利点2: 带事务ID冻结的UART请求队列与帧级原子性保证机制

- **一句话描述**: 在FPGA传感器身份认证系统中，顶层状态机通过"请求队列+事务ID+元数据冻结"机制，确保每个UART输出帧的原子性——在帧发送前一次性锁定该帧对应的SCALE_SCH索引、挑战值、上下电状态等全部元数据，防止状态机在帧发送过程中推进导致元数据错乱。

- **技术效果**:
  - 解决了2026-05-19发现的BUG（`transient_puf_test_top.v`第1126-1130行注释）：旧代码中1秒心跳直接驱动`uart_send`，导致二进制帧可能携带reset/default的txn/SCH字段或stale的ON/OFF标记
  - 实现两层隔离：
    - **请求层**（`uart_req_*`）：状态机在PEAK_DETECT阶段将当前帧的全部元数据写入请求寄存器，设置`uart_req_pending`
    - **帧层**（`uart_frame_*`）：当`uart_busy`为低且`uart_req_pending`为高时，将请求层元数据一次性复制到帧层寄存器，同时置位`uart_send`
  - 事务ID（`uart_txn_counter`）每帧递增，PC端可通过`txn_id`字段追踪帧序列连续性（`capture_binary.py`第128行`txn_gaps`检测）
  - `uart_req_pending`确保即使状态机快速推进（fast_scan模式~50ms周期），也不会覆盖正在排队等待发送的帧元数据

- **证据文件**:
  - `rtl/transient_puf_test_top.v` 第271-298行（`uart_req_*`和`uart_frame_*`寄存器声明）
  - `rtl/transient_puf_test_top.v` 第1126-1146行（BUG-FIX注释+请求队列消费逻辑）
  - `rtl/transient_puf_test_top.v` 第1323-1338行（ON状态设置uart_req_pending）
  - `rtl/transient_puf_test_top.v` 第1444-1459行（OFF状态设置uart_req_pending）
  - `rtl/uart_feature_streamer.v` 第31行（`txn_id`输入）、第1016-1017行/第1054-1055行（二进制帧txn_id输出）
  - `scripts/capture_binary.py` 第127-128行（`txn_gaps`计数）

- **与现有三件专利的关系**:
  - **01_上下电瞬态响应传感器身份提取**: 可作为从属权利要求，限定"数据输出模块"的原子性保证机制。01专利的"频谱变换单元"输出需要可靠的传输，本专利点确保传输过程中的数据一致性
  - **02_SCALE_SCH挑战扫描响应图谱生成**: 事务ID与SCALE_SCH索引的关联（`txn_id`与`sch_index`同时冻结在帧头），支持多挑战批量采集时的帧级对齐，是02专利大规模采集的工程保障
  - **03_多特征融合稳定比特量化**: 03专利的bit量化依赖准确的挑战-响应对应关系。本专利点防止"SCH索引错位"导致响应图谱结构破坏，是03专利的数据完整性前提

- **需要补的实验**:
  - 在fast_scan模式下（~50ms周期），验证请求队列是否会出现overflow（pending未被消费时新请求到达）
  - 测量uart_busy为高的持续时间（完整帧发送时间），验证请求队列深度是否足够
  - 故意在帧发送中途复位FPGA，验证PC端能否通过txn_id gap检测到异常终止
  - 对比"请求队列"方案 vs "双缓冲"方案的资源开销和可靠性

- **新颖性风险**:
  - **中**。通用FIFO/队列是公知技术。但"在传感器身份认证场景中，利用事务ID+元数据冻结保证挑战-响应帧原子性"这一特定应用组合具有新颖性。
  - **规避建议**: 权利要求中限定"物理身份认证"、"挑战参数索引"、"上下电状态标记"等特定元数据字段，绑定应用场景。强调"防止状态机推进导致元数据错乱"这一特定技术问题。

---

### 专利点3: 二进制UART帧的Magic字节同步恢复与损坏帧丢弃机制

- **一句话描述**: 在传感器身份认证系统的高速二进制UART传输中，通过Magic字节（0xA5 0x5A）作为帧边界标记，结合帧头多字段校验（协议版本、帧类型、负载长度、保留字段），实现传输流中的自动同步恢复和损坏帧自动丢弃，确保即使在丢包/误码场景下也能快速重建正确的帧解析状态。

- **技术效果**:
  - `capture_binary.py`实现了完整的resync逻辑：
    - 缓冲区中搜索Magic字节定位帧头（第138行`buffer.find(MAGIC)`）
    - Magic前存在残留数据时删除并计数resync（第144-146行）
    - 帧头找到后检查完整帧长度（第148行`len(buffer) < EXPECTED_FRAME_LEN`）
    - 解码时多字段校验：Magic、proto version、frame type、payload length、reserved field（第40-62行`decode_frame`）
    - 任一校验失败则丢弃该候选帧（单字节步进，第155-158行）
    - CH1/CH2事务配对校验：同一txn_id的CH1和CH2帧必须具有相同的`is_off`标志，否则双双丢弃（第169-175行）
  - 统计指标：`frame_count`（成功帧）、`resync_count`（同步次数）、`discarded_frames`（丢弃帧）、`complete_txn_count`（完整事务数）
  - 相比ASCII模式的逐行解析，二进制模式的Magic字节同步更鲁棒——ASCII模式依赖换行符分隔，若换行符丢失则整行错乱；二进制模式可在任意位置恢复同步

- **证据文件**:
  - `scripts/capture_binary.py` 第20-27行（Magic/版本/帧类型常量定义）
  - `scripts/capture_binary.py` 第40-75行（`decode_frame`多字段校验）
  - `scripts/capture_binary.py` 第109-193行（主循环resync+decode逻辑）
  - `rtl/uart_feature_streamer.v` 第146-152行（二进制常量定义：BIN_MAGIC0=0xA5, BIN_MAGIC1=0x5A）
  - `rtl/uart_feature_streamer.v` 第1008-1081行（二进制帧发送逻辑）
  - `PROGRESS.md` 第23行（二进制/CSV捕获管道支持256点4通道数据）

- **与现有三件专利的关系**:
  - **01_上下电瞬态响应传感器身份提取**: 可作为从属权利要求，限定"数据输出模块"在二进制模式下的传输鲁棒性机制
  - **02_SCALE_SCH挑战扫描响应图谱生成**: 二进制模式的事务ID+SCH索引帧头，直接服务于02专利的大规模挑战-响应采集。resync机制确保256个挑战的响应帧在传输中断后仍能正确重组
  - **03_多特征融合稳定比特量化**: 损坏帧丢弃机制防止错误数据进入bit量化流程，提高最终指纹的可靠性

- **需要补的实验**:
  - 量化resync机制在模拟误码场景下的恢复时间（从误码到恢复正常帧解析的延迟）
  - 测量Magic字节假阳性率（随机数据中0xA5 0x5A出现的概率及后续校验的过滤效果）
  - 对比二进制模式resync vs ASCII模式在相同误码率下的数据恢复率
  - 验证CH1/CH2配对校验对"半事务"（只收到CH1没收到CH2）的检测效果

- **新颖性风险**:
  - **中高**。Magic字节+帧头校验是通信协议的通用技术（如HDLC的0x7E标志、UART的break检测）。本方案的新颖性在于：
    - 将Magic字节与"事务ID+双通道配对校验"结合，确保挑战-响应帧的完整性
    - 针对传感器身份认证场景中的"长帧高带宽传输"优化（512字节负载+14字节头）
  - **规避建议**: 不作为独立申请，而是作为01/02主案的从属权利要求，限定"传感器瞬态身份认证"、"挑战-响应帧"、"双通道配对校验"等特定组合。

---

### 专利点4: 基于帧类型前缀过滤的UART采集鲁棒性方法

- **一句话描述**: 在PC端UART采集过程中，通过正则表达式匹配预定义的帧类型前缀列表（STATUS、STABLE_POINT、PEAKS、SPECTRUM、RAW、DEBUG_BINS、ST等），自动过滤非预期数据行和噪声，同时保留上下电双态前缀变体（OFF_前缀），确保采集CSV中只包含结构化的身份认证相关数据。

- **技术效果**:
  - `capture_uart.ps1`第95行实现了完整的前缀过滤正则：匹配15种帧类型前缀（含legacy兼容前缀如OFF_STABLEPT、OFFPK_CH1等）
  - 非匹配行被标记为"Ignored unexpected UART line"（第101行），防止噪声/调试输出污染CSV
  - 同时支持ON/OFF双态前缀自动识别：`SPECTRUM_CH1` vs `OFF_SPEC_CH1`、`PEAKS_CH1_B` vs `OFF_PEAKS_CH1_B`等
  - 与`verify_uart_format.py`联动：采集阶段过滤+后处理阶段格式验证，形成两层数据质量保证
  - 实际效果：500份CSV文件经integrity re-check确认全部包含完整的256 sch x 4 line_type记录

- **证据文件**:
  - `scripts/capture_uart.ps1` 第93-102行（前缀过滤正则+unexpected line处理）
  - `scripts/verify_uart_format.py` 第1-20行（验证项列表，覆盖9类格式检查）
  - `scripts/verify_uart_format.py` 第269-413行（主验证函数，含line type计数、版本一致性检查）
  - `PROGRESS.md` 第25行（500 CSV完整性re-check结果）
  - `.harness/tasks.ps1` 第484-512行（AUTO-HOOK：check通过后自动运行verify_uart_format.py）

- **与现有三件专利的关系**:
  - **01_上下电瞬态响应传感器身份提取**: 可作为从属权利要求，限定"数据采集模块"的帧类型过滤机制，确保ON/OFF双态数据正确分离
  - **02_SCALE_SCH挑战扫描响应图谱生成**: STATUS帧中的SCALE_SCH索引是02专利的核心。前缀过滤确保STATUS帧不被噪声淹没或误识别
  - **03_多特征融合稳定比特量化**: 过滤机制防止非结构化数据进入特征提取流程，提高bit量化的输入质量

- **需要补的实验**:
  - 量化前缀过滤的误过滤率（合法帧被误判为unexpected的比例）和漏过滤率（噪声被误判为合法帧的比例）
  - 测试legacy前缀兼容（OFF_STABLEPT、OFFPK_等）在实际采集中的触发频率
  - 验证`verify_uart_format.py`对故意篡改的CSV（如删除STATUS行、修改版本号）的检测能力
  - 测量AUTO-HOOK（check通过后自动验证）对开发流程缺陷的拦截效果

- **新颖性风险**:
  - **高**。正则表达式过滤是通用编程技术，单独主张容易被现有技术覆盖。
  - **规避建议**: 不作为独立申请。可作为01主案的从属权利要求中的一个步骤，强调"在传感器身份认证场景中，通过预定义帧类型前缀列表自动区分上电/下电双态数据并过滤噪声"。

---

### 专利点5: FPGA状态机超时 watchdog 与错误码上报机制

- **一句话描述**: 在传感器身份认证FPGA中，为主状态机的每个操作状态设置超时 watchdog（3秒阈值），当状态机异常卡住时自动复位到IDLE并上报特定错误码，同时通过UART STATE_LOG帧将错误码和状态迁移历史传递给PC端，实现硬件级故障自诊断与数据完整性关联。

- **技术效果**:
  - `transient_puf_test_top.v`第1153-1193行实现了完整的超时检测：
    - 每个状态迁移被记录为`main_debug_event`（4位hex，第1158-1174行）
    - 状态停留时间计数器`state_timeout_counter`（第1175行）
    - 11个操作状态各有独立错误码（`timeout_error_code` 1-11，第1180-1191行）
    - 超时后自动复位到IDLE，防止FPGA永久卡死
  - 错误码通过两条路径上报：
    - UART STATUS帧中的EC字段（error_code，2位十进制）
    - UART STATE_LOG帧（`ST,X,Y,ZZ\n`格式，第988-1006行）
  - PC端可通过`timeout_error_code`非零值判断该次采集是否发生过状态机异常，从而标记该capture文件的可靠性
  - 与数据完整性关联：若某capture文件中多个SCH的STATUS帧EC字段非零，说明FPGA在采集过程中多次超时复位，该文件应被视为不可靠

- **证据文件**:
  - `rtl/transient_puf_test_top.v` 第1153-1193行（超时watchdog完整实现）
  - `rtl/transient_puf_test_top.v` 第1175行（`STATE_TIMEOUT_LIMIT`计数器）
  - `rtl/uart_feature_streamer.v` 第276-335行（STATUS帧EC字段输出）
  - `rtl/uart_feature_streamer.v` 第988-1006行（STATE_LOG帧格式）
  - `scripts/verify_uart_format.py` 第43-67行（STATUS格式验证，含EC字段检查）

- **与现有三件专利的关系**:
  - **01_上下电瞬态响应传感器身份提取**: 可作为从属权利要求，限定"状态控制模块"的故障自诊断能力。01专利的"受控电源状态切换"需要可靠的状态机执行，本专利点确保状态机异常可被检测和恢复
  - **02_SCALE_SCH挑战扫描响应图谱生成**: 超时复位会导致当前SCH的响应不完整。错误码机制帮助PC端识别哪些SCH的响应是在异常后采集的，应予以剔除
  - **03_多特征融合稳定比特量化**: 03专利的稳定性筛选可结合错误码信息——仅使用EC=0的采集数据进行bit模板训练

- **需要补的实验**:
  - 故意在FPGA运行中注入故障（如暂停时钟），验证watchdog超时和错误码上报的准确性
  - 统计正常采集过程中错误码的触发频率（应接近0）
  - 验证PC端通过EC字段筛选可靠数据的分类效果
  - 测量超时复位对整体采集时间的影响（256 SCH完整周期延长多少）

- **新颖性风险**:
  - **中高**。状态机超时watchdog是FPGA设计的常规技术。新颖性在于：
    - 将超时错误码与UART输出帧绑定，实现"硬件故障→数据标记"的闭环
    - 错误码与传感器身份认证的数据质量评估直接关联
  - **规避建议**: 作为01主案的从属权利要求，限定"传感器身份认证场景中的状态机超时自诊断与数据可靠性标记"。

---

## 综合建议

### 优先申请排序

1. **专利点1（挑战索引锚点完整性校验）** — 新颖性中低但技术效果明确，与02专利强关联，可作为02的从属权利要求或独立申请
2. **专利点2（事务ID冻结请求队列）** — 新颖性中，直接解决实际BUG，工程价值高，可作为01的从属权利要求
3. **专利点3（Magic字节同步恢复）** — 新颖性中高，但工程实用性强，可作为01/02的从属权利要求
4. **专利点5（状态机超时watchdog）** — 新颖性中高，可作为01的从属权利要求
5. **专利点4（帧类型前缀过滤）** — 新颖性高（风险大），建议仅作为技术秘密或01的极从属权利要求

### 与现有三件专利的整合策略

| 专利点 | 建议整合方式 | 绑定主案 |
|:---|:---|:---|
| 1. 挑战索引锚点校验 | 从属权利要求："数据完整性校验模块" | 02 |
| 2. 事务ID冻结队列 | 从属权利要求："UART输出原子性保证" | 01 |
| 3. Magic字节resync | 从属权利要求："二进制传输鲁棒性" | 01/02 |
| 4. 帧类型前缀过滤 | 技术秘密或极从属权利要求 | 01 |
| 5. 状态机超时watchdog | 从属权利要求："故障自诊断" | 01 |

### 需要补的共同实验

1. **完整性校验覆盖率测试**: 故意构造100种错误模式（单条缺失、整SCH缺失、line_type错位、txn_id跳号、版本号不一致等），验证各专利点检测机制的综合覆盖率
2. **端到端可靠性量化**: 从FPGA上电到PC端生成完整tensor的全链路，量化各环节的错误率和检测率
3. **数据完整性对认证安全的影响**: 对比"完整数据"vs"含缺失数据"对最终识别准确率的影响，证明完整性校验的安全必要性
