import json
from langchain_tavily import TavilySearch
from openai import AsyncOpenAI
import chainlit as cl

# Initialize OpenAI client for document generation
client = AsyncOpenAI()

def search_tool(query):
    """Perform web search using Tavily to find relevant information"""
    try:
        # Create Tavily search tool with optimized settings
        search = TavilySearch(
            max_results=5,
            topic="general",
            include_domains=None,  # Allow all domains for broader results
            exclude_domains=None,
            search_depth="basic"  # Use basic search for faster results
        )
        
        # Perform the search
        results = search.invoke({"query": query})
        
        # Format results for better readability
        if isinstance(results, dict) and 'results' in results:
            formatted_results = "Search Results:\n\n"
            for i, result in enumerate(results['results'], 1):
                formatted_results += f"{i}. {result.get('title', 'No title')}\n"
                formatted_results += f"   {result.get('content', 'No content')[:200]}...\n"
                formatted_results += f"   URL: {result.get('url', 'No URL')}\n"
                if result.get('score'):
                    formatted_results += f"   Relevance Score: {result.get('score'):.2f}\n"
                formatted_results += "\n"
            return formatted_results
        else:
            return str(results)
    except Exception as e:
        return f"Search failed: {str(e)}"

async def download_document_tool(conversation_summary, requirements_focus):
    """Generate a structured requirements document and return the content"""
    try:
        # Create a comprehensive prompt for document generation
        document_prompt = f"""
        Based on the following conversation summary and requirements focus, create a well-structured software requirements document.
        
        Conversation Summary: {conversation_summary}
        Requirements Focus: {requirements_focus}
        
        Please create a professional requirements document that includes:
        1. Executive Summary
        2. Project Overview
        3. Functional Requirements
        4. Non-Functional Requirements
        5. User Stories (if applicable)
        6. Acceptance Criteria
        7. Assumptions and Constraints
        8. Glossary of Terms
        
        Format the document in a clear, professional manner suitable for stakeholders and development teams.
        """
        
        # Generate the document using OpenAI
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert requirements engineer. Create clear, structured, and professional software requirements documents."},
                {"role": "user", "content": document_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        document_content = response.choices[0].message.content
        
        # Return just the document content - let the main app handle the file creation
        return f"Requirements document generated successfully! Document content:\n\n{document_content}"
        
    except Exception as e:
        return f"Document generation failed: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_tool",
            "description": "Search the web for relevant information, best practices, examples, or industry standards related to requirements engineering",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant information about requirements engineering, software development, or related topics",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_document_tool",
            "description": "Generate a structured requirements document based on the conversation history and make it available for download",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_summary": {
                        "type": "string",
                        "description": "A summary of the key points discussed in the conversation about requirements",
                    },
                    "requirements_focus": {
                        "type": "string",
                        "description": "The specific focus area or main requirement being discussed",
                    },
                },
                "required": ["conversation_summary", "requirements_focus"],
            },
        },
    }
]