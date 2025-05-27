import openai
import streamlit as st

def get_gpt4o_response(api_key, messages):
    """
    使用GPT-4o模型获取回应。

    参数:
    - api_key (str): OpenAI API密钥。
    - messages (list): 对话历史消息列表，格式为:
                       [{"role": "user", "content": "你好"},
                        {"role": "assistant", "content": "你好！有什么可以帮您？"}]

    返回:
    - str: GPT-4o的回应内容，如果出错则返回None。
    """
    try:
        client = openai.OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model="gpt-4o",  # 或者您希望使用的特定模型如 "gpt-4o-2024-05-13"
            messages=messages
        )
        return completion.choices[0].message.content
    except Exception as e:
        st.error(f"调用OpenAI API时发生错误: {e}")
        return None

def generate_initial_analysis_prompt(file_content_str, user_instruction):
    """
    为文件的初次分析生成提示。
    """
    return f"""以下是用户提供的文件内容和处理指令。请根据指令分析文件内容。

用户指令：
{user_instruction}

文件内容：
---
{file_content_str}
---

请提供您的分析结果：
"""