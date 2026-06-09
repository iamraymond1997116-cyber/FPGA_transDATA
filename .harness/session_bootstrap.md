# 会话启动引导

用户说"初始化"时，按此顺序执行。

## 执行顺序

1. **跑 `init.ps1`** — 环境检查 + 状态恢复 + 清理锁
2. **读 `PROGRESS.md`** — 当前状态、下一步、会话记录
3. **读 `.harness/lessons.md`** — 27 条硬性约束
4. **读 `.harness/omc.md`** — OMC 调度规则
5. **跑 `tasks.ps1 check`** — env + lint + sim 全绿验证

## 初始化条件

只在以下情况走完整流程：
- `tasks.ps1 check` 失败
- harness 文件缺失
- 用户明确说"初始化"

## 最短路径

```
.\.harness\tasks.ps1 check      # 环境+lint+sim
.\.harness\tasks.ps1 build      # bitstream
.\.harness\tasks.ps1 program    # JTAG 烧录
python scripts\capture_ascii_v60.py --port COM5  # 捕获
```
