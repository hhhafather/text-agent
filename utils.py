import json
import streamlit as st

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

PROMPT_TEMPLATE = """你是一位专业的数据分析助手，你的回应内容严格取决于用户的请求内容。请始终遵循以下步骤和格式规范：

1.  **思考阶段 (Thought)**：
    * 首先，仔细分析用户请求的意图和类型（是需要纯文字回答、表格数据、还是特定类型的图表？）。
    * 其次，验证提供的数据集是否足以满足用户请求，以及数据类型是否与所需的分析或图表类型匹配。

2.  **行动阶段 (Action)**：
    * 根据你的分析结果，严格选择以下对应的JSON格式进行输出。**只返回一个JSON对象**。

    * **纯文字回答**: 当用户只寻求文字解释或总结时使用。
        ```json
        {"answer": "这里是您的简明答案，不超过50个字符。"}
        ```

    * **表格数据**: 当用户需要展示处理后的数据表格时使用。
        ```json
        {"table": {"columns": ["列名1", "列名2", ...], "data": [["第一行值1", "值2", ...], ["第二行值1", "值2", ...]]}}
        ```

    * **柱状图数据**: 当用户请求柱状图时使用。
        ```json
        {"bar": {"columns": ["类别1", "类别2", ...], "data": [数值1, 数值2, ...]}}
        ```

    * **折线图数据**: 当用户请求折线图时使用。
        ```json
        {"line": {"columns": ["点名1", "点名2", ...], "data": [数值1, 数值2, ...]}}
        ```

    * **饼图数据**: 当用户请求饼图时使用。
        ```json
        {"pie": {"columns": ["扇区1", "扇区2", ...], "data": [数值1, 数值2, ...]}}
        ```

3.  **格式校验要求 (Format Validation)**：
    * 所有字符串值（包括列名、答案文本、类别名称等）必须使用英文双引号 `"` 进行包裹。
    * 数值类型不得添加引号。
    * 确保所有数组和JSON对象都正确闭合，没有遗漏。
    * **错误案例**：`{'columns':['Product', 'Sales'], data:[[A001, 200]]}`
    * **正确案例**：`{"columns": ["product", "sales"], "data": [["A001", 200]]}`

注意：响应数据的 "output" 字段中不要包含任何换行符、制表符或任何其他非JSON格式的符号。你的最终输出必须是一个可以直接被 `json.loads()` 解析的有效JSON字符串。

当前用户请求如下：
"""


def dataframe_agent(df, query):
    model = ChatOpenAI(
        model='gpt-4.1-mini',
        base_url='https://twapi.openai-hk.com/v1',
        api_key=st.secrets["API_KEY"],
        temperature=0,
        max_tokens=8192

    )
    agent = create_pandas_dataframe_agent(
        llm=model,
        df=df,
        agent_executor_kwargs={"handle_parsing_errors": True},
        max_iterations=32,
        allow_dangerous_code=True,
        verbose=True
    )

    prompt = PROMPT_TEMPLATE + query

    try:
        response = agent.invoke({"input": prompt})
        return json.loads(response["output"])
    except Exception as err:
        print(err)
        return {"answer": "暂时无法提供分析结果，请稍后重试！"}
