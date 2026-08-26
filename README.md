# Minimal Qwen Agent

一个用 Python 编写的极简 Agent harness，用来展示最核心的 Agent Loop：
模型根据任务决定是否调用工具，程序执行工具并返回结果，模型继续推理，直到给出最终答案。

## 设计思想

这个项目追求简单、清晰和可替换：

- Agent Loop 只负责消息流转、工具执行和循环控制，不依赖具体模型。
- `conversation.json` 使用 harness 自己的统一消息格式，不保存某个模型专用的 prompt 文本。
- 模型协议负责在统一消息与模型原生格式之间进行转换。目前的 `QwenProtocol` 负责 Qwen chat template 的渲染与输出解析。
- 推理后端只接收完整 context 并返回原始文本。目前使用 vLLM 的 Completions API。
- 工具通过统一的 `Tool` 接口注册，可以独立增加或删除。

因此，接入工具调用格式不同的新模型时，主要新增对应的 protocol；Agent Loop 和工具实现通常不需要改变。

## 支持的模型

当前支持并配置的是：

- Qwen3.8-27B
- vLLM 推理后端

默认配置位于 `main.py`：

```python
MODEL_PATH = "/data4/haibo/weights/Qwen3.8-27B"
VLLM_MODEL_NAME = "qwen3.8-27b"
VLLM_BASE_URL = "http://127.0.0.1:8000/v1"
```

`MODEL_PATH` 用于读取 tokenizer 和 chat template，`VLLM_MODEL_NAME` 必须与 vLLM 的 `--served-model-name` 一致。

## 支持的工具

- `read`：读取 UTF-8 文本文件。
- `bash`：执行 Bash 命令。
- `edit`：替换文件中唯一匹配的文本块。
- `write`：创建或覆盖 UTF-8 文本文件。
- `web_search`：通过 DuckDuckGo 搜索网页。

这些工具直接使用运行 `main.py` 的进程权限，没有额外的沙箱或人工确认机制，请在受控环境中运行。

## 安装

建议分别创建 vLLM 服务端环境和 Agent 客户端环境。

安装 vLLM：

```bash
conda create -n vllm python=3.12 -y
conda activate vllm
python -m pip install --upgrade pip uv
uv pip install vllm --torch-backend=auto
```

安装 Agent 客户端：

```bash
conda create -n pi_agent python=3.12 -y
conda activate pi_agent
cd /data4/haibo/code/pi_qwen
pip install -r requirements.txt
```

## 运行

先启动 vLLM 服务：

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve /data4/haibo/weights/Qwen3.8-27B \
    --served-model-name qwen3.8-27b \
    --host 127.0.0.1 \
    --port 8000 \
    --dtype bfloat16 \
    --tensor-parallel-size 1 \
    --max-model-len 262144 \
    --gpu-memory-utilization 0.90
```

然后在另一个终端运行 Agent：

```bash
conda activate pi_agent
cd /data4/haibo/code/pi_qwen
python main.py --prompt "搜索今天的重要 AI 新闻并总结"
```

也可以使用默认任务：

```bash
python main.py
```

最终答案打印在终端。结构化对话记录和完整模型 trace 分别保存在：

```text
./tmp/conversation.json
./tmp/trace.txt
```
