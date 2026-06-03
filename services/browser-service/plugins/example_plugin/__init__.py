"""
示例插件 - 网页内容提取工具

演示如何创建自定义工具插件
"""
from typing import Dict, Any, List

from src.core.tools.plugin import (
    ToolPlugin,
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ToolRegistry,
)


class ExtractTextTool(ToolPlugin):
    """
    提取页面文本工具

    从当前页面提取指定选择器的文本内容
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="extract_text",
            description="从页面提取指定元素的文本内容",
            category=ToolCategory.CUSTOM,
            parameters=[
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS选择器，用于定位要提取文本的元素",
                    required=True,
                ),
                ToolParameter(
                    name="multiple",
                    type="boolean",
                    description="是否提取所有匹配元素的文本",
                    default=False,
                ),
                ToolParameter(
                    name="include_html",
                    type="boolean",
                    description="是否包含HTML标签",
                    default=False,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        selector = arguments["selector"]
        multiple = arguments.get("multiple", False)
        include_html = arguments.get("include_html", False)

        try:
            page = browser.page
            if not page:
                return {"success": False, "error": "No active page"}

            if multiple:
                elements = await page.query_selector_all(selector)
                if include_html:
                    texts = [await el.inner_html() for el in elements]
                else:
                    texts = [await el.inner_text() for el in elements]
                return {"success": True, "texts": texts, "count": len(texts)}
            else:
                element = await page.query_selector(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}

                if include_html:
                    text = await element.inner_html()
                else:
                    text = await element.inner_text()
                return {"success": True, "text": text}

        except Exception as e:
            return {"success": False, "error": str(e)}


class ExtractLinksTool(ToolPlugin):
    """
    提取页面链接工具

    从当前页面提取所有链接
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="extract_links",
            description="从页面提取所有链接",
            category=ToolCategory.CUSTOM,
            parameters=[
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS选择器，限定提取范围（可选）",
                    required=False,
                ),
                ToolParameter(
                    name="filter_pattern",
                    type="string",
                    description="URL过滤正则表达式（可选）",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="最大返回数量",
                    default=50,
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        import re

        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        selector = arguments.get("selector", "a")
        filter_pattern = arguments.get("filter_pattern")
        limit = arguments.get("limit", 50)

        try:
            page = browser.page
            if not page:
                return {"success": False, "error": "No active page"}

            # 提取所有链接
            links = await page.evaluate(f"""
                () => {{
                    const elements = document.querySelectorAll('{selector}');
                    return Array.from(elements).map(el => ({{
                        href: el.href,
                        text: el.innerText.trim(),
                        title: el.title || ''
                    }})).filter(link => link.href);
                }}
            """)

            # 应用过滤
            if filter_pattern:
                pattern = re.compile(filter_pattern)
                links = [link for link in links if pattern.search(link["href"])]

            # 限制数量
            links = links[:limit]

            return {"success": True, "links": links, "count": len(links)}

        except Exception as e:
            return {"success": False, "error": str(e)}


class ExtractTableTool(ToolPlugin):
    """
    提取表格数据工具

    从页面提取表格数据并转换为结构化格式
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="extract_table",
            description="从页面提取表格数据",
            category=ToolCategory.CUSTOM,
            parameters=[
                ToolParameter(
                    name="selector",
                    type="string",
                    description="表格的CSS选择器",
                    default="table",
                ),
                ToolParameter(
                    name="has_header",
                    type="boolean",
                    description="表格是否有表头",
                    default=True,
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description="输出格式: list (列表) 或 dict (字典，需要表头)",
                    default="dict",
                    enum=["list", "dict"],
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        selector = arguments.get("selector", "table")
        has_header = arguments.get("has_header", True)
        output_format = arguments.get("format", "dict")

        try:
            page = browser.page
            if not page:
                return {"success": False, "error": "No active page"}

            # 提取表格数据
            table_data = await page.evaluate(f"""
                () => {{
                    const table = document.querySelector('{selector}');
                    if (!table) return null;

                    const rows = Array.from(table.querySelectorAll('tr'));
                    return rows.map(row => {{
                        const cells = Array.from(row.querySelectorAll('th, td'));
                        return cells.map(cell => cell.innerText.trim());
                    }});
                }}
            """)

            if not table_data:
                return {"success": False, "error": f"Table not found: {selector}"}

            if output_format == "list":
                return {"success": True, "data": table_data, "rows": len(table_data)}

            # 转换为字典格式
            if has_header and len(table_data) > 0:
                headers = table_data[0]
                rows = table_data[1:]
                data = [
                    {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                    for row in rows
                ]
                return {"success": True, "headers": headers, "data": data, "rows": len(data)}
            else:
                return {"success": True, "data": table_data, "rows": len(table_data)}

        except Exception as e:
            return {"success": False, "error": str(e)}


class FillFormTool(ToolPlugin):
    """
    表单填写工具

    自动填写表单字段
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="fill_form",
            description="自动填写表单字段",
            category=ToolCategory.CUSTOM,
            parameters=[
                ToolParameter(
                    name="fields",
                    type="object",
                    description="字段映射，格式: {选择器: 值}",
                    required=True,
                ),
                ToolParameter(
                    name="submit",
                    type="boolean",
                    description="填写后是否提交表单",
                    default=False,
                ),
                ToolParameter(
                    name="submit_selector",
                    type="string",
                    description="提交按钮的选择器",
                    default="button[type='submit'], input[type='submit']",
                ),
            ],
        )

    async def execute(self, user_id: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        browser = context.get("browser")
        if not browser:
            return {"success": False, "error": "Browser not available"}

        fields = arguments.get("fields", {})
        submit = arguments.get("submit", False)
        submit_selector = arguments.get("submit_selector", "button[type='submit'], input[type='submit']")

        try:
            page = browser.page
            if not page:
                return {"success": False, "error": "No active page"}

            filled = []
            errors = []

            for selector, value in fields.items():
                try:
                    element = await page.query_selector(selector)
                    if not element:
                        errors.append(f"Field not found: {selector}")
                        continue

                    # 获取元素类型
                    tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                    input_type = await element.evaluate("el => el.type || ''")

                    if tag_name == "select":
                        await element.select_option(value)
                    elif input_type in ["checkbox", "radio"]:
                        if value:
                            await element.check()
                        else:
                            await element.uncheck()
                    else:
                        await element.fill(value)

                    filled.append(selector)

                except Exception as e:
                    errors.append(f"{selector}: {str(e)}")

            # 提交表单
            submitted = False
            if submit and filled:
                try:
                    submit_btn = await page.query_selector(submit_selector)
                    if submit_btn:
                        await submit_btn.click()
                        submitted = True
                except Exception as e:
                    errors.append(f"Submit failed: {str(e)}")

            return {
                "success": len(errors) == 0,
                "filled": filled,
                "errors": errors,
                "submitted": submitted,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# 注册所有插件
def register_plugins():
    """注册示例插件"""
    plugins = [
        ExtractTextTool(),
        ExtractLinksTool(),
        ExtractTableTool(),
        FillFormTool(),
    ]

    for plugin in plugins:
        ToolRegistry.register(plugin)


# 模块加载时自动注册
register_plugins()
