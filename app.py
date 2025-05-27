import streamlit as st
# from dotenv import load_dotenv # 在云端不需要 dotenv，可以注释掉或保留用于本地
import os
import time

from openai_utils import get_gpt4o_response, generate_initial_analysis_prompt
from persistence_utils import save_app_state, load_app_state, STATE_FILE

# 页面配置 (应是第一个 Streamlit 命令)
st.set_page_config(page_title="批量文件智能处理助手", layout="wide", initial_sidebar_state="expanded")

# load_dotenv() # 如果使用，确保它只在本地开发时加载

# --- 应用状态初始化 ---
DEFAULT_USER_INSTRUCTION = "请仔细检查以下文本的翻译质量，评估其准确性、流畅性和文化适应性。如果存在不合理之处，请具体指出并提供修改建议。"

# 获取API密钥的辅助函数
def get_configured_api_key():
    """
    优先从 Streamlit Secrets 获取 API 密钥。
    如果 Secrets 中没有，则回退到 session_state 中的 api_key (通常由用户在侧边栏输入)。
    """
    try:
        # 检查是否在 Streamlit Cloud 环境中运行，并且 Secrets 是否已配置
        # Streamlit Cloud 会自动将 Secrets 注入到 st.secrets 中
        # 您需要在 Streamlit Cloud 的应用设置中设置一个名为 "OPENAI_API_KEY" 的 Secret
        if hasattr(st, 'secrets') and "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception: # st.secrets 可能在本地环境中不存在
        pass
    
    # 如果 Secrets 中没有，或者不在云环境中，则使用 session_state 中的 api_key
    return st.session_state.get("api_key", "")


if 'app_initialized' not in st.session_state:
    # 对于云部署，load_app_state() 读取本地 session_data.json 的方式对于持久化记忆是无效的。
    # 如果您希望保留本地开发时的加载功能，可以有条件地调用它。
    if 'streamlit_sharing' not in os.environ: # 仅在本地环境尝试加载
        persisted_state_loaded = load_app_state()

    # 初始化 session_state 中的 api_key (主要用于本地用户输入)
    if 'api_key' not in st.session_state: 
        st.session_state.api_key = "" # 初始为空，等待用户输入或从 Secrets 加载

    default_values = {
        'files_data': {}, # 在云端，这部分数据在会话结束后会丢失
        'current_view': "main_upload",
        'selected_file_for_chat': None,
        'user_general_instruction': DEFAULT_USER_INSTRUCTION,
        'confirm_clear_history': False
    }
    for key_name, default_value in default_values.items(): 
        if key_name not in st.session_state:
            st.session_state[key_name] = default_value
    
    st.session_state.app_initialized = True

# --- 侧边栏 ---
with st.sidebar:
    st.title("⚙️ 设置与导航")
    
    # API 密钥输入框，主要用于本地测试或当 Secrets 未配置时的备用
    # 在云端，我们期望 API 密钥通过 st.secrets 提供
    st.text_input(
        "OpenAI API 密钥 (若云端已配置Secrets则此处可留空)", 
        type="password", 
        key="api_key" # 这个 key 会将输入值存入 st.session_state.api_key
    )

    # 获取当前应该使用的API密钥
    # 在每次需要使用API密钥的地方调用 get_configured_api_key()
    # 或者在应用开始时获取一次，并保存在一个变量中（但要注意 session_state 的更新）

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
    # “保存当前状态”按钮在云端作用有限，因为文件系统是临时的
    if st.button("💾 保存当前状态 (云端效果有限)", key="save_state_btn_sidebar"):
        if 'streamlit_sharing' not in os.environ: # 仅在本地尝试保存到文件
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
                if 'streamlit_sharing' not in os.environ: # 仅在本地尝试保存空状态
                    save_app_state() 
                st.session_state.confirm_clear_history = False 
                st.success("所有内存中的历史记录已清空！") # 调整提示，强调内存
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

# --- 主应用逻辑 ---
if st.session_state.current_view == "main_upload":
    st.header("📝 批量文件处理与分析")
    st.markdown("上传您的文件，并提供一个通用的处理指令。")

    # 在操作前获取实际使用的API密钥
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

    uploaded_files = st.file_uploader(
        "选择文件进行批量处理",
        accept_multiple_files=True,
        type=['txt', 'md', 'csv', 'json', 'py', 'html', 'css', 'js'], 
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
                try:
                    file_content_bytes = uploaded_file.getvalue()
                    file_content_str = file_content_bytes.decode("utf-8") # 假设UTF-8，可以添加更多编码尝试
                except Exception as e:
                    st.error(f"读取或解码文件 {filename} 时发生错误: {e}")
                    processing_errors_local[filename] = f"读取/解码错误: {e}"
                    progress_bar.progress((i + 1) / total_files, text=f"处理中: {filename} (错误)")
                    time.sleep(0.1)
                    continue

                progress_text = f"处理中 ({i+1}/{total_files}): {filename} (请求AI分析...)"
                progress_bar.progress((i + 0.5) / total_files, text=progress_text)
                initial_prompt_content = generate_initial_analysis_prompt(file_content_str, st.session_state.user_general_instruction)
                messages_for_api = [{"role": "user", "content": initial_prompt_content}]
                # 使用 effective_api_key 进行API调用
                initial_response = get_gpt4o_response(effective_api_key, messages_for_api)

                if initial_response:
                    st.session_state.files_data[filename] = {
                        "content_str": file_content_str,
                        "initial_user_prompt_content": initial_prompt_content,
                        "initial_response": initial_response,
                        "chat_history": [
                            {"role": "user", "content": initial_prompt_content}, 
                            {"role": "assistant", "content": initial_response}
                        ]
                    }
                    st.success(f"文件 {filename} 初步分析完成！")
                else:
                    st.error(f"文件 {filename} 分析失败，未能从API获取回应。")
                    processing_errors_local[filename] = "API无回应或错误"
                
                progress_bar.progress((i + 1) / total_files, text=f"已完成: {filename}")
                time.sleep(0.1) 

            progress_bar.empty()
            if processing_errors_local: 
                st.warning("部分文件处理失败：")
                for fname, err_msg in processing_errors_local.items(): 
                    st.caption(f"- {fname}: {err_msg}")
            
            st.session_state.current_view = "file_results" 
            if 'streamlit_sharing' not in os.environ: # 仅在本地尝试保存状态
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
                        # st.container 保留 key (根据您之前的测试结果)
                        with st.container(border=True, key=f"overview_container_{safe_filename_display}"):
                            st.markdown(f"**📄 {filename_main}**")
                            st.caption("初步分析摘要:")
                            # st.expander 移除 key (根据您之前的测试结果，作为 workaround)
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
        
        # 获取API密钥
        effective_api_key_chat = get_configured_api_key()

        st.subheader(f"💬 与文件 '{filename_chat}' 对话中")
        # st.expander 移除 key (根据您之前的测试结果，作为 workaround)
        with st.expander("原始文件内容 (点击展开/折叠)"): 
            st.text_area("Content", file_data_chat.get('content_str', '无内容'), height=200, disabled=True, key=f"orig_content_text_{safe_filename_chat}")
        
        st.markdown("---")
        st.markdown("##### 对话历史")
        
        chat_container_height = st.sidebar.slider("调整对话框高度:", 200, 800, 400, 50, key=f"chat_height_slider_chatview_{safe_filename_chat}")
        # st.container 保留 key (根据您之前的测试结果)
        with st.container(height=chat_container_height, key=f"chat_display_container_chatview_{safe_filename_chat}"): 
            for i_msg, message in enumerate(file_data_chat["chat_history"]): 
                # st.chat_message 移除 key (根据您之前的测试结果，作为 workaround，可能影响渲染稳定性)
                with st.chat_message(message["role"]): 
                    if message["role"] == "user" and i_msg == 0:
                        display_content = (
                            f"用户为文件 '{filename_chat}' 提交了分析请求。\n\n"
                            f"**通用处理指令**:\n{st.session_state.user_general_instruction}\n\n"
                            f"(AI已收到完整文件内容并进行了首次分析。首次分析结果见下方AI回复)"
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
                # 使用 effective_api_key_chat 进行API调用
                ai_response = get_gpt4o_response(effective_api_key_chat, messages_for_api)
                if ai_response:
                    file_data_chat["chat_history"].append({"role": "assistant", "content": ai_response})
                else:
                    file_data_chat["chat_history"].append({"role": "assistant", "content": "抱歉，我暂时无法回复。"})
                
                if 'streamlit_sharing' not in os.environ: # 仅在本地尝试保存状态
                    save_app_state() 
                st.rerun()