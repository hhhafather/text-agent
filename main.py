# --- START OF FILE main.py ---

"""
main.py - 自助式数据分析（数据分析智能体）

Author: 骆昊
Version: 0.1.2 (Allow empty chart selection)
Date: 2025/6/26
"""
import os
import pickle
import uuid

import matplotlib.pyplot as plt
import openpyxl
import pandas as pd
import streamlit as st
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

from utils import dataframe_agent

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def create_chart(input_data, chart_type):
    """生成统计图表"""
    df_data = pd.DataFrame(
        data={
            "x": input_data["columns"],
            "y": input_data["data"]
        }
    ).set_index("x")
    if chart_type == "柱状图":
        plt.figure(figsize=(8, 5), dpi=120)
        plt.bar(input_data["columns"], input_data["data"], width=0.4, hatch='///')
        st.pyplot(plt.gcf())
    elif chart_type == "折线图":
        st.line_chart(df_data)
    elif chart_type == "饼图":
        plt.figure(figsize=(8, 8), dpi=120)
        plt.pie(input_data["data"], labels=input_data["columns"], autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        st.pyplot(plt.gcf())


# 使用 st.cache_data 缓存文件加载函数
@st.cache_data(show_spinner="正在加载数据...")
def load_data(file_path, file_type, sheet_name=None):
    """根据文件类型加载数据并返回DataFrame"""
    try:
        if file_type == 'xlsx' or file_type == 'xls':
            return pd.read_excel(file_path, sheet_name=sheet_name)
        elif file_type == 'csv':
            return pd.read_csv(file_path)
        elif file_type == 'pdf':
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            return pd.DataFrame({"Content": ["\n".join([doc.page_content for doc in documents])]})
        elif file_type == 'docx':
            loader = Docx2txtLoader(file_path)
            documents = loader.load()
            return pd.DataFrame({"Content": ["\n".join([doc.page_content for doc in documents])]})
        elif file_type == 'txt' or file_type == 'md':
            # 【修复】智能尝试多种编码加载文本文件
            try:
                # 优先尝试 UTF-8，因为它是最标准的编码
                loader = TextLoader(file_path, encoding='utf-8')
                documents = loader.load()
            except (UnicodeDecodeError, RuntimeError):
                # 如果 UTF-8 失败，回退尝试 GBK 编码，它在中国很常用
                loader = TextLoader(file_path, encoding='gbk')
                documents = loader.load()
            return pd.DataFrame({"Content": ["\n".join([doc.page_content for doc in documents])]})
        else:
            st.error(f"不支持的文件类型: {file_type}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"加载文件时发生错误: {e}")
        return pd.DataFrame()


# 使用 st.cache_resource 缓存 ConversationBufferMemory 和 EM 模型
@st.cache_resource
def get_memory_and_model():
    memory = ConversationBufferMemory(
        return_messages=True,
        memory_key='chat_history',
        input_key='question',
        output_key='answer'
    )
    em_model = None
    try:
        with open('em.pkl', 'rb') as file_obj:
            em_model = pickle.load(file_obj)
    except FileNotFoundError:
        st.warning("未找到 em.pkl。如果需要，请确保它在正确的目录中。")
    except Exception as e:
        st.error(f"加载 em.pkl 时出错: {e}")
    return memory, em_model


st.write("## 文档分析智能体")

# 获取缓存的 memory 和 em_model
st.session_state['memory'], st.session_state['em_model'] = get_memory_and_model()

if 'session_id' not in st.session_state:
    st.session_state['session_id'] = uuid.uuid4().hex
    st.session_state['is_new_file'] = True
    st.session_state['current_file_name'] = None  # 初始化

# 如果 'uploads' 目录不存在则创建它
if not os.path.exists('uploads'):
    os.makedirs('uploads')

with st.sidebar:
    option = st.radio("请选择数据文件类型:", ("Excel", "CSV", "txt", "pdf", "docx", "md"))

    file_type_map = {
        "Excel": ["xlsx", "xls"],
        "CSV": ["csv"],
        "txt": ["txt"],
        "pdf": ["pdf"],
        "docx": ["docx"],
        "md": ["md"]
    }

    # 根据所选选项确定文件上传器允许的文件类型
    allowed_file_types = file_type_map.get(option, ["csv"])

    data = st.file_uploader(f"上传你的{option}数据文件", type=allowed_file_types)

# 清除缓存的 DataFrame 如果上传了新文件
if data:
    if 'current_file_name' not in st.session_state or st.session_state['current_file_name'] != data.name:
        st.session_state['is_new_file'] = True
        st.session_state['current_file_name'] = data.name

        suffix = data.name[data.name.rfind('.'):].lower().replace('.', '')

        temp_file_path = os.path.join('uploads', f'{st.session_state["session_id"]}_{data.name}')

        # 【修复】统一使用二进制写入模式('wb')保存所有上传文件，以保留其原始字节，避免编码问题
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(data.read())

        sheet_name_to_load = None
        if suffix in ('xlsx', 'xls'):
            try:
                wb = openpyxl.load_workbook(temp_file_path)
                sheet_names = wb.sheetnames
                if sheet_names:
                    if 'selected_excel_sheet' in st.session_state and st.session_state[
                        'selected_excel_sheet'] in sheet_names:
                        default_sheet_index = sheet_names.index(st.session_state['selected_excel_sheet'])
                    else:
                        default_sheet_index = 0

                    selected_sheet = st.radio(label="请选择要加载的工作表：", options=sheet_names,
                                              index=default_sheet_index, key="excel_sheet_selector")
                    st.session_state['selected_excel_sheet'] = selected_sheet
                    sheet_name_to_load = selected_sheet
                else:
                    st.warning("Excel 文件中没有检测到工作表。")
            except Exception as e:
                st.error(f"读取Excel工作表时出错: {e}")

        st.session_state["df"] = load_data(temp_file_path, suffix, sheet_name=sheet_name_to_load)

    elif 'current_file_name' in st.session_state and st.session_state['current_file_name'] == data.name:
        suffix = data.name[data.name.rfind('.'):].lower().replace('.', '')
        if suffix in ('xlsx', 'xls'):
            temp_file_path = os.path.join('uploads', f'{st.session_state["session_id"]}_{data.name}')
            try:
                wb = openpyxl.load_workbook(temp_file_path)
                sheet_names = wb.sheetnames
                if sheet_names:
                    if 'selected_excel_sheet' in st.session_state and st.session_state[
                        'selected_excel_sheet'] in sheet_names:
                        default_sheet_index = sheet_names.index(st.session_state['selected_excel_sheet'])
                    else:
                        default_sheet_index = 0
                    selected_sheet = st.radio(label="请选择要加载的工作表：", options=sheet_names,
                                              index=default_sheet_index, key="excel_sheet_selector_re_render")
                    if selected_sheet != st.session_state.get('selected_excel_sheet'):
                        st.session_state['selected_excel_sheet'] = selected_sheet
                        st.session_state["df"] = load_data(temp_file_path, suffix, sheet_name=selected_sheet)
                else:
                    st.warning("Excel 文件中没有检测到工作表。")
            except Exception as e:
                st.error(f"读取Excel工作表时出错: {e}")

if "df" in st.session_state and not st.session_state['df'].empty:
    with st.expander("原始数据"):
        st.dataframe(st.session_state["df"])
elif "df" in st.session_state and "current_file_name" in st.session_state and st.session_state[
    'current_file_name'] is not None and st.session_state['df'].empty:
    st.info("上传的文件已处理，但生成的 DataFrame 为空。")
elif data is None and "df" in st.session_state:
    st.session_state.pop('df', None)

query = st.text_area(
    "请输入你关于以上文件的问题或数据可视化需求：",
    disabled="df" not in st.session_state,
    placeholder='请输入你的需求'
)

table = st.radio(
    "请选择想要生成什么图表（可选）：",
    ("不生成图表", "柱状图", "折线图", "饼图")
)

button = st.button("生成回答")

if button and not data:
    st.info("请先上传数据文件")
    st.stop()

if button and query and "df" in st.session_state and not st.session_state["df"].empty:
    @st.cache_data(show_spinner="AI正在分析中...", ttl=3600)
    def get_analysis_result(df_hash, query_text):
        return dataframe_agent(st.session_state["df"], query_text)


    df_hash_key = hash((st.session_state["df"].shape, tuple(st.session_state["df"].columns)))
    result = get_analysis_result(df_hash_key, query)

    if "answer" in result:
        st.write(result["answer"])
    if "table" in result:
        st.table(pd.DataFrame(result["table"]["data"], columns=result["table"]["columns"]))

    if table == "柱状图" and "bar" in result:
        create_chart(result["bar"], "柱状图")
    elif table == "折线图" and "line" in result:
        create_chart(result["line"], "折线图")
    elif table == "饼图" and "pie" in result:
        create_chart(result["pie"], "饼图")
elif button:
    st.info("请上传数据文件并输入问题。")
