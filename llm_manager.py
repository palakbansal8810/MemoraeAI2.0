import os
from typing import List, Dict
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

class LLMManager:
    def __init__(self):
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        self.model_name = os.getenv('LLM_MODEL', 'mixtral-8x7b-32768')
        self.timezone = pytz.timezone('Asia/Kolkata')
        
        # Initialize Groq LLM
        self.llm = ChatGroq(
            groq_api_key=self.groq_api_key,
            model_name=self.model_name,
            temperature=0.7,
            max_tokens=2048
        )
    
    def get_system_prompt(self) -> str:
        """Generate system prompt with current time - called fresh each time"""
        current_datetime = datetime.now(self.timezone)
        current_time = current_datetime.strftime('%I:%M %p')  # 01:26 PM format
        current_date = current_datetime.strftime('%A, %B %d, %Y')  # Monday, January 28, 2026
        
        return f"""You are a helpful AI assistant integrated into a Telegram bot. You have access to:
- Conversation history and context
- User's images and their analysis
- User's voice notes and transcriptions
- User's lists and reminders
- Vector search for semantic memory retrieval

Your capabilities:
1. Remember and recall information from previous conversations
2. Analyze and describe images using the Gemini API
3. Process voice messages and transcribe them
4. Help users CREATE reminders (but you don't send them - the system does automatically)
5. Help users CREATE and manage lists
6. Search through user's memory semantically

IMPORTANT NOTES ABOUT REMINDERS:
- When a user asks to set a reminder, acknowledge it will be set by the system
- When a user asks why they weren't reminded, check if the reminder time has passed
- If reminder time hasn't passed yet, tell them to wait
- If reminder time has passed and they weren't notified, acknowledge there may be a technical issue
- You can see when reminders were created, but you don't personally send them

RESPONSE STYLE:
- Be natural and conversational
- Keep responses SHORT (1-3 sentences typically)
- Don't repeat information unnecessarily
- Don't be defensive or make excuses
- If something failed, acknowledge it simply and helpfully

Current time is {current_time} IST and current date is {current_date}. Timezone: IST (Indian Standard Time - UTC+5:30).
Always be concise, helpful, and honest. When users ask about images, lists, or reminders, use the provided context to give accurate answers.
Do not make up information."""
    
    def create_prompt_with_context(self, query: str, context: List[str] = None) -> str:
        """Create a prompt with retrieved context"""
        if context and len(context) > 0:
            context_str = "\n\n".join([f"Context {i+1}: {ctx}" for i, ctx in enumerate(context)])
            prompt = f"""Based on the following context from the user's memory:

{context_str}

User Query: {query}

Please provide a helpful response using the context when relevant."""
        else:
            prompt = query
        
        return prompt
    
    def generate_response(self, query: str, context: List[str] = None, conversation_history: List[Dict] = None) -> str:
        """Generate response using Groq LLM"""
        try:
            # Create messages with FRESH system prompt
            messages = [SystemMessage(content=self.get_system_prompt())]
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history[-10:]:  # Last 10 messages for context
                    if msg['role'] == 'user':
                        messages.append(HumanMessage(content=msg['content']))
                    elif msg['role'] == 'assistant':
                        messages.append(AIMessage(content=msg['content']))
            
            # Add current query with context
            final_query = self.create_prompt_with_context(query, context)
            messages.append(HumanMessage(content=final_query))
            
            # Generate response
            response = self.llm.invoke(messages)
            return response.content
        
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def extract_reminder_info(self, text: str) -> Dict:
        """Extract reminder information from text"""
        prompt = f"""Extract reminder information from the following text:
"{text}"

Return a JSON-like response with:
- content: what to remind about
- time: when to remind (in natural language)

If no clear reminder is found, return empty values."""

        try:
            messages = [
                SystemMessage(content="You are a helpful assistant that extracts reminder information from text."),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            return {"raw_response": response.content}
        except Exception as e:
            return {"error": str(e)}
    
    def extract_list_info(self, text: str) -> Dict:
        """Extract list information from text"""
        prompt = f"""Extract list information from the following text:
"{text}"

Return a JSON-like response with:
- name: name of the list
- items: list of items

If no clear list is found, return empty values."""

        try:
            messages = [
                SystemMessage(content="You are a helpful assistant that extracts list information from text."),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            return {"raw_response": response.content}
        except Exception as e:
            return {"error": str(e)}
    
    def detect_list_intent(self, text: str) -> dict:
        """
        Use LLM to detect list-related intent in natural language.
        
        Returns:
            dict with 'intent', 'list_name', 'item', 'action', or None if no intent detected
        """
        import json
        import logging
        
        logger = logging.getLogger(__name__)
        
        prompt = f"""Analyze this user message and determine if it's about list management:
"{text}"

Possible intents:
1. ADD_TO_LIST - User wants to add an item to a list
2. SHOW_LIST - User wants to see a specific list
3. SHOW_ALL_LISTS - User wants to see all their lists
4. DELETE_ITEM - User wants to remove/delete an item from a list
5. COMPLETE_ITEM - User wants to mark an item as done/completed
6. NONE - Not about lists

IMPORTANT: Questions about "tomorrow" or time-based queries are usually about reminders/tasks, NOT lists.
Only treat as list intent if explicitly mentions "list" or clearly refers to a named list.

Respond with ONLY a JSON object (no markdown, no explanation):
{{
  "intent": "ADD_TO_LIST" | "SHOW_LIST" | "SHOW_ALL_LISTS" | "DELETE_ITEM" | "COMPLETE_ITEM" | "NONE",
  "list_name": "name of the list (without 'list' suffix, e.g., 'shopping' not 'shopping list')",
  "item": "item to add/delete/complete",
  "confidence": 0.0 to 1.0
}}

Examples:
- "add sugar to shopping list" → {{"intent": "ADD_TO_LIST", "list_name": "shopping", "item": "sugar", "confidence": 0.95}}
- "show me my shopping list" → {{"intent": "SHOW_LIST", "list_name": "shopping", "item": null, "confidence": 0.9}}
- "what's in my todo list" → {{"intent": "SHOW_LIST", "list_name": "todo", "item": null, "confidence": 0.85}}
- "show all my lists" → {{"intent": "SHOW_ALL_LISTS", "list_name": null, "item": null, "confidence": 0.95}}
- "remove besan from shopping list" → {{"intent": "DELETE_ITEM", "list_name": "shopping", "item": "besan", "confidence": 0.93}}
- "mark eggs as done on shopping list" → {{"intent": "COMPLETE_ITEM", "list_name": "shopping", "item": "eggs", "confidence": 0.91}}
- "what do I have to do tomorrow?" → {{"intent": "NONE", "list_name": null, "item": null, "confidence": 0.95}}
- "how are you today?" → {{"intent": "NONE", "list_name": null, "item": null, "confidence": 0.99}}"""

        try:
            messages = [
                SystemMessage(content="You are an expert at understanding user intent for list management. Always respond with valid JSON only."),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            
            # Parse JSON response
            response_text = response.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            result = json.loads(response_text)
            
            # Only return if confidence is high enough and intent is not NONE
            if result.get("intent") != "NONE" and result.get("confidence", 0) > 0.7:
                # Map to the format expected by handle_list_intent
                intent_map = {
                    "ADD_TO_LIST": "add_to_list",
                    "SHOW_LIST": "show_list",
                    "SHOW_ALL_LISTS": "show_all_lists",
                    "DELETE_ITEM": "delete_item",
                    "COMPLETE_ITEM": "complete_item"
                }
                
                mapped_intent = intent_map.get(result["intent"])
                if not mapped_intent:
                    return None
                
                return {
                    "intent": mapped_intent,
                    "list_name": result.get("list_name"),
                    "item": result.get("item"),
                    "action": mapped_intent.replace("_", " ").split()[0],  # 'add', 'show', etc.
                    "confidence": result.get("confidence", 0.0)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting list intent: {e}", exc_info=True)
            return None
    
    def summarize_conversation(self, messages: List[Dict]) -> str:
        """Summarize a conversation"""
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" for msg in messages
        ])
        
        prompt = f"""Summarize the following conversation concisely:

{conversation_text}

Provide a brief summary highlighting key points and topics discussed."""

        try:
            messages_for_llm = [
                SystemMessage(content="You are a helpful assistant that summarizes conversations."),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages_for_llm)
            return response.content
        except Exception as e:
            return f"Error summarizing: {str(e)}"