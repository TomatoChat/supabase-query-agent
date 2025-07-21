from pocketflow import Node
from agentUtils import callLLM, getSupabaseTools, callTool
import yaml


class GetTools(Node):
    def prep(self, shared):
        """Initialize and get tools"""
        print("🔍 Getting available tools...")
        return "supabaseMCP.py"


    def exec(self, inputs):
        """Retrieve tools from the MCP server"""
        supabaseTools = getSupabaseTools()
        createQuerySQLSchema = {
            "name": "create_query_SQL",
            "description": "Create a SQL query to answer the question",
            "inputSchema": {
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to answer with the SQL query"
                    },
                    "databaseSchema": {
                        "type": "object",
                        "description": "The database schema as a JSON object with all the descriptions of the tables and columns"
                    }
                },
                "required": ["question", "databaseSchema"]
            }
        }
        otherTools = [createQuerySQLSchema]
        tools = supabaseTools + otherTools

        return tools


    def post(self, shared, prep_res, exec_res):
        """Store tools and process to decision node"""
        tools = exec_res
        shared["tools"] = tools
        toolInfo = []

        for i, tool in enumerate(tools, 1):
            # Handle both object attributes and dictionary keys
            if hasattr(tool, 'inputSchema'):
                properties = tool.inputSchema.get('properties', {})
                required = tool.inputSchema.get('required', [])
                tool_name = tool.name
                tool_description = tool.description
            else:
                properties = tool.get('inputSchema', {}).get('properties', {})
                required = tool.get('inputSchema', {}).get('required', [])
                tool_name = tool.get('name', 'Unknown')
                tool_description = tool.get('description', 'No description')
            
            params = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'unknown')
                req_status = "(Required)" if param_name in required else "(Optional)"
                params.append(f"    - {param_name} ({param_type}): {req_status}")
            
            toolInfo.append(f"[{i}] {tool_name}\n  Description: {tool_description}\n  Parameters:\n" + "\n".join(params))
        
        shared["toolInfo"] = "\n".join(toolInfo)

        return "decide"


class DecideAction(Node):
    def prep(self, shared):
        toolInfo = shared.get("toolInfo", "No tool information provided.")
        question = shared.get("question", "No question provided.")
        databaseContext = shared.get("databaseContext", "No database list of tables and context provided.")
        queryUsed = shared.get("queryUsed", "No query used.")
        queryResult = shared.get("queryResult", "No query result returned.")

        return toolInfo, question, databaseContext, queryUsed, queryResult


    def exec(self, inputs):
        toolInfo, question, databaseContext, queryUsed, queryResult = inputs
        print(f"🤔 Agent deciding what to do next...")

        contextPrompt = f"""
### CONTEXT
You are a data analyst that can query a database and provide the response to the answer the person is asking.
Question: {question}
Database Context: {databaseContext}
Query Used: {queryUsed}
Query Result: {queryResult}

### ACTION SPACE
{toolInfo}

## NEXT ACTION
Decide the next action based on the context and available actions.
Return your response in this format:

```yaml
thinking: |
    <your step-by-step reasoning process>
action: <tool_name_from_action_space>
reason: <why you chose this action>
parameters: <parameters for the chosen tool>
```"""
        
        response = callLLM(contextPrompt)
        yamlStr = response.split("```yaml")[1].split("```")[0].strip()
        decision = yaml.safe_load(yamlStr)

        return decision


    def post(self, shared, prep_res, exec_res):
        # Store the decision in shared state
        shared["chosenAction"] = exec_res.get("action", "")
        shared["actionReason"] = exec_res.get("reason", "")
        shared["actionParameters"] = exec_res.get("parameters", {})
        
        return exec_res.get("action", "")


class ExecuteToolNode(Node):
    """Execute the chosen tool based on the decision"""
    
    def prep(self, shared):
        """Prepare inputs for tool execution"""
        chosenAction = shared.get("chosenAction", "")
        actionParameters = shared.get("actionParameters", {})
        
        return chosenAction, actionParameters
    
    def exec(self, inputs):
        """Execute the chosen tool"""
        chosenAction, actionParameters = inputs
        
        if chosenAction == "create_query_SQL":
            temp_shared = {
                "question": actionParameters.get("question", ""),
                "databaseContext": str(actionParameters.get("databaseSchema", {})),
                "queryUsed": "",
                "queryResult": "",
                "queryThinking": "",
                "queryExplanation": "",
                "correctData": True
            }
            
            generateSQLNode = GenerateQuerySQL()
            prep_result = generateSQLNode.prep(temp_shared)
            exec_result = generateSQLNode.exec(prep_result)
            post_result = generateSQLNode.post(temp_shared, prep_result, exec_result)
            
            generated_query = temp_shared.get("queryUsed", "")
            query_explanation = temp_shared.get("queryExplanation", "")
            
            return {
                "tool": "create_query_SQL",
                "action": "storeResult",
                "result": {
                    "sql_query": generated_query,
                    "explanation": query_explanation,
                    "thinking": temp_shared.get("queryThinking", "")
                },
                "success": True
            }
        else:
            try:
                result = callTool(chosenAction, actionParameters)
                
                return {
                    "tool": chosenAction,
                    "action": "storeResult",
                    "result": result,
                    "success": True
                }
            except Exception as e:
                return {
                    "tool": chosenAction,
                    "action": "storeResult",
                    "result": f"Error: {str(e)}",
                    "success": False
                }
    
    def post(self, shared, prep_res, exec_res):
        """Store results and route to next node"""
        tool = exec_res.get("tool", "")
        action = exec_res.get("action", "")
        
        if action == "storeResult":
            # Store the result
            result = exec_res.get("result", "")
            
            if isinstance(result, dict) and "sql_query" in result:
                # Handle SQL generation result
                shared["queryUsed"] = result.get("sql_query", "")
                shared["queryExplanation"] = result.get("explanation", "")
                shared["queryThinking"] = result.get("thinking", "")
                print("✅ SQL query generated successfully!")
                print(f"📝 Query: {result.get('sql_query', '')[:100]}...")
            else:
                # Handle other tool results
                shared["queryResult"] = result
            
            if exec_res.get("success", False):
                print("✅ Tool executed successfully!")
            else:
                print(f"❌ Tool execution failed: {result}")
            
            return "responseChecker"
        else:
            print(f"❓ Unknown action: {action}")
            return "decide"


class GenerateQuerySQL(Node):
    def prep(self, shared):
        """Prepare inputs for SQL query generation"""
        # Check if we have parameters from the create_query_SQL tool
        actionParameters = shared.get("actionParameters", {})
        
        if actionParameters and "question" in actionParameters:
            # Use parameters from the tool
            question = actionParameters.get("question", "")
            databaseSchema = actionParameters.get("databaseSchema", {})
            databaseContext = str(databaseSchema) if databaseSchema else "No database context provided."
        else:
            # Use default shared state
            question = shared.get("question", "No question provided.")
            databaseContext = shared.get("databaseContext", "No database context provided.")
        
        print("🔍 Preparing to generate SQL query...")
        return question, databaseContext


    def exec(self, inputs):
        """Generate SQL query using LLM"""
        question, databaseContext = inputs
        print("🤖 Generating SQL query...")
        
        prompt = f"""
You are a SQL expert. Generate a SQL query to answer the user's question.

### USER QUESTION
{question}

### DATABASE CONTEXT
{databaseContext}

### TASK
Generate a SQL query that will answer the user's question. The query should be:
1. Valid PostgreSQL syntax
2. Efficient and well-structured
3. Safe to execute (no DDL operations)
4. Focused on answering the specific question
5. Use the database schema and context to generate the query
6. Use the " in case of camel case strings in the query

### OUTPUT FORMAT
Return your response in this exact YAML format:

```yaml
thinking: |
    <your step-by-step reasoning about what tables to query, what joins are needed, etc.>
sql_query: |
    <the actual SQL query>
explanation: |
    <brief explanation of what the query does and how it answers the question>
```

### IMPORTANT
- Only return the YAML block, no additional text
- The SQL query should be properly formatted and ready to execute
- If you cannot generate a valid query, explain why in the thinking section
"""
        
        response = callLLM([prompt])
        
        # Extract YAML from response
        try:
            if "```yaml" in response:
                yamlStr = response.split("```yaml")[1].split("```")[0].strip()
            elif "```" in response:
                yamlStr = response.split("```")[1].split("```")[0].strip()
            else:
                yamlStr = response.strip()
            
            result = yaml.safe_load(yamlStr)
            return result
        except Exception as e:
            print(f"Error parsing YAML response: {e}")
            return {
                "thinking": "Failed to parse LLM response",
                "sql_query": "",
                "explanation": "Error occurred while generating SQL query"
            }


    def post(self, shared, prep_res, exec_res):
        """Store the generated SQL query and proceed"""
        # Store the query result in shared state
        shared["queryUsed"] = exec_res.get("sql_query", "")
        shared["queryThinking"] = exec_res.get("thinking", "")
        shared["queryExplanation"] = exec_res.get("explanation", "")
        
        print(f"✅ SQL query generated successfully!")
        print(f"📝 Query: {exec_res.get('sql_query', '')[:100]}...")
        
        # Return the next node to execute
        return "decide"
    

class ResponseChecker(Node):
    def prep(self, shared):
        """Prepare inputs for response checking"""
        question = shared.get("question", "No question provided.")
        queryUsed = shared.get("queryUsed", "No query used.")
        queryThinking = shared.get("queryThinking", "No query thinking provided.")
        queryExplanation = shared.get("queryExplanation", "No query explanation provided.")
        queryResult = shared.get("queryResult", "No query result returned.")

        return question, queryUsed, queryThinking, queryExplanation, queryResult
    
    
    def exec(self, inputs):
        """Check the response from the query"""
        question, queryUsed, queryThinking, queryExplanation, queryResult = inputs
        print("🤖 Checking the response from the query...")
        
        prompt = f"""
You are a data analyst that checks the responses of the query that has run based and sees if the query is correct and if it answers the question.

The question is: {question}

#### QUERY USED
{queryUsed}

#### QUERY THINKING
{queryThinking}

#### QUERY EXPLANATION
{queryExplanation}

### OUTPUT FORMAT
Return your response in this exact YAML format:

```yaml
correctData: <boolean>
refineQuestion: |
    <the refined question so that the query can be created in a more accurate way if the data is not correct>
```
"""
        response = callLLM([prompt])
        
        # Extract YAML from response
        try:
            if "```yaml" in response:
                yamlStr = response.split("```yaml")[1].split("```")[0].strip()
            elif "```" in response:
                yamlStr = response.split("```")[1].split("```")[0].strip()
            else:
                yamlStr = response.strip()
            
            result = yaml.safe_load(yamlStr)
            return result
        except Exception as e:
            print(f"Error parsing YAML response: {e}")
            return {
                "correctData": False,
                "refineQuestion": "Error occurred while parsing the response"
            }


    def post(self, shared, prep_res, exec_res):
        """Store the generated SQL query and proceed"""
        # Store the query result in shared state
        shared["correctData"] = exec_res.get("correctData", False)
        shared["question"] = exec_res.get("refineQuestion", shared["question"])
        
        # Return the next node to execute
        return "decide"