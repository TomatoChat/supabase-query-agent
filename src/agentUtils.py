from dotenv import load_dotenv
load_dotenv()

import asyncio
from google import genai
from google.genai import types
import os
from supabaseMCP import loadSupabaseMCPConfig
from typing import List, Any, Dict


def callLLM(messages: List[str]) -> str:
    """
    This function sends messages to the Gemini 2.5 Flash model and returns the generated response. The messages should be in Gemini format (list of strings) rather than OpenAI format.
    
    Args:
        messages (List[str]): List of message strings to send to the LLM. Should be in Gemini format (simple strings, not dicts with role/content).
    
    Returns:
        str: The generated response text from the Gemini model.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=messages,  # Now messages are already in Gemini format
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
        ),
    )

    return response.text


def callTool(toolName: str, arguments: Dict[str, Any] = None) -> Any:
    """
    Call a Supabase MCP tool with the specified arguments.
    
    Args:
        toolName (str): Name of the tool to call (e.g., 'list_tables', 'execute_sql')
        arguments (Dict[str, Any]): Arguments to pass to the tool. Defaults to empty dict.
    
    Returns:
        Any: The result from the tool call. Returns None if the call fails.
    """
    async def callToolAsync():
        try:
            # Load the Supabase MCP client using existing configuration
            client = loadSupabaseMCPConfig()
            
            async with client:
                # Call the specified tool with arguments
                result = await client.call_tool(toolName, arguments or {})
                return result
                
        except Exception as e:
            print(f"Error calling tool '{toolName}': {str(e)}")
            return None
    
    return asyncio.run(callToolAsync())


def getSupabaseTools() -> List[Any]:
    """
    This function connects to the Supabase MCP server using the existing configuration and retrieves all available tools that can be used for database operations, project management, and development tasks.
    
    Returns:
        List[Any]: List of available tools from the Supabase MCP server. Each tool contains name, description, and other metadata. Returns empty list if connection fails.
    """
    async def getTools():
        try:
            client = loadSupabaseMCPConfig()
            
            async with client:
                toolsResponse = await client.list_tools()
                return toolsResponse
                
        except Exception as e:
            print(f"Error getting Supabase tools: {str(e)}")
            return []
    
    return asyncio.run(getTools())