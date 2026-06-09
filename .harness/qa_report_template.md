# QA Report — `<YYYY-MM-DD>` — `<topic>`

> 任何代码改动完成后，复制本模板填写到 `.harness/qa/QA_REPORT_<日期>_<topic>.md`，呈递用户。

## 1. 独立验证结果

| 验证项 | 结果 | 输出摘要 |
|:---|:---|:---|
| Verilator lint (`tasks.ps1 lint`) | ✅/❌ | |
| Simulation (`tasks.ps1 sim`) | ✅/❌ | |
| RTL static review | ✅/❌ | |

## 2. 改动清单

| 文件 | 改动类型 | 行号 | 摘要 |
|:---|:---|:---|:---|
| `rtl/foo.v` | MODIFY | L100-L120 | |

**版本号**：V`x.y` → V`x.y+1`

## 3. 残留风险

| 风险点 | 级别 | 影响 | 缓解 |
|:---|:---|:---|:---|
| | P0/P1/P2 | | |

## 4. 下一步

1. `.\.harness\tasks.ps1 build` (~5-10 min)
2. `program` → `capture` 验证

## 签字

- 代理：`<agent>`
- 用户审阅：`☐ 已审阅 ☐ 已授权烧板`
