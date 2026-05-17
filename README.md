# AstrBot NovelAI MCP + Skill

一个面向 AstrBot 的 NovelAI 创作方案：

- **MCP Server**：调用 NovelAI 进行图片 / 文本生成
- **Skill**：指导 LLM 何时、如何调用 MCP 工具
- **记忆集成**：通过 AstrBot 原生对话流记录创作历史，可被 livingmemory 等记忆插件拾取

## 仓库结构

```text
.
├── mcp_server/   # NovelAI MCP 服务端源码
└── skill/        # AstrBot Skill 源码
```

## 功能特性

- 图像生成：中文需求 → 英文标签 → NovelAI 生图
- 文本生成：写诗、短文、故事、续写
- 默认免费小图：`small_portrait` / `small_landscape` / `small_square`
- 生图 / 文本冷却限制
- 失败不计入冷却
- 创作行为纳入正常对话流，减少记忆割裂

## 适用场景

适合你在 AstrBot 中：

- 让 LLM 通过 Skill 自然触发生图 / 创作
- 让创作历史进入对话记忆
- 与 livingmemory 等长期记忆插件一起使用

## 部署说明

### Linux 服务器

请查看：

- `mcp_server/README.md`

### Windows 本地

请查看：

- `mcp_server/README.md`

## AstrBot 使用方式

1. 配置 MCP 服务器（指向 `mcp_server/server.py`）
2. 上传 Skill（`skill/SKILL.md` 所在文件夹打包后上传）
3. 由 LLM 根据 Skill 指令调用 NovelAI MCP 工具

## 重要说明

### 1. 当前是 stdio MCP

当前 `mcp_server` 使用的是 **stdio MCP**。

- AstrBot 会按需拉起它
- 不需要手动长期常驻
- 不建议把当前版本直接作为普通 systemd 常驻服务运行

如果后续需要 systemd 常驻托管，建议改造成 **HTTP / SSE MCP** 服务。

### 2. 关于 tokenizer 文件

`mcp_server/tokenizers/` 中包含 NovelAI 文本模型所需 tokenizer 文件。

### 3. API Key 安全

本仓库不存储真实 API Key。

请通过 AstrBot 的 MCP 配置 `env` 注入：

- `NOVELAI_API_KEY`
- `NOVELAI_PROXY`


## License

MIT
