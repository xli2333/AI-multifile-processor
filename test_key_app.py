# test_key_app.py
import streamlit as st

st.set_page_config(page_title="Key Parameter Test")

st.title("Streamlit Component Key Test")

# 打印当前运行这个脚本的 Streamlit 版本
st.write(f"Streamlit version reported by this script's execution environment: **{st.__version__}**")
st.markdown("---")

# 测试 st.container
st.subheader("Test 1: `st.container`")
try:
    with st.container(border=True, key="my_test_container_with_key"):
        st.write("Container with `key` argument: Content is visible.")
    st.success("`st.container(key=...)` loaded without a TypeError.")
except TypeError as e:
    st.error(f"TypeError on `st.container(key=...)`: {e}")
    st.warning("This error is unexpected for Streamlit versions that support 'key' on st.container (e.g., v1.35.x).")
except Exception as e:
    st.error(f"Other error on `st.container(key=...)`: {e}")

st.markdown("---")

# 测试 st.expander
st.subheader("Test 2: `st.expander`")
try:
    with st.expander("Expander with `key` argument", key="my_test_expander_with_key"):
        st.write("Expander content is visible.")
    st.success("`st.expander(key=...)` loaded without a TypeError.")
except TypeError as e:
    st.error(f"TypeError on `st.expander(key=...)`: {e}")
    st.warning("This error is unexpected for Streamlit versions that support 'key' on st.expander (e.g., v1.35.x).")
except Exception as e:
    st.error(f"Other error on `st.expander(key=...)`: {e}")

st.markdown("---")

# 测试 st.chat_message
st.subheader("Test 3: `st.chat_message`")
try:
    with st.chat_message("user", key="my_test_chat_message_with_key"):
        st.write("Chat message content.")
    st.success("`st.chat_message(key=...)` loaded without a TypeError.")
except TypeError as e:
    st.error(f"TypeError on `st.chat_message(key=...)`: {e}")
    st.warning("This error is unexpected for Streamlit versions that support 'key' on st.chat_message (e.g., v1.22.0+).")
except AttributeError:
    st.error("AttributeError: `st.chat_message` does not exist. This indicates a very old Streamlit version (pre-1.22.0).")
except Exception as e:
    st.error(f"Other error on `st.chat_message(key=...)`: {e}")

st.markdown("---")
st.info("If the tests above for your Streamlit version show TypeErrors for 'key', it strongly suggests an issue with the Streamlit execution environment or installation, as these keys should be supported.")