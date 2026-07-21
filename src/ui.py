import streamlit as st
import asyncio
import os
import sys
import ollama
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ollama_client = ollama.Client(host=OLLAMA_HOST)

st.set_page_config(page_title="Local AI Agent", page_icon="🤖", layout="wide")

# Lấy danh sách model từ Ollama
try:
    models_response = ollama_client.list()
    if hasattr(models_response, 'models'):
        available_models = [m.model for m in models_response.models]
    else:
        available_models = [m['name'] for m in models_response.get('models', [])]
except Exception as e:
    available_models = []

with st.sidebar:
    st.header("⚙️ Cấu hình AI")
    if not available_models:
        st.error(f"Không thể kết nối Ollama tại `{OLLAMA_HOST}` hoặc chưa có model nào.")
        MODEL_NAME = st.text_input("Nhập tên model thủ công:", value="qwen2.5-coder:7b")
    else:
        MODEL_NAME = st.selectbox("Chọn mô hình AI:", available_models)
    
    st.markdown("---")
    st.caption("Khởi động ứng dụng bằng `start.bat` để có quyền hệ thống cao nhất.")

st.title("🤖 Local MCP AI Agent")
st.caption(f"Trợ lý AI 100% Offline đang chạy bằng `{MODEL_NAME}` tại `{OLLAMA_HOST}`")

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
                "content": (
                    "You are a Software Engineering Assistant running fully offline. "
                    "You have access to tools - you MUST use them, never refuse or say a tool is unavailable. "
                    "RULE: When the user asks about network (ping, IP address, interfaces, ARP) -> ALWAYS call execute_command immediately. "
                    "RULE: When the user asks to find/search files or code -> ALWAYS call search_notes. "
                    "RULE: When the user asks to read a file -> ALWAYS call read_note. "
                    "RULE: For SAFE commands (ping, ipconfig, arp, nslookup, tracert, tasklist, systeminfo, hostname, whoami, netstat, pathping, curl) -> use execute_command. "
                    "RULE: For DANGEROUS commands (netsh, route, net, wmic) -> You MUST ask the user for explicit permission first. If they agree, use execute_dangerous_command. "
                    "Reply to the user in Vietnamese after getting tool results."
                )
            })
            for m in st.session_state.messages:
                # Bỏ qua các tin nhắn tool_calls trong history hiển thị để tránh rối
                if m["role"] in ["user", "assistant"]:
                    chat_history.append({"role": m["role"], "content": m["content"]})
            
            chat_history.append({"role": "user", "content": user_prompt})

            with st.spinner("AI đang suy nghĩ..."):
                response = ollama_client.chat(
                    model=MODEL_NAME,
                    messages=chat_history,
                    tools=ollama_tools
                )
                
            message = response['message']
            # Xử lý nếu AI gọi tool (Cách chuẩn API)
            tool_calls = message.get('tool_calls', [])
            
            # Xử lý fallback cho các model custom (như abliterated) trả về text thay vì API chuẩn
            if not tool_calls and "{" in message.get('content', ''):
                import json, re
                try:
                    # Tìm chuỗi JSON giống {"name": "...", "arguments": {...}}
                    match = re.search(r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}', message['content'], re.DOTALL)
                    if match:
                        raw_tool = json.loads(match.group(0))
                        # Gắn ngược lại vào message để chat_history chuẩn API
                        message['tool_calls'] = [{
                            'function': raw_tool
                        }]
                        tool_calls = message['tool_calls']
                except:
                    pass

            if tool_calls:
                chat_history.append(message)
                for tool_call in tool_calls:
                    name = tool_call['function']['name']
                    args = tool_call['function']['arguments']
                    
                    # Fix lỗi nếu args là string (do model tự parse ngu)
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except:
                            pass
                    
                    with st.status(f"🛠️ Đang gọi công cụ: `{name}`", expanded=False) as status:
                        st.write(f"**Arguments:** {args}")
                        try:
                            tool_result = await session.call_tool(name, args)
                            result_text = "\n".join([c.text for c in tool_result.content if c.type == "text"])
                            st.write("**Result:**")
                            st.code(result_text)
                            chat_history.append({
                                "role": "tool",
                                "content": result_text
                            })
                            status.update(label=f"✅ Hoàn tất gọi công cụ: `{name}`", state="complete", expanded=False)
                        except Exception as e:
                            error_msg = f"Lỗi: {str(e)}"
                            st.error(error_msg)
                            chat_history.append({
                                "role": "tool",
                                "content": error_msg
                            })
                            status.update(label=f"❌ Lỗi khi gọi công cụ: `{name}`", state="error", expanded=True)
                
                # Gọi ollama lần nữa với kết quả từ tool
                with st.spinner("Đang phân tích kết quả..."):
                    final_response = ollama_client.chat(
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
