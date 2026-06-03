"""
智能模型路由器
支持多个 API 提供商：SiliconFlow、DeepSeek、豆包（火山方舟）
"""
from typing import Dict, Any, Optional
from enum import Enum
import json
import os


class ModelProvider(str, Enum):
    """API 提供商"""
    SILICONFLOW = "siliconflow"  # SiliconFlow（免费视觉模型）
    DEEPSEEK = "deepseek"        # DeepSeek（文本对话、推理）
    DOUBAO = "doubao"            # 豆包/火山方舟（需要 endpoint_id）


class ModelType(str, Enum):
    """模型类型枚举"""
    # SiliconFlow 视觉模型（推荐，免费）
    SILICONFLOW_VISION = "siliconflow_vision"
    # DeepSeek 模型
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"
    # 豆包模型（需要 endpoint_id）
    DOUBAO_GUI = "doubao_gui"
    DOUBAO_VISION = "doubao_vision"


class TaskCategory(str, Enum):
    """任务类别"""
    GUI_OPERATION = "gui_operation"      # GUI 操作（点击、输入等）
    VISUAL_ANALYSIS = "visual_analysis"  # 视觉分析（理解截图内容）
    CODE_GENERATION = "code_generation"  # 代码生成
    REASONING = "reasoning"              # 复杂推理
    GENERAL_CHAT = "general_chat"        # 通用对话


class ModelRouter:
    """智能模型路由器"""

    # 关键词匹配规则（快速路由）
    KEYWORD_RULES = {
        TaskCategory.GUI_OPERATION: [
            "点击", "click", "双击", "右键", "输入", "type", "按键", "press",
            "滚动", "scroll", "拖拽", "drag", "打开", "open", "关闭", "close",
            "最大化", "最小化", "切换", "switch", "选择", "select"
        ],
        TaskCategory.VISUAL_ANALYSIS: [
            "看到", "显示", "截图", "画面", "界面", "窗口", "内容",
            "what do you see", "describe", "analyze", "观察", "屏幕"
        ],
        TaskCategory.CODE_GENERATION: [
            "写代码", "生成代码", "实现", "函数", "类", "方法",
            "write code", "generate", "implement", "function", "class"
        ],
        TaskCategory.REASONING: [
            "为什么", "如何", "分析", "推理", "解释", "原因",
            "why", "how", "analyze", "reason", "explain"
        ],
    }

    def __init__(self, deepseek_client=None):
        """
        初始化模型路由器

        Args:
            deepseek_client: DeepSeek 客户端，用于智能分析任务
        """
        self.deepseek_client = deepseek_client
        self._init_model_configs()

    def _init_model_configs(self):
        """初始化模型配置"""
        # 从环境变量读取配置
        self.siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY", "")
        self.siliconflow_base_url = os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")
        self.siliconflow_vision_model = os.getenv("SILICONFLOW_VISION_MODEL", "deepseek-ai/deepseek-vl2")

        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")

        self.doubao_api_key = os.getenv("DOUBAO_API_KEY", "")
        self.doubao_base_url = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
        self.doubao_gui_model = os.getenv("DOUBAO_GUI_MODEL", "")
        self.doubao_vision_model = os.getenv("DOUBAO_VISION_MODEL", "")

        # 确定可用的视觉模型提供商
        self._determine_vision_provider()

    def _determine_vision_provider(self):
        """确定可用的视觉模型提供商"""
        # 优先级：豆包 > SiliconFlow
        if self.doubao_api_key and (self.doubao_gui_model or self.doubao_vision_model):
            self.vision_provider = ModelProvider.DOUBAO
            self.vision_model = self.doubao_vision_model or self.doubao_gui_model
            self.vision_base_url = self.doubao_base_url
            self.vision_api_key = self.doubao_api_key
        elif self.siliconflow_api_key:
            self.vision_provider = ModelProvider.SILICONFLOW
            self.vision_model = self.siliconflow_vision_model
            self.vision_base_url = self.siliconflow_base_url
            self.vision_api_key = self.siliconflow_api_key
        else:
            # 默认使用豆包
            self.vision_provider = ModelProvider.DOUBAO
            self.vision_model = self.doubao_vision_model or "doubao-1-5-vision-pro-32k"
            self.vision_base_url = self.doubao_base_url
            self.vision_api_key = self.doubao_api_key

    def get_task_model_mapping(self) -> Dict[TaskCategory, ModelType]:
        """获取任务类别到模型的映射"""
        # 根据可用的提供商动态确定映射
        if self.vision_provider == ModelProvider.DOUBAO:
            vision_model = ModelType.DOUBAO_VISION if self.doubao_vision_model else ModelType.DOUBAO_GUI
        elif self.vision_provider == ModelProvider.SILICONFLOW:
            vision_model = ModelType.SILICONFLOW_VISION
        else:
            vision_model = ModelType.DOUBAO_VISION

        return {
            TaskCategory.GUI_OPERATION: ModelType.DOUBAO_GUI if self.doubao_gui_model else vision_model,
            TaskCategory.VISUAL_ANALYSIS: vision_model,
            TaskCategory.CODE_GENERATION: ModelType.DEEPSEEK_CHAT,
            TaskCategory.REASONING: ModelType.DEEPSEEK_REASONER,
            TaskCategory.GENERAL_CHAT: ModelType.DEEPSEEK_CHAT,
        }

    def route_by_keywords(self, task: str) -> Optional[TaskCategory]:
        """
        基于关键词快速路由（不调用 LLM）

        Args:
            task: 任务描述

        Returns:
            任务类别，如果无法判断则返回 None
        """
        task_lower = task.lower()

        # 计算每个类别的匹配分数
        scores = {}
        for category, keywords in self.KEYWORD_RULES.items():
            score = sum(1 for keyword in keywords if keyword in task_lower)
            if score > 0:
                scores[category] = score

        # 返回得分最高的类别
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        return None

    async def route_by_llm(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        使用 DeepSeek 智能分析任务类别

        Args:
            task: 任务描述
            context: 额外上下文（如历史对话、截图描述等）

        Returns:
            {"category": TaskCategory, "llm_response": str, "reasoning": str}
        """
        if not self.deepseek_client:
            category = self.route_by_keywords(task)
            return {
                "category": category or TaskCategory.GENERAL_CHAT,
                "llm_response": "",
                "reasoning": "",
            }

        prompt = f"""分析以下任务，判断其类别，并简要说明理由。

任务描述：{task}

可选类别：
1. gui_operation - GUI 操作任务（点击、输入、拖拽等桌面操作）
2. visual_analysis - 视觉分析任务（理解截图内容、描述界面）
3. code_generation - 代码生成任务（编写代码、实现功能）
4. reasoning - 复杂推理任务（分析问题、解释原因）
5. general_chat - 通用对话（闲聊、问答）

请按以下格式返回：
类别：<类别名称>
理由：<简要说明为什么选择这个类别>"""

        if context:
            prompt += f"\n\n额外上下文：{json.dumps(context, ensure_ascii=False)}"

        try:
            response = await self.deepseek_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )

            raw_content = response.get("content", "").strip()
            reasoning = response.get("reasoning", "") or ""
            category_str = raw_content.lower()

            for category in TaskCategory:
                if category.value in category_str:
                    return {
                        "category": category,
                        "llm_response": raw_content,
                        "reasoning": reasoning,
                    }

            fallback = self.route_by_keywords(task) or TaskCategory.GENERAL_CHAT
            return {
                "category": fallback,
                "llm_response": raw_content,
                "reasoning": reasoning,
            }

        except Exception as e:
            print(f"[ModelRouter] LLM routing failed: {e}, fallback to keyword routing")
            fallback = self.route_by_keywords(task) or TaskCategory.GENERAL_CHAT
            return {
                "category": fallback,
                "llm_response": "",
                "reasoning": "",
            }

    async def select_model(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        use_llm_routing: bool = True
    ) -> Dict[str, Any]:
        """
        选择最合适的模型

        Args:
            task: 任务描述
            context: 额外上下文
            use_llm_routing: 是否使用 LLM 智能路由

        Returns:
            {
                "model": ModelType,
                "category": TaskCategory,
                "provider": ModelProvider,
                "confidence": float,
                "reason": str
            }
        """
        task_model_mapping = self.get_task_model_mapping()

        # 1. 尝试关键词快速路由
        keyword_category = self.route_by_keywords(task)

        if keyword_category and not use_llm_routing:
            model_type = task_model_mapping[keyword_category]
            return {
                "model": model_type,
                "category": keyword_category,
                "provider": self._get_provider_for_model(model_type),
                "confidence": 0.8,
                "reason": f"Keyword matching: {keyword_category.value}"
            }

        # 2. 使用 LLM 智能路由
        if use_llm_routing and self.deepseek_client:
            llm_result = await self.route_by_llm(task, context)
            llm_category = llm_result["category"]
            confidence = 0.95 if llm_category == keyword_category else 0.85
            model_type = task_model_mapping[llm_category]

            return {
                "model": model_type,
                "category": llm_category,
                "provider": self._get_provider_for_model(model_type),
                "confidence": confidence,
                "reason": f"LLM analysis: {llm_category.value}",
                "llm_response": llm_result["llm_response"],
                "llm_reasoning": llm_result["reasoning"],
            }

        # 3. 后备方案
        if keyword_category:
            model_type = task_model_mapping[keyword_category]
            return {
                "model": model_type,
                "category": keyword_category,
                "provider": self._get_provider_for_model(model_type),
                "confidence": 0.7,
                "reason": f"Keyword fallback: {keyword_category.value}"
            }

        # 4. 默认使用通用模型
        default_model = ModelType.DEEPSEEK_CHAT
        return {
            "model": default_model,
            "category": TaskCategory.GENERAL_CHAT,
            "provider": ModelProvider.DEEPSEEK,
            "confidence": 0.5,
            "reason": "Default model"
        }

    def _get_provider_for_model(self, model_type: ModelType) -> ModelProvider:
        """获取模型对应的提供商"""
        if model_type == ModelType.SILICONFLOW_VISION:
            return ModelProvider.SILICONFLOW
        elif model_type in [ModelType.DEEPSEEK_CHAT, ModelType.DEEPSEEK_REASONER]:
            return ModelProvider.DEEPSEEK
        elif model_type in [ModelType.DOUBAO_GUI, ModelType.DOUBAO_VISION]:
            return ModelProvider.DOUBAO
        else:
            return ModelProvider.DEEPSEEK

    def get_model_config(self, model_type: ModelType) -> Dict[str, Any]:
        """
        获取模型配置

        Args:
            model_type: 模型类型

        Returns:
            模型配置字典
        """
        configs = {
            ModelType.SILICONFLOW_VISION: {
                "model": self.siliconflow_vision_model,
                "base_url": self.siliconflow_base_url,
                "api_key": self.siliconflow_api_key,
                "max_tokens": 4096,
                "temperature": 0.7,
                "supports_vision": True,
                "supports_tools": True,
                "provider": ModelProvider.SILICONFLOW,
            },
            ModelType.DEEPSEEK_CHAT: {
                "model": "deepseek-chat",
                "base_url": self.deepseek_base_url,
                "api_key": self.deepseek_api_key,
                "max_tokens": 4096,
                "temperature": 0.7,
                "supports_vision": False,
                "supports_tools": True,
                "provider": ModelProvider.DEEPSEEK,
            },
            ModelType.DEEPSEEK_REASONER: {
                "model": "deepseek-reasoner",
                "base_url": self.deepseek_base_url,
                "api_key": self.deepseek_api_key,
                "max_tokens": 8192,
                "temperature": 0.7,
                "supports_vision": False,
                "supports_tools": False,
                "provider": ModelProvider.DEEPSEEK,
            },
            ModelType.DOUBAO_GUI: {
                "model": self.doubao_gui_model,
                "base_url": self.doubao_base_url,
                "api_key": self.doubao_api_key,
                "max_tokens": 4096,
                "temperature": 0.1,
                "supports_vision": True,
                "supports_tools": True,
                "provider": ModelProvider.DOUBAO,
            },
            ModelType.DOUBAO_VISION: {
                "model": self.doubao_vision_model,
                "base_url": self.doubao_base_url,
                "api_key": self.doubao_api_key,
                "max_tokens": 4096,
                "temperature": 0.7,
                "supports_vision": True,
                "supports_tools": True,
                "provider": ModelProvider.DOUBAO,
            },
        }

        return configs.get(model_type, configs[ModelType.DEEPSEEK_CHAT])

    # 工具集合：用于中途切换判断
    _GUI_TOOLS = {"sandbox_click", "sandbox_double_click", "sandbox_type",
                  "sandbox_key", "sandbox_scroll", "sandbox_move",
                  "sandbox_browser", "sandbox_hybrid_click"}
    _CODE_TOOLS = {"sandbox_shell", "sandbox_bash_execute", "sandbox_terminal"}
    # browser-use 通过 DOM 操作，不需要视觉模型，路由到 DeepSeek
    _BROWSER_USE_TOOLS = {"sandbox_browser_use"}

    def should_switch_to_vision(self, current_provider: str, last_tool: str) -> bool:
        """上一步执行了 GUI 工具 → 下一步需要看屏幕确认结果。
        browser-use 工具自带 DOM 反馈，不需要切换到视觉模型。"""
        if last_tool in self._BROWSER_USE_TOOLS:
            return False
        return current_provider != "doubao" and last_tool in self._GUI_TOOLS

    def should_switch_to_text(self, current_provider: str, last_tool: str) -> bool:
        """上一步执行了代码工具或 browser-use → 不需要视觉，切回 DeepSeek。"""
        if last_tool in self._BROWSER_USE_TOOLS:
            return current_provider == "doubao"
        return current_provider == "doubao" and last_tool in self._CODE_TOOLS

    def get_available_providers(self) -> Dict[str, bool]:
        """获取可用的提供商状态"""
        return {
            "siliconflow": bool(self.siliconflow_api_key),
            "deepseek": bool(self.deepseek_api_key),
            "doubao": bool(self.doubao_api_key and (self.doubao_gui_model or self.doubao_vision_model)),
        }

    def get_vision_config(self) -> Dict[str, Any]:
        """获取当前视觉模型配置"""
        return {
            "provider": self.vision_provider.value,
            "model": self.vision_model,
            "base_url": self.vision_base_url,
            "api_key_configured": bool(self.vision_api_key),
        }
