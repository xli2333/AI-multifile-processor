import json
import streamlit as st
import os

STATE_FILE = "session_data.json"

def save_app_state():
    """将Streamlit session_state中的特定数据保存到文件。"""
    state_to_save = {}
    if 'files_data' in st.session_state:
        state_to_save['files_data'] = st.session_state.files_data
    if 'api_key' in st.session_state: # 保存API密钥可能不是最佳实践，但按需求保留
        state_to_save['api_key'] = st.session_state.api_key
    if 'user_general_instruction' in st.session_state:
        state_to_save['user_general_instruction'] = st.session_state.user_general_instruction

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.warning(f"保存应用状态失败: {e}")

def load_app_state():
    """从文件加载应用状态到Streamlit session_state。"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                loaded_state = json.load(f)
                
                if 'files_data' in loaded_state:
                    st.session_state.files_data = loaded_state['files_data']
                if 'api_key' in loaded_state:
                    st.session_state.api_key = loaded_state['api_key']
                if 'user_general_instruction' in loaded_state:
                    st.session_state.user_general_instruction = loaded_state['user_general_instruction']
                return True # 表示加载成功
        except Exception as e:
            st.warning(f"加载应用状态失败: {e}. 将使用默认值初始化。")
            # 如果加载失败，确保核心结构存在
            if 'files_data' not in st.session_state:
                st.session_state.files_data = {} # filename -> data
    return False # 表示未加载或加载失败