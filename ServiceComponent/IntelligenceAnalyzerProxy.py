import datetime
import os
import re
import json
import time
import uuid
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ValidationError

from MyPythonUtility.DictTools import dict_list_to_markdown
from prompts import ANALYSIS_PROMPT
from Tools.OpenAIClient import OpenAICompatibleAPI


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AIMessage(BaseModel):
    UUID: str
    content: str
    title: str | None = None
    authors: List[str] = []
    pub_time: object | None = None
    informant: str | None = None


def extract_pure_response(text: str):
    while '<think>' in text and '</think>' in text:
        start_idx = text.find('<think>')
        end_idx = text.find('</think>', start_idx) + len('</think>')
        text = text[:start_idx] + text[end_idx:]
    text = text.replace('<answer>', '').replace('</answer>', '')
    return text.strip()


def extract_pure_json_text(text: str):
    return text.strip().removeprefix('```json').removesuffix('```').strip()


def record_conversation(folder: str, messages: list, response: dict):
    folder_path = os.path.join('conversation', folder)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"conversation_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.txt")

    with open(file_path, 'wt', encoding='utf-8') as f:
        f.write("[system]\n\n")
        f.write(messages[0]['content'])

        f.write("\n\n")
        f.write("[user]\n\n")
        f.write(messages[1]['content'])

        f.write("\n\n")
        f.write("[reply]\n\n")
        if isinstance(response, Dict) and "choices" in response:
            f.write(response["choices"][0]["message"]["content"])
        else:
            f.write('<None>')


def parse_ai_response(response: dict):
    if isinstance(response, Dict) and "choices" in response:
        ai_output = response["choices"][0]["message"]["content"]
        ai_answer = extract_pure_response(ai_output)
        ai_json = extract_pure_json_text(ai_answer)
        try:
            parsed_output = json.loads(ai_json)
            return parsed_output
        except json.JSONDecodeError:
            return {'error': "Cannot parse AI response to JSON."}
    else:
        return {'error': "Invalid AI response."}


def analyze_with_ai(
        api_client: OpenAICompatibleAPI,
        prompt: str,
        structured_data: Dict[str, Any],
        context: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Use the OpenAI API to analyze the input prompt and structured data, and return a formatted JSON result.

    Args:
    api_client (OpenAICompatibleAPI): Provides a client instance of the OpenAI compatible API.
    prompt (str): The main prompt, used to specify the role and rules for analysis.
    structured_data (Dict[str, Any]): Structured data, which must contain the 'content' field of the main content.
    context (Optional[List[Dict[str, str]]]): Dialogue context, optional.

    Returns:
    Dict[str, Any]: JSON object processed by AI, converted to a Python dictionary.
    """
    try:
        sanitized_data = AIMessage.model_validate(structured_data).model_dump(exclude_unset=True, exclude_none=True)
    except ValidationError as e:
        logger.error(f'AI require data field missing: {str(e)}')
        return {'error': str(e)}
    except Exception as e:
        logger.error(f'Validate AI data fail: {str(e)}')
        return {'error': str(e)}

    metadata_items = [f"- {k}: {v}" for k, v in sanitized_data.items() if k != "content"]
    metadata_block = '## metadata\n' + "\n".join(metadata_items)
    content_block = f"\n\n## 正文内容\n{sanitized_data['content']}"
    user_message = metadata_block + content_block

    messages = context if context else []
    messages.append({"role": "system", "content": prompt})
    messages.append({"role": "user", "content": user_message})

    start = time.time()

    response = api_client.create_chat_completion_sync(
        messages=messages,
        temperature=0,
        max_tokens=5000
    )

    elapsed = time.time() - start
    print(f"AI response spends {elapsed} s")

    record_conversation('analysis', messages, response)
    return parse_ai_response(response)


def aggressive_by_ai(
        api_client: OpenAICompatibleAPI,
        prompt: str,
        new_data: Dict[str, Any],
        history_data: List[Dict[str, str]]
) -> Dict:
    new_data_text = \
        f"{new_data['EVENT_TITLE']}\n\n"\
        f"{new_data['EVENT_BRIEF']}\n\n"
    history_data_md_table = dict_list_to_markdown(history_data)

    user_message = \
        f"# 新情报\n {new_data_text}"\
        f"# 历史情报\n {history_data_md_table}"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_message}]

    start = time.time()

    response = api_client.create_chat_completion_sync(
        messages=messages,
        temperature=0,
        max_tokens=5000
    )

    elapsed = time.time() - start
    print(f"AI response spends {elapsed} s")

    record_conversation('aggressive', messages, response)
    return parse_ai_response(response)


def generate_recommendation_by_ai(
        api_client: OpenAICompatibleAPI,
        prompt: str,
        intelligence_list: List[Dict[str, str]]
) -> List[str]:

    intelligence_table = dict_list_to_markdown(intelligence_list)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": intelligence_table}]

    start = time.time()

    response = api_client.create_chat_completion_sync(
        messages=messages,
        temperature=0,
        max_tokens=5000
    )

    elapsed = time.time() - start
    print(f"AI response spends {elapsed} s")

    record_conversation('recommend', messages, response)
    return parse_ai_response(response)


# ----------------------------------------------------------------------------------------------------------------------

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


API_BASE_URL = ["http://localhost:11434",
                "https://api.siliconflow.cn"]

MODEL = ['qwen3:14b',
         'Qwen/Qwen3-235B-A22B']

def main():
    select_index = 0

    api_client = OpenAICompatibleAPI(
        api_base_url=API_BASE_URL[select_index],
        token='SleepySoft',
        default_model=MODEL[select_index])

    structured_data = {
        "UUID": str(uuid.uuid4()),
        "title": "Big streamers argue at CRTC hearing they shouldn't",
        "content": NEWS_TEXT
    }

    # 调用函数
    result = analyze_with_ai(api_client, ANALYSIS_PROMPT, structured_data)

    # 打印结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()




