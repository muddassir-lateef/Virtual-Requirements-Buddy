import ast
import tempfile
import os

from io import BytesIO

from dotenv import load_dotenv
from typing import Dict, Optional
load_dotenv()

from tools import tools, search_tool, download_document_tool
from prompts import SYSTEM_PROMPT
from openai import AsyncOpenAI
import chainlit as cl

client = AsyncOpenAI()
MAX_ITER = 3

# Instrument the OpenAI client
# cl.instrument_openai()

settings = {
    "model": "gpt-4o-mini",
    "temperature": 0,
    "tools": tools,
    "tool_choice": "auto",
    # ... more settings
}

# @cl.oauth_callback
# def oauth_callback(
#   provider_id: str,
#   token: str,
#   raw_user_data: Dict[str, str],
#   default_user: cl.User,
# ) -> Optional[cl.User]:
#   return default_user


@cl.on_chat_start
def start_chat():
    cl.user_session.set(
        "message_history",
        [{"role": "system", "content":SYSTEM_PROMPT}],
    )
    # Initialize the document generation flag
    cl.user_session.set("document_generated_this_turn", False)

@cl.step(type="tool")
async def call_tool(tool_call_id, name, arguments, message_history):
    arguments = ast.literal_eval(arguments)

    current_step = cl.context.current_step
    current_step.name = name
    current_step.input = arguments
    function_response=""
    
    if name=="search_tool":
        function_response = search_tool(
            query=arguments.get("query"),
        )
    elif name=="download_document_tool":
        # Check if we've already generated a document in this conversation turn
        if cl.user_session.get("document_generated_this_turn", False):
            # Skip document generation if already done
            function_response = "Document already generated in this conversation turn."
        else:
            function_response = await download_document_tool(
                conversation_summary=arguments.get("conversation_summary"),
                requirements_focus=arguments.get("requirements_focus"),            
            )
            
            # Handle the document tool response by creating a downloadable file
            if "Requirements document generated successfully!" in function_response:
                try:
                    # Extract the document content from the response
                    # The response format is: "Requirements document generated successfully! Document content:\n\n{content}"
                    content_start = function_response.find("Document content:\n\n") + len("Document content:\n\n")
                    document_content = function_response[content_start:]
                    
                    print(f"DEBUG: Document content length: {len(document_content)} characters")
                    print(f"DEBUG: Document content preview: {document_content[:100]}...")
                    
                    # Create a file element for download
                    file_element = cl.File(
                        name="requirements_document.md",
                        content=document_content.encode('utf-8'),
                        display="inline"
                    )
                    
                    print("DEBUG: File element created successfully")
                    
                    # Send the message with the file attachment
                    await cl.Message(
                        content="Requirements document generated successfully! You can download it using the file attachment below.",
                        elements=[file_element]
                    ).send()
                    
                    print("DEBUG: Message sent successfully with file attachment")
                    
                    # Mark that we've generated a document this turn
                    cl.user_session.set("document_generated_this_turn", True)
                    
                    # Update the function response to just indicate success
                    function_response = "Requirements document generated successfully! The document contains a comprehensive analysis of your requirements based on our conversation."
                    
                except Exception as e:
                    print(f"ERROR: Failed to create or send file: {e}")
                    function_response = f"Document generation succeeded but file creation failed: {str(e)}"

    current_step.output = function_response
    current_step.language = "json"

    message_history.append(
        {
            "role": "function",
            "name": name,
            "content": function_response,
            "tool_call_id": tool_call_id,
        }
    )

async def call_gpt4(message_history):

    stream = await client.chat.completions.create(
        messages=message_history, stream=True, **settings
    )

    tool_call_id = None
    function_output = {"name": "", "arguments": ""}

    final_answer = cl.Message(content="", author="Venus")

    async for part in stream:
        new_delta = part.choices[0].delta
        tool_call = new_delta.tool_calls and new_delta.tool_calls[0]
        function = tool_call and tool_call.function
        if tool_call and tool_call.id:
            tool_call_id = tool_call.id

        if function:
            if function.name:
                function_output["name"] = function.name
            else:
                function_output["arguments"] += function.arguments
        if new_delta.content:
            if not final_answer.content:
                await final_answer.send()
            await final_answer.stream_token(new_delta.content)

    if tool_call_id:
        await call_tool(
            tool_call_id,
            function_output["name"],
            function_output["arguments"],
            message_history,
        )

    if final_answer.content:
        message_history.append({"role": "assistant", "content": final_answer.content})
        cl.user_session.set('message_history',message_history)
        await final_answer.update()

    return tool_call_id

@cl.step(type="tool")
async def speech_to_text(audio_file):
    response = await client.audio.translations.create(
        model="whisper-1", file=audio_file
    )

    return response.text

@cl.on_message
async def on_message(message: cl.Message):

    message_history = cl.user_session.get("message_history")
    message_history.append({"role": "user", "content": message.content})
    
    # Reset the document generation flag for new user messages
    cl.user_session.set("document_generated_this_turn", False)

    cur_iter = 0

    while cur_iter < MAX_ITER:
        tool_call_id = await call_gpt4(message_history)
        if not tool_call_id:
            break

        cur_iter += 1

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    if chunk.isStart:
        buffer = BytesIO()
        # This is required for whisper to recognize the file type
        buffer.name = f"input_audio.{chunk.mimeType.split('/')[1]}"
        # Initialize the session for a new audio stream
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", chunk.mimeType)

    # Write the chunks to a buffer and transcribe the whole audio at the end
    cl.user_session.get("audio_buffer").write(chunk.data)


@cl.on_audio_end
async def on_audio_end():
    # Get the audio buffer from the session
    audio_buffer: BytesIO = cl.user_session.get("audio_buffer")
    audio_buffer.seek(0)  # Move the file pointer to the beginning
    audio_file = audio_buffer.read()
    audio_mime_type: str = cl.user_session.get("audio_mime_type")

    input_audio_el = cl.Audio(
        mime=audio_mime_type, content=audio_file, name=audio_buffer.name
    )
    # await cl.Message(
    #     author="You",
    #     type="user_message",
    #     content="",
    #         elements=[input_audio_el, *elements],
    # ).send()

    whisper_input = (audio_buffer.name, audio_file, audio_mime_type)
    transcription = await speech_to_text(whisper_input)

    msg = cl.Message(author="User", content=transcription)
    await msg.send()
    message_history = cl.user_session.get("message_history")
    message_history.append({"role": "user", "content": transcription})
    
    # Reset the document generation flag for new audio messages
    cl.user_session.set("document_generated_this_turn", False)

    cur_iter = 0

    while cur_iter < MAX_ITER:
        tool_call_id = await call_gpt4(message_history)
        if not tool_call_id:
            break

        cur_iter += 1