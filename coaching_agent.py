"""
Coaching Agent using Socratic Method
This module provides a coaching agent that uses Socratic questioning
to help students arrive at the correct answer.
"""

import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Fix for deprecated verbose attribute - set it before any LangChain imports
# This prevents the "module 'langchain' has no attribute 'verbose'" error
os.environ.setdefault("LANGCHAIN_VERBOSE", "false")
try:
    from langchain.globals import set_verbose
    set_verbose(False)
except (ImportError, AttributeError):
    # If the new API is not available, the environment variable should help
    pass

# Now import LangChain modules
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_coaching_response(
    question: str,
    options: list,
    user_answer: int,
    correct_answer: int,
    student_response: str = None,
    conversation_history: list = None
) -> str:
    """
    Get a coaching response using the Socratic method.
    
    Args:
        question: The quiz question
        options: List of answer options
        user_answer: Index of user's answer (0-3)
        correct_answer: Index of correct answer (0-3)
        student_response: Optional student response to continue conversation
        conversation_history: Previous messages in the conversation
    
    Returns:
        Coaching message from the agent
    """
    try:
        if not GOOGLE_API_KEY:
            return "Coaching is not available. Please set GOOGLE_API_KEY in your environment."
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.7,
            google_api_key=GOOGLE_API_KEY
        )
        
        system_prompt = """You are a patient and encouraging math tutor using the Socratic method.
Your goal is to help the student understand why their answer is incorrect and guide them 
to discover the correct answer through thoughtful questioning, NOT by directly telling them.

Socratic Method Principles:
1. Ask open-ended questions that make the student think
2. Break down the problem into smaller parts
3. Guide them to identify their mistake
4. Help them understand the underlying concept
5. Never directly reveal the answer - help them discover it

Be encouraging, patient, and supportive. Make the student feel safe to think and explore.
Keep your responses concise (2-3 sentences)."""
        
        # Validate inputs
        if not options or len(options) < 4:
            return "Error: Invalid question options. Please try again."
        
        if user_answer < 0 or user_answer >= len(options):
            return "Error: Invalid user answer index. Please try again."
        
        if correct_answer < 0 or correct_answer >= len(options):
            return "Error: Invalid correct answer index. Please try again."
        
        # Build conversation context
        context = f"""Question: {question}

Options:
A. {options[0]}
B. {options[1]}
C. {options[2]}
D. {options[3]}

Student's wrong answer: {chr(65 + user_answer)}. {options[user_answer]}
Correct answer: {chr(65 + correct_answer)}. {options[correct_answer]}"""
        
        # Add conversation history if available
        if conversation_history and len(conversation_history) > 0:
            context += "\n\nPrevious conversation:\n"
            # Safely get last 4 messages
            recent_messages = conversation_history[-4:] if len(conversation_history) >= 4 else conversation_history
            for msg in recent_messages:
                if isinstance(msg, dict):
                    role = "Student" if msg.get("role") == "student" else "Coach"
                    context += f"{role}: {msg.get('content', '')}\n"
        
        if student_response:
            prompt = f"""{context}

Student just said: "{student_response}"

Respond to the student's message. Continue guiding them using Socratic questioning. 
If they seem to understand or ask for the answer, you can reveal it with an explanation."""
        else:
            prompt = f"""{context}

Start the coaching session. Ask the student ONE thoughtful Socratic question that will help them 
think about the problem differently and guide them toward understanding why their answer is incorrect."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except AttributeError as e:
        if "verbose" in str(e).lower():
            # Retry with explicit verbose setting
            try:
                from langchain.globals import set_verbose
                set_verbose(False)
                # Recreate LLM and messages
                llm_retry = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    temperature=0.7,
                    google_api_key=GOOGLE_API_KEY
                )
                messages_retry = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt)
                ]
                response = llm_retry.invoke(messages_retry)
                return response.content
            except Exception as retry_error:
                return f"Coaching service encountered an issue. Please try again or skip to see the answer. Error: {str(retry_error)}"
        return f"I encountered an error while coaching. Please try again. Error: {str(e)}"
    except Exception as e:
        error_msg = str(e)
        if "verbose" in error_msg.lower():
            return "Coaching service configuration issue. Please ensure all LangChain packages are up to date. Try: pip install --upgrade langchain langchain-core"
        return f"I encountered an error while coaching. Please try again. Error: {error_msg}"

def start_coaching_session(
    question: str,
    options: list,
    user_answer: int,
    correct_answer: int
) -> dict:
    """
    Start a new coaching session.
    
    Returns:
        Dictionary with initial coaching message and session state
    """
    try:
        initial_message = get_coaching_response(
            question=question,
            options=options,
            user_answer=user_answer,
            correct_answer=correct_answer,
            student_response=None,
            conversation_history=None
        )
        
        return {
            "initial_message": initial_message,
            "state": None,
            "is_complete": False
        }
        
    except Exception as e:
        return {
            "initial_message": f"Error starting coaching session: {str(e)}",
            "state": None,
            "is_complete": False
        }

