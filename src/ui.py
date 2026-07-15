import streamlit as st
import asyncio
import os
import ollama
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

MODEL_NAME = "dommage/gemma4-e4b-qat:latest"

st.set_page_config(page_title="Local AI Agent", page_icon="🤖")
st.title("🤖 Local MCP AI Agent")
st.caption(f"Trợ lý AI 100% Offline chạy bằng `{MODEL_NAME}`")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    if msg["role"] in ["user", "assistant"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

async def ask_agent(user_prompt):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    
    server_params = StdioServerParameters(
        command="python",
        args=["src/server.py"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            tools_response = await session.list_tools()
            ollama_tools = []
            for tool in tools_response.tools:
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })

            # Lấy lịch sử chat
            chat_history = []
            chat_history.append({
                "role": "system",
                "content": "Bạn là một trợ lý AI thông minh chạy hoàn toàn offline. Bạn có khả năng sử dụng các công cụ để đọc, tìm kiếm, và tạo ghi chú. Hãy trả lời thật chuyên nghiệp, ngắn gọn bằng tiếng Việt."
            })
            for m in st.session_state.messages:
                # Bỏ qua các tin nhắn tool_calls trong history hiển thị để tránh rối
                if m["role"] in ["user", "assistant"]:
                    chat_history.append({"role": m["role"], "content": m["content"]})
            
            chat_history.append({"role": "user", "content": user_prompt})

            with st.spinner("AI đang suy nghĩ..."):
                response = ollama.chat(
                    model=MODEL_NAME,
                    messages=chat_history,
                    tools=ollama_tools
                )
                
            message = response['message']
            
            # Xử lý nếu AI gọi tool
            if message.get('tool_calls'):
                chat_history.append(message)
                for tool_call in message['tool_calls']:
                    name = tool_call['function']['name']
                    args = tool_call['function']['arguments']
                    st.toast(f"🛠️ Đang gọi công cụ: {name}", icon="⚙️")
                    
                    try:
                        tool_result = await session.call_tool(name, args)
                        result_text = "\n".join([c.text for c in tool_result.content if c.type == "text"])
                        chat_history.append({
                            "role": "tool",
                            "content": result_text
                        })
                    except Exception as e:
                        chat_history.append({
                            "role": "tool",
                            "content": f"Lỗi: {str(e)}"
                        })
                
                # Gọi ollama lần nữa với kết quả từ tool
                with st.spinner("Đang phân tích kết quả..."):
                    final_response = ollama.chat(
                        model=MODEL_NAME,
                        messages=chat_history
                    )
                return final_response['message']['content']
            else:
                return message['content']

query = st.chat_input("Hỏi tôi bất cứ điều gì về ghi chú của bạn...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
        
    with st.chat_message("assistant"):
        with st.spinner("Đang kết nối..."):
            answer = asyncio.run(ask_agent(query))
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
