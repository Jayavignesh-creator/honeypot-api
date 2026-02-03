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
    }
]
