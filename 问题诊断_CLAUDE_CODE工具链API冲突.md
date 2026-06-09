# Claude Code 工具链 API 冲突诊断

> 日期：2026-06-09  
> 环境：Claude Code v2.1.169 (VS Code 扩展) + 代理 `api-slb.packyapi.com`

## 现象

Claude Code 的内置工具链（WebSearch、Agent、WebFetch、Workflow 子 agent）会报 400：

```text
API Error: 400 thinking options type cannot be disabled when reasoning_effort is set
```

主对话正常，Python 直调 API 正常。

## 已排除的因素

| 排查项 | 结论 |
|:---|:---|
| `settings.json` 里的 `effortLevel` | 不是，改成 `none` / `low` / 不设置都试过 |
| 模型名里的 `[1m]` ANSI 残留 | 不是，清理后仍报错 |
| `ANTHROPIC_REASONING_MODEL` 环境变量 | 不是，删除后仍报错 |
| 模型 tier 不统一（haiku / opus / sonnet） | 不是，全部统一为 `deepseek-v4-flash` 后仍报错 |
| 旧 daemon 进程缓存配置 | 不是，杀掉旧进程重启后仍报错 |
| 请求参数组合（`thinking` / `reasoning_effort` / `system` / `tools`） | 不是单纯参数值问题，Python 直调同组合均 HTTP 200 |
| `CLAUDE_EFFORT` 环境变量 | 不是，从 `high` 改 `low` 后仍报错 |

## 真正根因

**`claude.exe` 内部构造子请求的方式与代理 `api-slb.packyapi.com` 不兼容。**

具体来说：

1. Claude Code 的工具链在发起子请求时，由 `claude.exe` 构造 HTTP 请求。
2. 该内部请求会带上 `thinking: { type: "disabled" }`，并且还会携带某种 `reasoning_effort`。
3. 代理 `api-slb.packyapi.com` 对这个组合返回 400。
4. 关键证据是：同样的参数组合通过 Python `requests` 直调 `/v1/messages` 全部返回 HTTP 200。
5. 所以问题不在参数值本身，而在 **Claude Code 生成请求的方式**，或者代理对该请求格式的兼容层。

## 验证方法

```python
import os
import requests

headers = {
    "Content-Type": "application/json",
    "x-api-key": os.environ["ANTHROPIC_AUTH_TOKEN"],
    "anthropic-version": "2023-06-01",
}

body = {
    "model": "deepseek-v4-flash",
    "max_tokens": 200,
    "messages": [{"role": "user", "content": "say hello"}],
    "thinking": {"type": "disabled"},
    "reasoning_effort": "medium",
    "stream": False,
}

r = requests.post("https://api-slb.packyapi.com/v1/messages", headers=headers, json=body, timeout=15)
print(r.status_code)
print(r.text[:200])
```

## 当前 settings.json 状态

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<已轮换>",
    "ANTHROPIC_BASE_URL": "https://api-slb.packyapi.com",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_MODEL": "deepseek-v4-flash"
  },
  "effortLevel": "low",
  "theme": "light-daltonized",
  "enabledPlugins": {
    "caveman@caveman": true,
    "superpowers@claude-plugins-official": true,
    "academic-research-skills@academic-research-skills": true
  }
}
```

> 注意：模型名已去掉所有 `[1m]` ANSI 残留，`ANTHROPIC_REASONING_MODEL` 已删除，所有 tier 统一为 `deepseek-v4-flash`。

## 建议修复方向

1. 升级 Claude Code 版本，再复测是否修复了子请求构造问题。
2. 代理端修复，让 `api-slb.packyapi.com` 兼容 `claude.exe` 发送的请求格式。
3. 切换客户端，例如继续用 Codex CLI 或直接 Python 调 API，绕开这条兼容链。
4. 保留最小复现脚本，继续验证 `thinking` / `reasoning_effort` 的边界。
