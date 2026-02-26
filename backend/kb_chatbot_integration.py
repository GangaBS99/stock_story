from typing import Dict, Any, Optional
from document_knowledge_base import kb


def handle_knowledge_query(user_message: str, session_context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Process user query against knowledge base.
    Returns answer with sources if found, otherwise returns None.
    """
    # Only check knowledge base if TCS is mentioned
    if "tcs" not in user_message.lower():
        return None
    
    # Skip knowledge base for stock story generation requests
    skip_keywords = ["stock story", "create a", "generate", "summarize", "analyze"]
    if any(kw in user_message.lower() for kw in skip_keywords):
        return None
    
    # Query the knowledge base for TCS
    result = kb.answer_question(user_message, "TCS")
    
    if result["confidence"] > 0:
        return {
            "type": "knowledge_base_response",
            "answer": result["answer"],
            "sources": result["sources"],
            "confidence": result["confidence"],
            "company": "TCS"
        }
    
    return None


def add_company_document(company_name: str, content: str, doc_type: str = "general") -> str:
    """Add a new document to the knowledge base."""
    return kb.add_document(company_name, content, doc_type)


def search_knowledge_base(query: str, company: Optional[str] = None) -> list:
    """Search the knowledge base."""
    return kb.search_documents(query, company)


def get_company_info(company_name: str) -> list:
    """Get all documents for a company."""
    return kb.get_company_documents(company_name)
