import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import os
from pathlib import Path


class DocumentKnowledgeBase:
    """Advanced knowledge base for storing and querying company documents."""
    
    def __init__(self):
        self.documents: Dict[str, List[Dict[str, Any]]] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
    
    def add_document(self, company_name: str, content: str, doc_type: str = "general", metadata: Optional[Dict] = None) -> str:
        """Add a document to the knowledge base."""
        if company_name not in self.documents:
            self.documents[company_name] = []
            self.metadata[company_name] = {}
        
        doc_id = f"{company_name}_{len(self.documents[company_name])}"
        document = {
            "id": doc_id,
            "content": content,
            "type": doc_type,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.documents[company_name].append(document)
        return doc_id
    
    def search_documents(self, query: str, company_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search documents by keyword matching."""
        query_lower = query.lower()
        results = []
        
        companies = [company_name] if company_name else self.documents.keys()
        
        for company in companies:
            if company not in self.documents:
                continue
                
            for doc in self.documents[company]:
                content_lower = doc["content"].lower()
                if query_lower in content_lower:
                    score = content_lower.count(query_lower)
                    results.append({
                        "company": company,
                        "document": doc,
                        "relevance_score": score
                    })
        
        return sorted(results, key=lambda x: x["relevance_score"], reverse=True)
    
    def get_company_documents(self, company_name: str) -> List[Dict[str, Any]]:
        """Get all documents for a specific company."""
        return self.documents.get(company_name, [])
    
    def answer_question(self, question: str, company_name: Optional[str] = None) -> Dict[str, Any]:
        """Answer a question using the knowledge base."""
        keywords = self._extract_keywords(question)
        relevant_docs = []
        
        for keyword in keywords:
            results = self.search_documents(keyword, company_name)
            relevant_docs.extend(results)
        
        if not relevant_docs:
            return {
                "answer": "No relevant information found in the knowledge base.",
                "sources": [],
                "confidence": 0.0
            }
        
        # Deduplicate and rank
        seen = set()
        unique_docs = []
        for doc in relevant_docs:
            doc_id = doc["document"]["id"]
            if doc_id not in seen:
                seen.add(doc_id)
                unique_docs.append(doc)
        
        # Get top document
        top_doc = unique_docs[0]
        doc = top_doc["document"]
        company = top_doc["company"]
        
        # Extract meaningful content (skip headers/formatting)
        content = self._clean_content(doc['content'])
        
        # Build structured answer
        answer = f"Based on {company} documents:\n\n{content[:800]}..."
        
        return {
            "answer": answer,
            "sources": [{"company": company, "doc_id": doc["id"], "type": doc["type"]}],
            "confidence": 0.8
        }
    
    def _clean_content(self, text: str) -> str:
        """Clean and format document content."""
        # Remove excessive whitespace and formatting artifacts
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'Page \d+ of \d+', '', text)
        text = re.sub(r'&amp;', '&', text)
        return text.strip()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from question."""
        stop_words = {"what", "when", "where", "who", "how", "is", "are", "the", "a", "an", "in", "on", "at", "tell", "me", "about"}
        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def get_all_companies(self) -> List[str]:
        """Get list of all companies in knowledge base."""
        return list(self.documents.keys())
    
    def delete_document(self, company_name: str, doc_id: str) -> bool:
        """Delete a specific document."""
        if company_name not in self.documents:
            return False
        
        self.documents[company_name] = [
            doc for doc in self.documents[company_name] 
            if doc["id"] != doc_id
        ]
        return True
    
    def load_from_folder(self, folder_path: str) -> Dict[str, int]:
        """Load documents from a folder. Returns count per company."""
        folder = Path(folder_path)
        if not folder.exists():
            return {}
        
        loaded = {}
        
        for file_path in folder.glob('*'):
            if file_path.is_file():
                company_name = file_path.stem.split('-')[0].strip()
                
                try:
                    if file_path.suffix.lower() == '.pdf':
                        content = self._extract_pdf_text(file_path)
                    elif file_path.suffix.lower() in ['.txt', '.md']:
                        content = file_path.read_text(encoding='utf-8')
                    else:
                        continue
                    
                    if content:
                        self.add_document(company_name, content, "document", {"source_file": file_path.name})
                        loaded[company_name] = loaded.get(company_name, 0) + 1
                except Exception as e:
                    print(f"Error loading {file_path.name}: {e}")
        
        return loaded
    
    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ' '.join(page.extract_text() for page in reader.pages)
                return text
        except ImportError:
            return f"PDF content from {pdf_path.name} (PyPDF2 not installed)"
        except Exception as e:
            return f"Error reading PDF: {str(e)}"


# Global instance
kb = DocumentKnowledgeBase()

# Load documents from docs folder
import os
docs_folder = os.path.join(os.path.dirname(__file__), 'docs')
if os.path.exists(docs_folder):
    loaded = kb.load_from_folder(docs_folder)
    print(f"Loaded documents: {loaded}")
