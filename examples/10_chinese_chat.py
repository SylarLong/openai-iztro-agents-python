"""示例 10 — 用中文对话（Chinese conversation）。

紫微斗数本来就是中文的。这个例子展示：你可以全程用中文提问，智能体也用中文回答；
你自己写的工具函数可以保存中文内容（函数名用英文，符合代码规范）。

────────────────────────────────────────────────────────────────────────────
运行  RUN IT       python examples/10_chinese_chat.py
你会看到 WHAT YOU'LL SEE   一段中文性格分析，以及一条被“记录”下来的中文笔记。
────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os
import sys

# Windows 终端默认可能不是 UTF-8，这一行让中文正常打印。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from agents import Runner

from iztro_agents import function_tool, iztro_ziwei_agent

API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"

notebook: list[str] = []  # 一个假装的笔记本，真实项目里可换成数据库


@function_tool
def save_note(title: str, content: str) -> str:
    """把一条笔记保存到用户的笔记本里。

    Args:
        title: 笔记的标题，例如“流年运势”。
        content: 笔记的正文。
    """
    print(f"  [本地函数执行] save_note(title={title!r}, content={content!r})")
    notebook.append(f"《{title}》{content}")
    return f"已记录：《{title}》"


async def main() -> None:
    agent = iztro_ziwei_agent(
        tools=[save_note],
        instructions="你是一位温暖、鼓励人心的紫微斗数顾问，请用简体中文回答，语气亲切。",
        api_key=API_KEY,
    )

    result = await Runner.run(
        agent,
        "我出生于 1990 年 6 月 15 日上午 10 点，男性。"
        "请用三句话分析我的性格，并把要点用 save_note 工具记下来。",
    )

    # 多轮调用，汇总每次模型调用在服务端跑过的 iztro 工具
    used = [t for r in result.raw_responses for t in r.iztro_tools]
    print("\n🔮 已调用 iztro：", "、".join(dict.fromkeys(used)))
    print("\n=== 最终回复 ===")
    print(result.final_output)
    print("\n笔记本里现在有：", notebook)


if __name__ == "__main__":
    asyncio.run(main())
