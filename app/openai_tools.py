TOOLS = [
    {
        "type": "function",
        "name": "extract_intelligence",
        "description": "Extract UPI IDs, bank account numbers, phone numbers, and URLs from text.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to extract entities from"}
            },
            "required": ["text"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "evaluate_stop_condition",
        "description": "Decide whether the agent should stop engaging and trigger final callback.",
        "parameters": {
            "type": "object",
            "properties": {
                "should_stop": {
                    "type": "boolean",
                    "description": "Whether to stop the session now"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for stopping"
                }
            },
            "required": ["should_stop", "reason"]
        }
    }
]
