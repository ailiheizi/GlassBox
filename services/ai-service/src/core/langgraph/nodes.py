"""
LangGraph 节点实现
Planner/Executor/Reviewer 三个核心节点
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from .state import AgentState, PlanStep, ActionRecord


class PlannerNode:
    """
    规划节点
    负责分析任务并生成执行计划
    支持注入匹配的技能到 system prompt
    """

    def __init__(self, llm_client, skill_selector=None):
        self.llm = llm_client
        self.skill_selector = skill_selector
        self.system_prompt = """你是一个任务规划专家。你的职责是分析用户任务，并生成详细的执行计划。

## 输入
- 用户任务描述
- 当前屏幕截图（如果有）
- 之前的执行历史（如果有）

## 输出格式
请输出 JSON 格式的执行计划：
```json
{
    "analysis": "任务分析",
    "plan": [
        {
            "step_id": 1,
            "description": "步骤描述",
            "tool": "工具名称",
            "args": {"参数": "值"}
        }
    ],
    "reasoning": "规划理由"
}
```

## 沙箱环境说明
沙箱是一个 Debian 12 精简环境（Xvfb + Chromium + CDP），**根文件系统为只读**，请注意以下约束：

### 预装软件（直接使用，无需安装）
- **浏览器**: chromium（通过 CDP 远程调试控制）
- **编程语言**: Python 3 (python3/pip3), Node.js (node/npm)
- **编辑器**: vim, nano
- **工具**: git, curl, wget, htop, tmux
- **中文支持**: 已配置中文字体和 locale

### 重要约束
- **禁止 apt-get/apt install**：根文件系统只读，无法安装系统包
- **pip install 可用**：使用 `pip3 install --break-system-packages <包名>` 安装 Python 包（安装到用户目录）
- **可写目录**: /tmp, /home/sandbox/workspace（工作目录）, /home/sandbox/.cache, /home/sandbox/.local
- 用户为 `sandbox`，无 sudo 权限

## 可用工具
- sandbox_shell: 执行 shell 命令，参数 {"command": "命令"}
- sandbox_browser_use: 智能浏览器操作（推荐），参数 {"task": "任务描述"}
- sandbox_bash_execute: 持久化会话执行命令，参数 {"command": "命令"}
- sandbox_file_list: 列出目录，参数 {"path": "目录路径"}
- sandbox_file_read: 读取文件，参数 {"path": "文件路径"}
- sandbox_file_write: 写入文件，参数 {"path": "路径", "content": "内容"}
- sandbox_screenshot: 获取浏览器截图
- sandbox_wait: 等待，参数 {"seconds": 秒数}

## 规划原则
1. 优先使用已预装的软件，不要尝试安装系统包
2. 浏览器/网页任务优先使用 sandbox_browser_use
3. 命令行任务优先使用 sandbox_shell 或 sandbox_bash_execute
4. 文件操作使用 sandbox_file_read/write
5. 每个步骤应该是原子操作
6. 考虑可能的失败情况
7. 步骤数量控制在 10 步以内"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """执行规划"""
        # 查询匹配的技能并注入 system prompt
        system_prompt = self.system_prompt
        if self.skill_selector:
            try:
                matched_skills = await self.skill_selector.select(
                    message=state["task"], top_k=5
                )
                if matched_skills:
                    skills_text = "\n## 相关技能\n以下技能与当前任务相关，请优先参考：\n"
                    for skill in matched_skills:
                        steps_str = json.dumps(skill.get("steps", []), ensure_ascii=False)
                        skills_text += f"- {skill['name']}: {skill['description']}\n  步骤: {steps_str}\n"
                    system_prompt = system_prompt + "\n" + skills_text
            except Exception:
                pass  # skill 查询失败不影响规划

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # 构建用户消息
        user_content = f"任务：{state['task']}\n"

        if state.get("actions"):
            user_content += "\n已执行的操作：\n"
            for action in state["actions"][-5:]:
                status = "成功" if action.get("success") else "失败"
                user_content += f"- {action['action_type']}: {status}\n"

        if state.get("review_feedback"):
            user_content += f"\n审查反馈：{state['review_feedback']}\n"
            user_content += "请根据反馈调整计划。\n"

        # 添加截图（如果有）
        if state.get("screenshot"):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{state['screenshot']}"
                        }
                    }
                ]
            })
        else:
            messages.append({"role": "user", "content": user_content})

        # 调用 LLM
        try:
            response = await self.llm.chat(messages=messages, max_tokens=2048)
            content = response.get("content", "")

            # 解析 JSON
            plan_data = self._parse_plan(content)

            # 构建计划步骤
            plan_steps: List[PlanStep] = []
            for step in plan_data.get("plan", []):
                plan_steps.append(PlanStep(
                    step_id=step.get("step_id", len(plan_steps) + 1),
                    description=step.get("description", ""),
                    tool=step.get("tool"),
                    args=step.get("args"),
                    status="pending",
                    result=None
                ))

            return {
                "status": "executing",
                "plan": plan_steps,
                "current_step": 0,
                "thinking": plan_data.get("analysis", ""),
                "reasoning": plan_data.get("reasoning", ""),
                "iteration": state["iteration"] + 1,
            }

        except Exception as e:
            return {
                "status": "failed",
                "error": f"Planning failed: {str(e)}",
            }

    def _parse_plan(self, content: str) -> Dict[str, Any]:
        """解析 LLM 输出的计划"""
        # 尝试提取 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 返回默认结构
        return {
            "analysis": content,
            "plan": [],
            "reasoning": "无法解析计划"
        }


class ExecutorNode:
    """
    执行节点
    负责执行计划中的步骤
    """

    def __init__(self, sandbox_client):
        self.sandbox_client = sandbox_client

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """执行当前步骤"""
        plan = state.get("plan", [])
        current_step = state.get("current_step", 0)

        if current_step >= len(plan):
            # 所有步骤执行完毕
            return {
                "status": "reviewing",
                "current_step": current_step,
            }

        step = plan[current_step]
        tool_name = step.get("tool")
        tool_args = step.get("args", {})

        # 更新步骤状态
        updated_plan = list(plan)
        updated_plan[current_step] = {**step, "status": "executing"}

        # 执行工具
        action_record = ActionRecord(
            step=current_step + 1,
            action_type=step.get("description", "unknown"),
            tool_name=tool_name,
            tool_args=tool_args,
            result=None,
            success=False,
            error=None,
            timestamp=datetime.now().isoformat()
        )

        try:
            if tool_name:
                # 调用沙箱工具
                result = await self._execute_tool(
                    state["user_id"],
                    tool_name,
                    tool_args
                )

                action_record["result"] = result
                action_record["success"] = result.get("status") == "ok"

                if result.get("status") != "ok":
                    action_record["error"] = result.get("error")

                updated_plan[current_step] = {
                    **step,
                    "status": "completed" if action_record["success"] else "failed",
                    "result": result
                }
            else:
                # 无工具步骤，直接标记完成
                action_record["success"] = True
                updated_plan[current_step] = {**step, "status": "completed"}

        except Exception as e:
            action_record["error"] = str(e)
            updated_plan[current_step] = {**step, "status": "failed", "result": str(e)}

        # 获取新截图
        screenshot = None
        screenshot_width = None
        screenshot_height = None

        try:
            screenshot_data = await self.sandbox_client.get_screenshot(state["user_id"])
            screenshot = screenshot_data.get("image")
            screenshot_width = screenshot_data.get("width")
            screenshot_height = screenshot_data.get("height")
        except:
            pass

        # 决定下一步
        next_step = current_step + 1
        next_status = "executing" if next_step < len(plan) else "reviewing"

        return {
            "plan": updated_plan,
            "current_step": next_step,
            "status": next_status,
            "actions": [action_record],
            "screenshot": screenshot,
            "screenshot_width": screenshot_width,
            "screenshot_height": screenshot_height,
        }

    async def _execute_tool(
        self,
        user_id: str,
        tool_name: str,
        tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行沙箱工具"""
        # 映射工具名称
        tool_mapping = {
            "sandbox_shell": "shell",
            "sandbox_wait": "wait",
        }

        actual_tool = tool_mapping.get(tool_name, tool_name)

        result = await self.sandbox_client.execute_tool(
            user_id=user_id,
            tool=actual_tool,
            params=tool_args
        )

        # ToolResult 是 Pydantic BaseModel，需要转为 dict
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        elif hasattr(result, 'dict'):
            return result.dict()
        return result


class ReviewerNode:
    """
    审查节点
    负责审查执行结果并决定是否需要重新规划
    """

    def __init__(self, llm_client):
        self.llm = llm_client
        self.system_prompt = """你是一个任务审查专家。你的职责是审查任务执行结果，判断任务是否完成。

## 输入
- 原始任务描述
- 执行计划和结果
- 当前屏幕截图

## 输出格式
请输出 JSON 格式的审查结果：
```json
{
    "passed": true/false,
    "feedback": "审查反馈",
    "suggestions": ["改进建议1", "改进建议2"],
    "reasoning": "判断理由"
}
```

## 审查标准
1. 任务目标是否达成
2. 执行过程是否有错误
3. 最终状态是否符合预期

## 判断原则
- 如果任务明确完成，passed 为 true
- 如果有明显错误或未完成，passed 为 false
- 提供具体的改进建议"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """执行审查"""
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]

        # 构建审查内容
        user_content = f"原始任务：{state['task']}\n\n"

        user_content += "执行计划和结果：\n"
        for step in state.get("plan", []):
            status_icon = "✓" if step.get("status") == "completed" else "✗"
            user_content += f"{status_icon} {step.get('description', 'unknown')}\n"
            if step.get("result"):
                result_str = str(step["result"])[:200]
                user_content += f"   结果: {result_str}\n"

        user_content += f"\n迭代次数：{state.get('iteration', 0)}/{state.get('max_iterations', 5)}\n"

        # 添加截图
        if state.get("screenshot"):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{state['screenshot']}"
                        }
                    }
                ]
            })
        else:
            messages.append({"role": "user", "content": user_content})

        # 调用 LLM
        try:
            response = await self.llm.chat(messages=messages, max_tokens=1024)
            content = response.get("content", "")

            # 解析结果
            review_data = self._parse_review(content)

            return {
                "review_passed": review_data.get("passed", False),
                "review_feedback": review_data.get("feedback", ""),
                "review_suggestions": review_data.get("suggestions", []),
                "reasoning": review_data.get("reasoning", ""),
            }

        except Exception as e:
            return {
                "review_passed": False,
                "review_feedback": f"Review failed: {str(e)}",
                "review_suggestions": [],
            }

    def _parse_review(self, content: str) -> Dict[str, Any]:
        """解析审查结果"""
        # 尝试提取 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 基于关键词判断
        passed = any(kw in content.lower() for kw in ["完成", "成功", "passed", "true"])

        return {
            "passed": passed,
            "feedback": content,
            "suggestions": [],
            "reasoning": "基于关键词判断"
        }
