import json
import time
import uuid
from typing import Optional, Dict, Any, List

from Tools.OpenAIClient import OpenAICompatibleAPI
from prompts import DEFAULT_ANALYSIS_PROMPT


def analyze_with_ai(
        api_client: OpenAICompatibleAPI,
        prompt: str,
        structured_data: Dict[str, Any],
        context: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    使用 OpenAI API 对输入的 prompt 和结构化数据进行分析，并返回格式化的 JSON 结果。

    Args:
        api_client (OpenAICompatibleAPI): 提供 OpenAI 兼容 API 的客户端实例。
        prompt (str): 主 prompt，用于指定分析的角色和规则。
        structured_data (Dict[str, Any]): 结构化数据，需包含主要内容的 'content' 字段。
        context (Optional[List[Dict[str, str]]]): 对话上下文，可选。

    Returns:
        Dict[str, Any]: AI 处理后的 JSON 对象，转为 Python 字典。
    """
    # 校验输入的结构化数据是否包含 'content'
    if "content" not in structured_data:
        raise ValueError("结构化数据必须包含 'content' 字段")

    # 生成唯一的 UUID，便于追踪分析
    analysis_uuid = str(uuid.uuid4())

    # 构造输入的对话消息
    messages = []

    # 如果有上下文，添加到消息中
    if context:
        messages.extend(context)

    # 添加系统角色设定
    messages.append({"role": "system", "content": prompt})

    # 添加用户输入的内容
    user_message = f"""
UUID: {analysis_uuid}
Title: {structured_data.get('title', '无标题')}
Content: {structured_data['content']}
"""
    messages.append({"role": "user", "content": user_message})

    start = time.perf_counter()

    # 调用 OpenAI API 的聊天接口
    response = api_client.create_chat_completion_sync(
        messages=messages,
        temperature=0,      # 确保输出结果的确定性
        max_tokens=3000     # 最大 token 数，根据需要调整
    )

    elapsed = time.perf_counter() - start
    print(f"AI response spends {elapsed:.6f}s")

    # 检查响应是否成功
    if isinstance(response, Dict) and "choices" in response:
        # 假设返回结果在 `choices[0].message.content` 中
        ai_output = response["choices"][0]["message"]["content"]

        # 尝试将结果解析为 JSON 字典
        try:
            parsed_output = json.loads(ai_output)
            return parsed_output
        except json.JSONDecodeError:
            raise ValueError("AI 返回的结果无法解析为 JSON")
    else:
        raise RuntimeError("AI 响应无效或请求失败")


NEWS_TEXT = """An industry group representing companies including Netflix argued on Friday that streamers should not have rules around Canadian content imposed on them. Netflix was also scheduled to appear at a hearing this week, but then cancelled its appearance. (Richard Drew/The Associated Press)

Social Sharing
A group representing major foreign streaming companies told a hearing held by Canada's broadcasting regulator on Friday that those companies shouldn't be expected to fulfil the same responsibilities as traditional broadcasters when it comes to Canadian content.

The Motion Picture Association-Canada, which represents large streamers like Netflix, Paramount, Disney and Amazon, said the regulator should be flexible in modernizing its definition of Canadian content.

The Canadian Radio-television and Telecommunications Commission (CRTC) is holding a two-week public hearing on a new definition of Canadian content that began Wednesday. The proceeding is part of its work to implement the Online Streaming Act — and it is bringing tensions between traditional players and large foreign streamers out in the open.

In a written copy of the statement being made at the hearing, MPA-Canada argued the Online Streaming Act, which updated broadcasting laws to capture online platforms, sets a lower standard for foreign online services.

Cancon funding debated
"The contribution standard applied to Canadian broadcasters is much greater and reflects their existing obligations," the group said in its opening remarks.

"This difference was intentional as Parliament rejected calls to impose the same standard because 'it is just not realistic' to expect foreign online undertakings operating in a global market to contribute in the same way as Canadian broadcasters."

MPA-Canada said the CRTC shouldn't impose "any mandatory positions, functions or elements of a 'Canadian program"' on global streaming services.

While the hearing is focused on the definition of Canadian content, the CRTC has also heard debate about financial contributions.

Canadian media company Corus suggested that Cancon funding requirements be eased on broadcasters, and that streamers follow the same rule. (Tijana Martin/The Canadian Press)

Earlier Friday, Canadian media company Corus urged the CRTC to require traditional broadcasters and online players to pay the same amount into the Canadian content system. The broadcaster, which owns Global TV, said both should contribute 20 per cent of their revenue toward Canadian content.

Currently, large English-language broadcasters must contribute 30 per cent of revenues to Canadian programming, and the CRTC last year ordered streaming services to pay five per cent of their annual Canadian revenues to a fund devoted to producing Canadian content.

The foreign streaming services are fighting that rule in court and Netflix, Paramount and Apple pulled out of the CRTC hearing earlier this week.

Streamers like Netflix, Disney Plus get court reprieve from paying for Canadian content

Controversial bill to regulate online streaming becomes law

MPA-Canada said that online services "should be allowed to fulfil their obligations through direct spending on production where that is consistent with their business model — not forced to pay into funds or into a program acquisition model that is inconsistent with how their services operate."

The CRTC has issued a preliminary position on the definition of Canadian content, suggesting it keep the current system for determining whether content is considered Canadian by awarding points when Canadians occupy key creative positions in a production.

The CRTC is considering expanding that system to allow more creative positions to count toward the total points. One of the topics of debate in the hearing is the position of "showrunner," which has become more significant in recent years.

MPA-Canada said that "adding just a few positions to a more than 40-year-old list ignores today's modern production landscape."""


def main():
    API_BASE_URL = "https://api.siliconflow.cn"

    api_client = (OpenAICompatibleAPI(
        api_base_url=API_BASE_URL,
        token='',
        default_model='Qwen/Qwen3-235B-A22B'))

    structured_data = {
        "title": "Big streamers argue at CRTC hearing they shouldn't",
        "content": NEWS_TEXT
    }

    # 调用函数
    result = analyze_with_ai(api_client, DEFAULT_ANALYSIS_PROMPT, structured_data)

    # 打印结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()




