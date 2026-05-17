"""
NovelAI MCP Server
本地 MCP 服务器，包装 NovelAI 图像和文本生成 API。
AstrBot 通过 MCP 连接调用，生成过程在对话中自然完成，记忆自动保存。
"""

import os
import json
import asyncio
import base64
from pathlib import Path
from typing import Any

import httpx

# NovelAI SDK
from novelai import NovelAI
from novelai.types import GenerateImageParams

# Tokenizer
import sys
sys.path.insert(0, str(Path(__file__).parent))
from spm_decoder import SentencePieceModel

# MCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

# ==================== 配置 ====================
NOVELAI_API_KEY = os.environ.get("NOVELAI_API_KEY", "")
NOVELAI_PROXY = os.environ.get("NOVELAI_PROXY", "")
NOVELAI_BASE_URL = "https://api.novelai.net"
NOVELAI_TEXT_URL = "https://text.novelai.net"

# Tokenizer 路径
TOKENIZER_DIR = Path(__file__).parent / "tokenizers"

# 模型配置
TEXT_MODELS = {"kayra-v1", "llama-3-erato-v1"}
MODEL_TOKENIZERS = {
    "clio-v1": "nerdstash_v1",
    "kayra-v1": "nerdstash_v2",
    "llama-3-erato-v1": "llama3",
}
FOUR_BYTE_TOKEN_MODELS = {"llama-3-erato-v1"}

# ==================== 初始化 ====================
app = Server("novelai-mcp")
novelai_client = None
tokenizers = {}

# 冷却时间配置（秒）
IMAGE_COOLDOWN = int(os.environ.get("IMAGE_COOLDOWN", "60"))
TEXT_COOLDOWN = int(os.environ.get("TEXT_COOLDOWN", "30"))
_last_image_time = 0
_last_text_time = 0

def init_novelai_client():
    global novelai_client
    if NOVELAI_API_KEY:
        if NOVELAI_PROXY:
            os.environ["HTTP_PROXY"] = NOVELAI_PROXY
            os.environ["HTTPS_PROXY"] = NOVELAI_PROXY
        novelai_client = NovelAI(api_key=NOVELAI_API_KEY)

def init_tokenizers():
    global tokenizers
    try:
        # Clio
        v1_path = TOKENIZER_DIR / "nerdstash_v1.model"
        if v1_path.exists():
            tokenizers["nerdstash_v1"] = SentencePieceModel.from_file(str(v1_path))

        # Kayra
        v2_path = TOKENIZER_DIR / "nerdstash_v2.model"
        if v2_path.exists():
            tokenizers["nerdstash_v2"] = SentencePieceModel.from_file(str(v2_path))

        # Erato (llama3)
        import tokenizers as tk
        llama3_path = TOKENIZER_DIR / "llama3.json"
        if llama3_path.exists():
            # 复制到临时文件避免中文路径问题
            import tempfile
            fd, tmp = tempfile.mkstemp(suffix=".json")
            try:
                flags = os.O_RDONLY
                if hasattr(os, 'O_BINARY'):
                    flags |= os.O_BINARY
                src_fd = os.open(str(llama3_path), flags)
                data = b""
                while True:
                    chunk = os.read(src_fd, 65536)
                    if not chunk:
                        break
                    data += chunk
                os.close(src_fd)
                os.write(fd, data)
                os.close(fd)
                tokenizers["llama3"] = tk.Tokenizer.from_file(tmp)
            finally:
                os.unlink(tmp)
    except Exception as e:
        print(f"Tokenizer 初始化失败: {e}")

def tokens_to_b64(tokens: list, token_size: int = 2) -> str:
    from base64 import b64encode
    return b64encode(b"".join(t.to_bytes(token_size, "little") for t in tokens)).decode()

def b64_to_tokens(b64_str: str, token_size: int = 2) -> list:
    from base64 import b64decode
    b = b64decode(b64_str)
    return [int.from_bytes(b[i:i+token_size], "little") for i in range(0, len(b), token_size)]

# ==================== MCP 工具 ====================

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="novelai_generate_image",
            description="使用 NovelAI 生成图片。根据描述生成一张 AI 图片。",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "图片描述（自然语言或英文标签），例如：'一个可爱的女孩在海边看日落' 或 '1girl, beach, sunset, masterpiece'"
                    },
                    "size": {
                        "type": "string",
                        "enum": ["small_portrait", "small_landscape", "small_square", "portrait", "landscape", "square", "large_portrait", "large_landscape"],
                        "description": "图片尺寸：small_portrait=小竖图(512x768,免费), small_landscape=小横图(768x512,免费), small_square=小方图(512x512,免费), portrait=竖图(832x1216), landscape=横图(1216x832), square=方图(1024x1024), large_portrait=大竖图(1024x1536), large_landscape=大横图(1536x1024)",
                        "default": "small_portrait"
                    },
                    "model": {
                        "type": "string",
                        "enum": ["nai-diffusion-4-5-full", "nai-diffusion-4-5-curated", "nai-diffusion-4-full", "nai-diffusion-4-curated"],
                        "description": "绘图模型",
                        "default": "nai-diffusion-4-5-full"
                    }
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="novelai_generate_text",
            description="使用 NovelAI 生成文本。可以写诗、写故事、续写等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "创作提示，例如：'写一首关于秋天的诗' 或 '在一个遥远的魔法王国里...'"
                    },
                    "model": {
                        "type": "string",
                        "enum": ["llama-3-erato-v1", "kayra-v1", "clio-v1"],
                        "description": "文本模型：llama-3-erato-v1=Erato(Opus,最强), kayra-v1=Kayra, clio-v1=Clio",
                        "default": "llama-3-erato-v1"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "最大生成长度（token数），250-1500",
                        "default": 500
                    }
                },
                "required": ["prompt"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    if name == "novelai_generate_image":
        return await handle_image_generation(arguments)
    elif name == "novelai_generate_text":
        return await handle_text_generation(arguments)
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]

# ==================== 图像生成 ====================

async def handle_image_generation(args: dict) -> list[TextContent | ImageContent]:
    global _last_image_time
    prompt = args.get("prompt", "")
    size = args.get("size", "portrait")
    model = args.get("model", "nai-diffusion-4-5-full")

    if not novelai_client:
        return [TextContent(type="text", text="错误：NovelAI API Key 未配置")]

    # 冷却检查
    import time
    now = time.time()
    elapsed = now - _last_image_time
    if elapsed < IMAGE_COOLDOWN:
        remaining = int(IMAGE_COOLDOWN - elapsed)
        return [TextContent(type="text", text=f"⏳ 请等待 {remaining} 秒后再试（生图冷却时间）")]

    # 尺寸映射
    SIZE_MAP = {
        # 小图（免费）
        "small_portrait": (512, 768),
        "small_landscape": (768, 512),
        "small_square": (512, 512),
        # 标准
        "portrait": (832, 1216), "landscape": (1216, 832), "square": (1024, 1024),
        # 大图
        "large_portrait": (1024, 1536), "large_landscape": (1536, 1024),
    }
    size_tuple = SIZE_MAP.get(size, (512, 768))

    # 添加质量标签
    if not prompt.startswith("masterpiece"):
        prompt = f"masterpiece, best quality, {prompt}"

    try:
        params = GenerateImageParams(
            prompt=prompt,
            negative_prompt="lowres, bad anatomy, bad hands, text, error, missing fingers, worst quality, low quality",
            model=model,
            size=size_tuple,
            steps=28,
            scale=5.0,
            sampler="k_euler_ancestral",
        )
        images = novelai_client.image.generate(params)

        if not images:
            return [TextContent(type="text", text="图像生成失败，未返回结果")]

        # 更新冷却时间
        _last_image_time = time.time()

        # 保存图片
        save_dir = Path(__file__).parent / "generated_images"
        save_dir.mkdir(exist_ok=True)

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []

        for i, img in enumerate(images):
            filename = f"nai_{timestamp}_{i}.png"
            filepath = save_dir / filename
            img.save(str(filepath))

            # 返回真正的图片内容给 AstrBot，而不只是文本路径
            with open(filepath, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            # 可同时返回一条简短文本，便于 LLM 组织回复
            results.append(TextContent(type="text", text="图片生成完成"))
            results.append(ImageContent(type="image", data=image_b64, mimeType="image/png"))

        return results

    except Exception as e:
        error_str = str(e)
        if "Rate limit" in error_str or "429" in error_str:
            return [TextContent(type="text", text="NovelAI API 限流了，请稍等几秒再试")]
        return [TextContent(type="text", text=f"图像生成失败: {error_str}")]

# ==================== 文本生成 ====================

async def handle_text_generation(args: dict) -> list[TextContent]:
    global _last_text_time
    prompt = args.get("prompt", "")
    model = args.get("model", "llama-3-erato-v1")
    max_length = args.get("max_length", 500)

    if not NOVELAI_API_KEY:
        return [TextContent(type="text", text="错误：NovelAI API Key 未配置")]

    # 冷却检查
    import time
    now = time.time()
    elapsed = now - _last_text_time
    if elapsed < TEXT_COOLDOWN:
        remaining = int(TEXT_COOLDOWN - elapsed)
        return [TextContent(type="text", text=f"⏳ 请等待 {remaining} 秒后再试（文本生成冷却时间）")]

    # Tokenize
    tokenizer_name = MODEL_TOKENIZERS.get(model)
    if not tokenizer_name or tokenizer_name not in tokenizers:
        return [TextContent(type="text", text=f"错误：模型 {model} 的 tokenizer 未加载")]

    tokenizer = tokenizers[tokenizer_name]

    try:
        # 编码
        if hasattr(tokenizer, 'encode') and hasattr(tokenizer, 'vocab_size'):
            tokens = tokenizer.encode(prompt)
        else:
            tokens = tokenizer.encode(prompt).ids

        token_size = 4 if model in FOUR_BYTE_TOKEN_MODELS else 2
        encoded_input = tokens_to_b64(tokens, token_size)

        # API 请求
        base_url = NOVELAI_TEXT_URL if model in TEXT_MODELS else NOVELAI_BASE_URL
        url = f"{base_url}/ai/generate"

        parameters = {
            "temperature": 1.0,
            "max_length": max_length,
            "min_length": 1,
            "top_k": 0,
            "top_p": 0.9,
            "typical_p": 0.0,
            "tail_free_sampling": 1.0,
            "repetition_penalty": 1.1,
            "repetition_penalty_range": 2048,
            "repetition_penalty_frequency": 0.0,
            "repetition_penalty_presence": 0.0,
            "generate_until_sentence": True,
            "order": [0, 2, 1, 3, 5],
        }

        headers = {
            "Authorization": f"Bearer {NOVELAI_API_KEY}",
            "Content-Type": "application/json",
        }

        proxy_kwargs = {"proxy": NOVELAI_PROXY} if NOVELAI_PROXY else {}

        async with httpx.AsyncClient(timeout=120.0, **proxy_kwargs) as client:
            response = await client.post(url, headers=headers, json={
                "input": encoded_input,
                "model": model,
                "parameters": parameters,
            })

        expected_status = 200 if model in TEXT_MODELS else 201
        if response.status_code != expected_status:
            return [TextContent(type="text", text=f"API 请求失败: {response.text[:500]}")]

        result = response.json()
        output_b64 = result.get("output", "")
        if not output_b64:
            return [TextContent(type="text", text="API 返回了空结果")]

        # 解码
        output_tokens = b64_to_tokens(output_b64, token_size)
        if hasattr(tokenizer, 'decode') and hasattr(tokenizer, 'vocab_size'):
            output_text = tokenizer.decode(output_tokens)
        else:
            output_text = tokenizer.decode(output_tokens)

        # 自动续写（如果被截断）
        full_text = output_text
        continues = 0
        while full_text and not full_text.rstrip()[-1] in '。！？…」』）》"' and continues < 3:
            continues += 1
            context = prompt + full_text
            if hasattr(tokenizer, 'encode') and hasattr(tokenizer, 'vocab_size'):
                tokens = tokenizer.encode(context)
            else:
                tokens = tokenizer.encode(context).ids
            encoded = tokens_to_b64(tokens, token_size)

            async with httpx.AsyncClient(timeout=120.0, **proxy_kwargs) as client:
                resp = await client.post(url, headers=headers, json={
                    "input": encoded,
                    "model": model,
                    "parameters": parameters,
                })

            if resp.status_code != expected_status:
                break
            r = resp.json()
            ob = r.get("output", "")
            if not ob:
                break
            ot = b64_to_tokens(ob, token_size)
            if hasattr(tokenizer, 'decode') and hasattr(tokenizer, 'vocab_size'):
                cont = tokenizer.decode(ot)
            else:
                cont = tokenizer.decode(ot)
            if cont:
                full_text += cont
            else:
                break

        # 更新冷却时间（只在成功时）
        _last_text_time = time.time()

        return [TextContent(type="text", text=full_text)]

    except Exception as e:
        # 失败不更新冷却时间
        return [TextContent(type="text", text=f"文本生成失败: {str(e)}")]


# ==================== 启动 ====================

async def main():
    init_novelai_client()
    init_tokenizers()
    print(f"NovelAI MCP Server 启动，API Key: {'已配置' if NOVELAI_API_KEY else '未配置'}", flush=True)
    print(f"已加载 tokenizer: {list(tokenizers.keys())}", flush=True)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
