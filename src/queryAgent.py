from pocketflow import Flow
from agentNodes import GetTools, DecideAction, ExecuteToolNode, ResponseChecker

# Create nodes
getTools = GetTools()
decideAction = DecideAction()
executeTool = ExecuteToolNode()
responseChecker = ResponseChecker()

# Connect nodes
getTools >> "decide" >> decideAction
decideAction >> "create_query_SQL" >> executeTool
decideAction >> "execute_sql" >> executeTool
decideAction >> "list_tables" >> executeTool
executeTool >> "responseChecker" >> responseChecker
responseChecker >> "decide" >> decideAction

# Create workflow
flow = Flow(start=getTools)


def runQueryAgent(question, databaseContext=""):
    """Run the query agent with a question"""
    
    # Initialize shared state
    shared = {
        "question": question,
        "databaseContext": databaseContext,
        "queryUsed": "",
        "queryResult": "",
        "queryThinking": "",
        "queryExplanation": "",
        "correctData": True,
        "chosenAction": "",
        "actionReason": "",
        "actionParameters": {}
    }
    
    # Run the flow
    print("🚀 Starting Query Agent...")
    print(f"📝 Question: {question}")
    print("=" * 50)
    
    try:
        flow.run(shared)
        
        # Return the results
        return {
            "question": shared.get("question", ""),
            "query_used": shared.get("queryUsed", ""),
            "query_result": shared.get("queryResult", ""),
            "query_explanation": shared.get("queryExplanation", ""),
            "chosen_action": shared.get("chosenAction", ""),
            "action_reason": shared.get("actionReason", "")
        }
        
    except Exception as e:
        print(f"❌ Error running query agent: {e}")
        return {
            "error": str(e),
            "question": question
        }


if __name__ == "__main__":
    # Example usage
    question = "How many users do we have in our database?"
    databaseContext = "Tables: users (id, name, email, created_at), orders (id, user_id, amount, created_at)"
    
    result = runQueryAgent(question, databaseContext)
    
    if "error" not in result:
        print("\n" + "=" * 50)
        print("🎉 QUERY AGENT RESULTS")
        print("=" * 50)
        print(f"Question: {result['question']}")
        print(f"Chosen Action: {result['chosen_action']}")
        print(f"Action Reason: {result['action_reason']}")
        print(f"Query Used: {result['query_used']}")
        print(f"Query Result: {result['query_result']}")
    else:
        print(f"Error: {result['error']}")