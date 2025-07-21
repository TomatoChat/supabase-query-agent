import json
import os
from dotenv import load_dotenv
import re
from typing import Any, Dict, List, Union
from fastmcp import Client
import asyncio
load_dotenv()


def substituteEnvVars(obj: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
    """
    Recursively substitute placeholders of the form ${VAR} in a data structure with environment variable values.

    Args:
        obj (dict | list | str | any): The object to process. Can be a dictionary, list, string, or any other type.

    Returns:
        dict | list | str | any: The object with all ${VAR} strings replaced by their corresponding environment variable values. If the environment variable is not found, the original string is returned.
    """
    if isinstance(obj, dict):
        return {k: substituteEnvVars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substituteEnvVars(i) for i in obj]
    elif isinstance(obj, str):
        def replacer(match):
            envVar = match.group(1)
            return os.getenv(envVar, match.group(0))
        return re.sub(r'\$\{([^}]+)\}', replacer, obj)
    else:
        return obj
    

def loadSupabaseMCPConfig(jsonPath: str = os.path.join(os.path.dirname(__file__), 'serversMCP.json'), returnClient: bool = True) -> Union[Client, Dict[str, Any]]:
    """
    Load the Supabase MCP configuration and optionally create a FastMCP client.
    
    Args:
        jsonPath (str): Path to the JSON file containing MCP server configurations. Defaults to 'serversMCP.json' in the same directory as this script.
        returnClient (bool): If True, returns a FastMCP client. If False, returns the resolved configuration dict.
    
    Returns:
        Union[Client, Dict[str, Any]]: Either a configured FastMCP client instance or the resolved configuration.
    """
    # Load the JSON file
    with open(jsonPath, 'r') as f:
        mcpConfig = json.load(f)
    
    # Substitute environment variables
    mcpConfig = substituteEnvVars(mcpConfig)
    
    if returnClient:
        # Return FastMCP client
        client = Client(transport=mcpConfig)
        return client
    else:
        # Return the Supabase config only
        supabaseConfig = mcpConfig['mcpServers']['supabase']
        return supabaseConfig