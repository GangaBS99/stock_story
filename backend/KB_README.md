# Document Knowledge Base System

## Overview
Advanced knowledge base system that loads company documents from the `docs/` folder and answers questions using stored information.

## Features
- Automatic PDF document loading from `backend/docs/` folder
- Keyword-based search and question answering
- Integration with chatbot API
- Source tracking and confidence scoring

## Files Created
1. `document_knowledge_base.py` - Core knowledge base with document storage and search
2. `kb_chatbot_integration.py` - Integration layer for chatbot
3. `verify_kb.py` - Verification script

## How It Works

### 1. Document Loading
- Place PDF/TXT files in `backend/docs/` folder
- Files are automatically loaded when the module imports
- Company name is extracted from filename (e.g., "Press Release - INR.pdf" → "Press Release")

### 2. Chatbot Integration
The chatbot now checks the knowledge base BEFORE calling the AI agent:
- User asks a question
- System searches knowledge base for relevant documents
- If found, returns answer with sources
- If not found, falls back to AI agent

### 3. Usage in app.py
```python
from kb_chatbot_integration import handle_knowledge_query

# In /process_message endpoint:
kb_response = handle_knowledge_query(user_message)
if kb_response:
    return {
        "output": kb_response["answer"],
        "sources": kb_response["sources"],
        "confidence": kb_response["confidence"]
    }
```

## Current Status
✓ Loaded 2 PDF documents from docs/ folder (Press Release - INR.pdf, Press Release - USD.pdf)
✓ 4 companies in knowledge base (Press Release, Tesla, Apple, Microsoft)
✓ Integrated with chatbot API
✓ Ready to answer questions

## Example Questions
- "What is the revenue of Press Release?"
- "Tell me about INR"
- "What products does Apple have?"
- "Microsoft Azure information"

## Adding New Documents
1. Place document files in `backend/docs/` folder
2. Restart the application
3. Documents are automatically loaded and indexed

## API Response Format
```json
{
  "output": "Answer from knowledge base",
  "sources": [{"company": "...", "doc_id": "...", "type": "..."}],
  "confidence": 0.8,
  "suggestions": ["Tell me more", "Show other companies"]
}
```
