# Harness — FPGA_transDATA V6.4

所有开发操作通过 `.\.harness\tasks.ps1 <command>` 统一入口。

## 命令一览

| 命令 | 作用 |
|:---|:---|
| `env` | 工具链检查（Vivado/Verilator/Python） |
| `lint` | Verilator lint 所有 RTL |
| `sim` | 运行所有 testbench |
| `check` | **env → lint → sim** 串行执行，全绿后自动 git commit |
| `build` | Vivado 完整构建（综合→实现→bitstream） |
| `program` | JTAG 烧录 SRAM（临时调试） |
| `capture -Port=COM5` | UART ASCII 捕获 |
| `clean [-Hard]` | 清理生成物（hard 也清 build/） |
| `status` | 项目状态概览 |
| `done` | 收工检查清单 |

## 目录结构

```
.harness/
├── tasks.ps1              # 统一入口
├── init.ps1               # 会话初始化
├── lessons.md              # 硬性约束规则
├── omc.md                  # OMC 调度规则
├── qa_report_template.md   # QA 报告模板
├── session_bootstrap.md    # 新会话启动胶囊
├── glossary.md             # 反直觉术语速查
├── feature_list.json       # 功能蓝图
├── sim_regressions.json    # 回归分组
├── qa/                     # QA 报告存档
├── logs/                   # 命令输出日志
└── state/                  # 状态文件
```

## QA 工作流

任何 RTL/脚本改动后：
1. `.\.harness\tasks.ps1 check` — 全绿才能进下一步
2. 填写 QA 报告到 `.harness/qa/QA_REPORT_<日期>_<topic>.md`
3. 呈递用户，等待"已审阅/已授权烧板"
4. 授权后 `build` / `program`

## 脚本说明

| 脚本 | 用途 |
|:---|:---|
| `scripts/env_check.ps1` | 工具链断言检查 |
| `scripts/lint_all.ps1` | Verilator lint |
| `scripts/sim_all.ps1` | 仿真运行 |
| `scripts/build.ps1` | Vivado 构建入口 |
| `scripts/build_v60.tcl` | TCL 构建脚本 |
| `scripts/program.ps1` | JTAG 烧录 |
| `scripts/program_v60.tcl` | TCL 烧录脚本 |
| `scripts/capture_ascii_v60.py` | UART 捕获解析 |

## 版本号

只在 `rtl/transient_puf_v60_top.v` 定义。所有子模块通过参数接收。
