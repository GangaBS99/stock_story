# token_tracker.py

tool_token_usage = {
    "total_input_tokens": 0,
    "total_output_tokens": 0
}

def add_tool_tokens(input_tokens: int, output_tokens: int):
    tool_token_usage["total_input_tokens"] += input_tokens
    tool_token_usage["total_output_tokens"] += output_tokens

def get_total_tool_tokens():
    total_input = tool_token_usage["total_input_tokens"]
    total_output = tool_token_usage["total_output_tokens"]
    return total_input, total_output

def reset_tool_tokens():
    tool_token_usage["total_input_tokens"] = 0
    tool_token_usage["total_output_tokens"] = 0
