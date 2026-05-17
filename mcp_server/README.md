# NovelAI MCP Server + Skill

AstrBot NovelAI 创作方案：MCP 服务器 + Skill，让 LLM 通过自然语言调用 NovelAI 生成图片和文本。

## 架构

```
用户 → AstrBot LLM → Skill（指令）→ MCP 工具 → NovelAI API → 返回结果 → LLM 回复用户
                                        ↓
                              AstrBot 对话系统自动记录
                                        ↓
                              livingmemory 等插件拾取记忆
```

## 功能

| 功能 | 说明 |
|------|------|
| 🎨 图像生成 | 自然语言 → 英文标签 → NovelAI 生图 |
| ✍️ 文本生成 | 写诗/写故事/续写，支持自动续写 |
| 📐 多尺寸 | 免费小图（默认）、标准图、大图 |
| ⏱️ 冷却时间 | 生图 60 秒，文本 30 秒，失败不计 |
| 🧠 记忆集成 | 创作记录自动注入 AstrBot 对话系统 |
| 🔑 安全 | API Key 只存 AstrBot 配置，服务器不存 |

## 重要说明

### 1. 当前 MCP 传输方式是 stdio

本项目当前使用 **stdio MCP**。

这意味着：
- AstrBot 会在需要时**自动启动** MCP 进程
- 不需要手动常驻运行
- **不建议**直接用 `systemd` 把当前这个 stdio 版 server.py 长期挂起

原因：stdio MCP 的输入输出由 AstrBot 接管；如果你把它当成普通常驻服务启动，它不会像 HTTP 服务那样对外监听端口，也不能被 AstrBot 通过网络连接复用。

如果后续你明确需要 **systemd 常驻托管**，建议下一步改造成 **HTTP / SSE 版 MCP 服务**。

### 2. 推荐使用“生产版 Skill”

当前附带的 `novelai_skill.zip` 已经是更短、更稳定的生产版：
- 更强约束默认免费小图
- 更明确要求先把中文描述转成英文标签
- 更少冗余说明，降低 LLM 跑偏概率

### 3. 公开发布前请注意 tokenizer 文件来源

仓库中包含 `tokenizers/` 目录，用于本地完成 NovelAI 文本模型的编码/解码。

在**私有使用**场景下通常没有问题；但如果你准备**公开发布到 GitHub**，建议你自行确认这些 tokenizer 文件的分发许可是否满足你的发布要求。

如果你不确定，建议：
- 将仓库设为私有
- 或改成首次运行时由脚本自行获取 tokenizer 文件
- 或在发布说明中明确它们的来源与用途

## MCP 工具

### novelai_generate_image

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| prompt | string | **英文标签**格式的图片描述 | 必填 |
| size | string | 图片尺寸 | small_portrait |
| model | string | 绘图模型 | nai-diffusion-4-5-full |

**尺寸选项：**

| 尺寸 | 分辨率 | Anlas |
|------|--------|-------|
| `small_portrait` | 512x768 | 免费 |
| `small_landscape` | 768x512 | 免费 |
| `small_square` | 512x512 | 免费 |
| `portrait` | 832x1216 | 消耗 |
| `landscape` | 1216x832 | 消耗 |
| `square` | 1024x1024 | 消耗 |
| `large_portrait` | 1024x1536 | 消耗更多 |
| `large_landscape` | 1536x1024 | 消耗更多 |

### novelai_generate_text

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| prompt | string | 创作提示（中文） | 必填 |
| model | string | 文本模型 | llama-3-erato-v1 |
| max_length | int | 最大生成长度 | 500 |

**模型选项：**

| 模型 | ID | 说明 |
|------|----|------|
| Erato | `llama-3-erato-v1` | 最强，Opus 订阅 |
| Kayra | `kayra-v1` | 高质量 |
| Clio | `clio-v1` | 经典 |

## 文件结构

```
novelai_mcp_server/
├── server.py              # MCP 服务器核心
├── spm_decoder.py         # 纯 Python sentencepiece 解码器
├── requirements.txt       # Python 依赖
├── install.sh             # Linux 安装脚本
├── start.sh               # Linux 启动脚本
├── start.bat              # Windows 启动脚本
├── mcp_config.json        # AstrBot MCP 配置示例（Windows）
├── astrbot_mcp_config.json # AstrBot MCP 配置示例（Linux）
└── tokenizers/            # NovelAI tokenizer 文件
    ├── nerdstash_v1.model
    ├── nerdstash_v2.model
    └── llama3.json

novelai_skill/
└── SKILL.md               # AstrBot Skill 文件
```

## 安装部署

### Linux 服务器

```bash
# 1. 上传
scp novelai_mcp_server_linux.zip ubuntu@服务器IP:/home/ubuntu/

# 2. 解压安装
cd /home/ubuntu
unzip novelai_mcp_server_linux.zip
cd novelai_mcp_server
chmod +x install.sh start.sh
./install.sh

# 3. 测试（可选）
NOVELAI_API_KEY=test NOVELAI_PROXY=http://127.0.0.1:7890 ./venv/bin/python3 server.py
```

> 注意：上面这一步只是手动测试 MCP 是否能正常启动。正式使用时，由 AstrBot 自动拉起，不需要你手动常驻运行。

### Windows 本地

```powershell
# 1. 解压
Expand-Archive novelai_mcp_server_windows.zip -DestinationPath .

# 2. 安装依赖
cd novelai_mcp_server
pip install -r requirements.txt

# 3. 测试
$env:NOVELAI_API_KEY = "你的密钥"
$env:NOVELAI_PROXY = "http://127.0.0.1:7897"
python server.py
```

## AstrBot 配置

### 1. MCP 服务器

AstrBot WebUI → 设置 → MCP 服务器 → 添加：

**Linux：**
```json
{
  "command": "/home/ubuntu/novelai_mcp_server/venv/bin/python3",
  "args": ["server.py"],
  "cwd": "/home/ubuntu/novelai_mcp_server",
  "env": {
    "NOVELAI_API_KEY": "你的API密钥",
    "NOVELAI_PROXY": "http://127.0.0.1:7890"
  }
}
```

**Windows：**
```json
{
  "command": "python",
  "args": ["server.py"],
  "cwd": "E:\\你的路径\\novelai_mcp_server",
  "env": {
    "NOVELAI_API_KEY": "你的API密钥",
    "NOVELAI_PROXY": "http://127.0.0.1:7897"
  }
}
```

### 2. Skill

AstrBot WebUI → 插件 → Skills → 上传 `novelai_skill.zip`

建议直接使用当前包内的生产版 Skill，不要再把过长的提示说明写进人格设定。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NOVELAI_API_KEY` | NovelAI API Key | 无（必填） |
| `NOVELAI_PROXY` | HTTP 代理地址 | 空 |
| `IMAGE_COOLDOWN` | 生图冷却时间（秒） | 60 |
| `TEXT_COOLDOWN` | 文本生成冷却时间（秒） | 30 |

## 使用示例

```
用户: 画一个海边日落
助手: 已为你生成了一幅海边日落的图片 🌅

用户: 写一首秋天的诗
助手: 这是为你创作的秋日小诗：
      金风送爽叶初黄，碧水长天映夕阳...

用户: 画一个猫娘，大图
助手: 已生成大图 🐱

用户: 再画一个   ← 冷却中
助手: 还需要等 45 秒哦~
```

## 记忆集成

MCP 工具调用后，AstrBot 自动将创作记录存入对话系统。配合 livingmemory 插件，LLM 能"记住"之前的创作内容，实现连续创作体验。

这也是推荐 MCP 方案的核心原因：
- 创作行为发生在正常对话流中
- AstrBot 原生记忆可以记录
- livingmemory 可以继续拾取这些历史
- 不需要在独立插件里额外模拟一套长期记忆系统

## 依赖

- Python 3.10+
- httpx >= 0.28.0
- novelai-sdk >= 0.8.0
- tokenizers >= 0.15.0
- mcp >= 1.0.0

## 许可证

MIT License
