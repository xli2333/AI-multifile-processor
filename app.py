import streamlit as st
from dotenv import load_dotenv
import os
import time
import pandas as pd # <--- 新增：导入 pandas

from openai_utils import get_gpt4o_response, generate_initial_analysis_prompt
from persistence_utils import save_app_state, load_app_state, STATE_FILE

# Page config (should be the first Streamlit command)
st.set_page_config(page_title="批量文件智能处理助手", layout="wide", initial_sidebar_state="expanded")

# Load environment variables (API Key)
load_dotenv() # 在本地开发时仍然有用

# --- Application State Initialization ---
DEFAULT_USER_INSTRUCTION = "请仔细检查以下文本的翻译质量，评估其准确性、流畅性和文化适应性。如果存在不合理之处，请具体指出并提供修改建议。"

# 获取API密钥的辅助函数 (与上一版本相同，用于云端部署)
def get_configured_api_key():
    try:
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return st.session_state.get("api_key", "")

if 'app_initialized' not in st.session_state:
    if 'streamlit_sharing' not in os.environ:
        persisted_state_loaded = load_app_state()

    if 'api_key' not in st.session_state: 
        st.session_state.api_key = "" 

    default_values = {
        'files_data': {},
        'current_view': "main_upload",
        'selected_file_for_chat': None,
        'user_general_instruction': DEFAULT_USER_INSTRUCTION,
        'confirm_clear_history': False
    }
    for key_name, default_value in default_values.items(): 
        if key_name not in st.session_state:
            st.session_state[key_name] = default_value
    
    st.session_state.app_initialized = True

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ 设置与导航")
    
    st.text_input(
        "OpenAI API 密钥 (若云端已配置Secrets则此处可留空)", 
        type="password", 
        key="api_key" 
    )

    if st.button("🏠 返回主上传/结果页", key="home_btn_sidebar"):
        st.session_state.current_view = "main_upload"
        st.session_state.selected_file_for_chat = None
        st.rerun()

    st.markdown("---")
    st.subheader("当前已处理文件")
    if not st.session_state.files_data:
        st.caption("尚未处理任何文件。")
    else:
        sorted_filenames = sorted(list(st.session_state.files_data.keys()))
        for filename_key_nav in sorted_filenames: 
            safe_nav_key = f"nav_btn_sidebar_{filename_key_nav.replace('.', '_').replace(' ', '_')}"
            if st.button(f"📄 {filename_key_nav}", key=safe_nav_key):
                st.session_state.selected_file_for_chat = filename_key_nav
                st.session_state.current_view = "chat_view"
                st.rerun()
    
    st.markdown("---")
    if st.button("💾 保存当前状态 (云端效果有限)", key="save_state_btn_sidebar"):
        if 'streamlit_sharing' not in os.environ: 
            save_app_state() 
            st.success("应用状态已在本地保存！")
        else:
            st.info("在云端环境中，状态主要保存在当前会话中，无法持久保存到本地文件。")

    st.markdown("---")
    if st.session_state.confirm_clear_history: 
        st.warning("您确定要清空所有已处理文件的数据和对话历史吗？此操作无法撤销。")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 是，全部清空", type="primary", key="confirm_clear_btn_sidebar"): 
                st.session_state.files_data = {}
                st.session_state.selected_file_for_chat = None
                st.session_state.current_view = "main_upload"
                st.session_state.user_general_instruction = DEFAULT_USER_INSTRUCTION 
                if 'streamlit_sharing' not in os.environ: 
                    save_app_state() 
                st.session_state.confirm_clear_history = False 
                st.success("所有内存中的历史记录已清空！") 
                time.sleep(1.5) 
                st.rerun()
        with col2:
            if st.button("❌ 否，取消操作", key="cancel_clear_btn_sidebar"): 
                st.session_state.confirm_clear_history = False
                st.rerun()
    else:
        if st.button("⚠️ 清空所有历史记录", help="点击后需要二次确认。", key="initiate_clear_btn_sidebar"): 
            st.session_state.confirm_clear_history = True
            st.rerun()

# --- Main Application Logic ---
if st.session_state.current_view == "main_upload":
    st.header("📝 批量文件处理与分析")
    st.markdown("上传您的文件，并提供一个通用的处理指令。")

    effective_api_key = get_configured_api_key()

    if not effective_api_key: 
        st.warning("请在侧边栏输入您的OpenAI API密钥，或确保云端部署已正确配置Secrets。")
    
    current_instruction = st.text_area(
        "通用处理指令:",
        value=st.session_state.user_general_instruction, 
        height=100,
        key="general_instruction_input_main" 
    )
    if current_instruction != st.session_state.user_general_instruction: 
        st.session_state.user_general_instruction = current_instruction

    # --- 修改处：st.file_uploader 添加 Excel 文件类型 ---
    uploaded_files = st.file_uploader(
        "选择文件进行批量处理 (支持 .txt, .md, .csv, .json, .py, .html, .css, .js, .xls, .xlsx)",
        accept_multiple_files=True,
        type=['txt', 'md', 'csv', 'json', 'py', 'html', 'css', 'js', 'xls', 'xlsx', 'xlsm'], # 添加 Excel 类型
        key="file_uploader_input_main" 
    )

    if st.button("🚀 开始处理上传的文件", disabled=not effective_api_key or not uploaded_files, key="process_files_btn_main"):
        if not st.session_state.user_general_instruction.strip():
            st.error("请输入通用的处理指令！")
        else:
            progress_bar = st.progress(0, text="准备开始处理...")
            total_files = len(uploaded_files)
            processing_errors_local = {} 

            for i, uploaded_file in enumerate(uploaded_files):
                filename = uploaded_file.name
                file_content_str = "" # 初始化文件内容字符串

                # --- 修改处：添加 Excel 文件处理逻辑 ---
                if filename.lower().endswith(('.xls', '.xlsx', '.xlsm')):
                    try:
                        excel_data = pd.read_excel(uploaded_file, sheet_name=None, engine='openpyxl') # 读取所有工作表
                        
                        content_parts = []
                        if isinstance(excel_data, dict): # 多工作表情况
                            if not excel_data: # 检查excel_data是否为空字典 (即没有工作表)
                                content_parts.append(f"--- 文件: {filename} (Excel) ---\n")
                                content_parts.append("Excel 文件中没有找到工作表。\n\n")
                            else:
                                for sheet_name, df in excel_data.items():
                                    content_parts.append(f"--- 工作表: {sheet_name} (来自文件: {filename}) ---\n")
                                    if not df.empty:
                                        # 将DataFrame转换为Markdown表格字符串，更适合LLM阅读
                                        content_parts.append(df.to_markdown(index=False))
                                    else:
                                        content_parts.append("此工作表为空。")
                                    content_parts.append("\n\n")
                        else: # 单工作表情况 (pandas 直接返回 DataFrame)
                            df = excel_data
                            content_parts.append(f"--- 文件: {filename} (Excel) ---\n")
                            if not df.empty:
                                content_parts.append(df.to_markdown(index=False))
                            else:
                                content_parts.append("Excel 文件（或其唯一工作表）为空。")
                            content_parts.append("\n\n")

                        file_content_str = "".join(content_parts)
                        if not file_content_str.strip():
                             file_content_str = f"文件 {filename} (Excel) 内容为空或未能提取有效文本。"
                             st.info(file_content_str)


                    except Exception as e:
                        st.error(f"读取 Excel 文件 {filename} 时发生错误: {e}")
                        processing_errors_local[filename] = f"Excel 读取错误: {e}"
                        file_content_str = f"错误：无法读取Excel文件 {filename}。错误信息：{e}" # 提供错误信息给AI
                        # continue # 可以选择跳过此文件，或者像下面这样继续但发送错误信息
                
                else: # 原有的文本文件处理逻辑
                    try:
                        file_content_bytes = uploaded_file.getvalue()
                        try:
                            file_content_str = file_content_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            try:
                                file_content_str = file_content_bytes.decode("gbk") # 尝试 GBK
                            except UnicodeDecodeError:
                                file_content_str = file_content_bytes.decode("latin-1", errors='replace') # 最后尝试 latin-1
                                st.warning(f"文件 {filename} 使用UTF-8和GBK解码失败，已尝试latin-1解码。")
                        if not file_content_str.strip():
                            file_content_str = f"文件 {filename} 内容为空。"
                            st.info(file_content_str)

                    except Exception as e:
                        st.error(f"读取文本文件 {filename} 时发生错误: {e}")
                        processing_errors_local[filename] = f"文本文件读取错误: {e}"
                        file_content_str = f"错误：无法读取文本文件 {filename}。错误信息：{e}" # 提供错误信息给AI
                        # continue

                # --- 文件内容准备完毕 (file_content_str) ---

                progress_text = f"处理中 ({i+1}/{total_files}): {filename} (请求AI分析...)"
                progress_bar.progress((i + 0.5) / total_files, text=progress_text)
                
                # 即使读取出错，也尝试将包含错误信息的内容发给AI，让AI知道哪个文件出错了
                initial_prompt_content = generate_initial_analysis_prompt(file_content_str, st.session_state.user_general_instruction)
                messages_for_api = [{"role": "user", "content": initial_prompt_content}]
                initial_response = get_gpt4o_response(effective_api_key, messages_for_api)

                if initial_response:
                    st.session_state.files_data[filename] = {
                        "content_str": file_content_str, # 保存转换后的文本内容或错误信息
                        "initial_user_prompt_content": initial_prompt_content,
                        "initial_response": initial_response,
                        "chat_history": [
                            {"role": "user", "content": initial_prompt_content}, 
                            {"role": "assistant", "content": initial_response}
                        ]
                    }
                    if filename not in processing_errors_local: # 如果之前没有记录错误
                        st.success(f"文件 {filename} 初步分析完成！")
                    else: # 如果之前读取时就有错误，这里提示一下，但AI还是处理了包含错误信息的内容
                        st.info(f"文件 {filename} 读取时存在问题，已将包含错误描述的内容发送给AI进行分析。")

                else: # API 调用失败
                    st.error(f"文件 {filename} 分析失败，未能从API获取回应。")
                    if filename not in processing_errors_local:
                        processing_errors_local[filename] = "API无回应或错误"
                
                progress_bar.progress((i + 1) / total_files, text=f"已完成: {filename}")
                time.sleep(0.1) 

            progress_bar.empty()
            if processing_errors_local: 
                st.warning("部分文件在预处理或API调用环节遇到问题：")
                for fname, err_msg in processing_errors_local.items(): 
                    st.caption(f"- {fname}: {err_msg}")
            
            st.session_state.current_view = "file_results" 
            if 'streamlit_sharing' not in os.environ:
                save_app_state() 
            st.rerun() 

    st.markdown("---")
    if st.session_state.files_data:
        st.subheader("📋 已处理文件概览")
        num_columns = 3 
        sorted_filenames_main = sorted(list(st.session_state.files_data.keys()))
        for i in range(0, len(sorted_filenames_main), num_columns):
            cols = st.columns(num_columns)
            for j in range(num_columns):
                if i + j < len(sorted_filenames_main):
                    filename_main = sorted_filenames_main[i+j]
                    file_data_main = st.session_state.files_data[filename_main]
                    safe_filename_display = filename_main.replace('.', '_').replace(' ', '_')
                    with cols[j]:
                        with st.container(border=True, key=f"overview_container_{safe_filename_display}"):
                            st.markdown(f"**📄 {filename_main}**")
                            st.caption("初步分析摘要:")
                            with st.expander("查看摘要", expanded=False): 
                                st.markdown(f"> {file_data_main['initial_response']}")
                            
                            if st.button("💬 查看详情与对话", key=f"details_btn_{safe_filename_display}"):
                                st.session_state.selected_file_for_chat = filename_main
                                st.session_state.current_view = "chat_view"
                                st.rerun()
    else:
        st.info("上传文件并开始处理后，结果将在此处显示。")

elif st.session_state.current_view == "file_results": 
    st.session_state.current_view = "main_upload"
    st.rerun()

elif st.session_state.current_view == "chat_view":
    filename_chat = st.session_state.selected_file_for_chat
    if not filename_chat or filename_chat not in st.session_state.files_data:
        st.error("未选择有效文件或文件数据丢失。请返回主页重新选择。")
        st.session_state.current_view = "main_upload" 
        st.rerun()
    else:
        file_data_chat = st.session_state.files_data[filename_chat]
        safe_filename_chat = filename_chat.replace('.', '_').replace(' ', '_')
        
        effective_api_key_chat = get_configured_api_key()

        st.subheader(f"💬 与文件 '{filename_chat}' 对话中")
        with st.expander("原始文件内容 (点击展开/折叠)"): 
            # 对于Excel，原始文件内容是转换后的文本，而不是二进制
            # 如果需要显示原始Excel的某种预览，需要更复杂的处理
            st.text_area(
                "已处理的文件内容 (文本格式)", 
                # 注意：file_data_chat['content_str'] 现在可能是Markdown表格字符串
                # 如果过长，text_area可能会很慢，但对于调试是好的
                file_data_chat.get('content_str', '无内容'), 
                height=300, 
                disabled=True, 
                key=f"processed_content_text_{safe_filename_chat}"
            )
        
        st.markdown("---")
        st.markdown("##### 对话历史")
        
        chat_container_height = st.sidebar.slider("调整对话框高度:", 200, 800, 400, 50, key=f"chat_height_slider_chatview_{safe_filename_chat}")
        with st.container(height=chat_container_height, key=f"chat_display_container_chatview_{safe_filename_chat}"): 
            for i_msg, message in enumerate(file_data_chat["chat_history"]): 
                with st.chat_message(message["role"]): 
                    if message["role"] == "user" and i_msg == 0:
                        display_content = (
                            f"用户为文件 '{filename_chat}' 提交了分析请求。\n\n"
                            f"**通用处理指令**:\n{st.session_state.user_general_instruction}\n\n"
                            f"(AI已收到转换后的文件文本内容并进行了首次分析。首次分析结果见下方AI回复)"
                        )
                        st.markdown(display_content)
                    else:
                        st.markdown(message["content"])
        
        user_chat_input = st.chat_input(f"就 '{filename_chat}' 继续提问...", key=f"chat_input_chatview_{safe_filename_chat}")

        if user_chat_input:
            if not effective_api_key_chat: 
                st.warning("请输入API密钥后才能发送消息，或确保云端部署已正确配置Secrets。")
            else:
                file_data_chat["chat_history"].append({"role": "user", "content": user_chat_input})
                messages_for_api = file_data_chat["chat_history"]
                ai_response = get_gpt4o_response(effective_api_key_chat, messages_for_api)
                if ai_response:
                    file_data_chat["chat_history"].append({"role": "assistant", "content": ai_response})
                else:
                    file_data_chat["chat_history"].append({"role": "assistant", "content": "抱歉，我暂时无法回复。"})
                
                if 'streamlit_sharing' not in os.environ:
                    save_app_state() 
                st.rerun()