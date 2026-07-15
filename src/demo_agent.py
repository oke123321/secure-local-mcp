import asyncio
import sys
import json
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
import ollama

MODEL_NAME = "dommage/gemma4-e4b-qat:latest"

async def main():
    if len(sys.argv) < 2:
        print("Vui lòng nhập câu hỏi. Ví dụ: python src/demo_agent.py 'Mật khẩu wifi là gì?'")
        sys.exit(1)
        
    user_prompt = " ".join(sys.argv[1:])
    print(f"[🤖 Agent] Đang khởi động và tải model {MODEL_NAME}...")

    import os
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Cấu hình kết nối tới MCP Server qua stdio
    server_params = StdioServerParameters(
        command="python",
        args=["src/server.py"],
        env=env
    )

    # Khởi tạo kết nối Stdio
    async with stdio_client(server_params) as (read, write):
        # Khởi tạo session MCP
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[✅ MCP] Đã kết nối với Local MCP Server.")

            # Lấy danh sách tools
            tools_response = await session.list_tools()
            
            # Chuyển đổi format tools của MCP sang format của Ollama
            ollama_tools = []
            for tool in tools_response.tools:
                # schema của mcp python sdk thường là dict
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })

            print(f"[✅ MCP] Đã nạp {len(ollama_tools)} tools: {', '.join([t.name for t in tools_response.tools])}")

            messages = [
                {
                    "role": "system",
                    "content": "Bạn là một trợ lý AI thông minh chạy hoàn toàn offline. Bạn sử dụng tools để đọc ghi chú và trả lời ngắn gọn."
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]

            print(f"[👤 Bạn] {user_prompt}")
            print(f"[🤖 Agent] Đang suy nghĩ...\n")

            while True:
                response = ollama.chat(
                    model=MODEL_NAME,
                    messages=messages,
                    tools=ollama_tools
                )

                message = response['message']
                messages.append(message)

                if message.get('tool_calls'):
                    for tool_call in message['tool_calls']:
                        name = tool_call['function']['name']
                        args = tool_call['function']['arguments']
                        print(f"[🛠️ Gọi Tool] -> {name}({json.dumps(args, ensure_ascii=False)})")

                        try:
                            # Gọi tool qua MCP
                            tool_result = await session.call_tool(name, args)
                            
                            # Xử lý kết quả trả về
                            # text format trong mcp sdk python thường là text field của content
                            result_text = "\n".join([c.text for c in tool_result.content if c.type == "text"])
                            
                            messages.append({
                                "role": "tool",
                                "content": result_text
                            })
                            print(f"[📩 Kết quả] Nhận được dữ liệu ({len(result_text)} ký tự). Đang phân tích tiếp...\n")
                        except Exception as e:
                            print(f"[❌ Lỗi Tool] {str(e)}")
                            messages.append({
                                "role": "tool",
                                "content": f"Lỗi khi chạy tool: {str(e)}"
                            })
                else:
                    # AI đã trả lời xong
                    print(f"[🤖 Trả lời]")
                    print(message['content'])
                    break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Lỗi nghiêm trọng: {e}")
