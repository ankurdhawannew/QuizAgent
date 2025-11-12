"""
Coaching Agent using LangGraph and Socratic Method
This module provides a coaching agent that uses Socratic questioning
to help students arrive at the correct answer.
"""

import os
from typing import TypedDict, Annotated, Literal
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Fix for deprecated verbose attribute - set it before any LangChain/LangGraph imports
# This prevents the "module 'langchain' has no attribute 'verbose'" error
os.environ.setdefault("LANGCHAIN_VERBOSE", "false")
try:
    from langchain.globals import set_verbose
    set_verbose(False)
except (ImportError, AttributeError):
    # If the new API is not available, the environment variable should help
    pass

# Now import LangChain/LangGraph modules
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class CoachingState(TypedDict):
    """State for the coaching agent."""
    messages: Annotated[list, add_messages]
    question: str
    options: list
    user_answer: int
    correct_answer: int
    coaching_complete: bool
    student_understood: bool

def create_coaching_agent():
    """
    Create a LangGraph coaching agent that uses Socratic method.
    
    The agent follows this flow:
    1. Analyze the wrong answer
    2. Ask guiding questions (Socratic method)
    3. Provide hints without giving away the answer
    4. Check if student understands
    5. Reveal answer only if student is ready
    """
    
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        temperature=0.7,
        google_api_key=GOOGLE_API_KEY
    )
    
    def analyze_answer(state: CoachingState) -> CoachingState:
        """Analyze why the student's answer is wrong."""
        question = state["question"]
        options = state["options"]
        user_answer_idx = state["user_answer"]
        correct_answer_idx = state["correct_answer"]
        
        user_answer_text = options[user_answer_idx]
        correct_answer_text = options[correct_answer_idx]
        
        system_prompt = """You are a patient and encouraging math tutor using the Socratic method.
Your goal is to help the student understand why their answer is incorrect and guide them 
to discover the correct answer through thoughtful questioning, NOT by directly telling them.

Socratic Method Principles:
1. Ask open-ended questions that make the student think
2. Break down the problem into smaller parts
3. Guide them to identify their mistake
4. Help them understand the underlying concept
5. Never directly reveal the answer - help them discover it

Be encouraging, patient, and supportive. Make the student feel safe to think and explore."""
        
        analysis_prompt = f"""A student answered a math question incorrectly.

Question: {question}

Options:
A. {options[0]}
B. {options[1]}
C. {options[2]}
D. {options[3]}

Student's Answer: {chr(65 + user_answer_idx)}. {user_answer_text}
Correct Answer: {chr(65 + correct_answer_idx)}. {correct_answer_text}

Your task:
1. Analyze why the student might have chosen their answer
2. Identify the misconception or error in their thinking
3. Prepare to guide them using Socratic questioning

Provide a brief analysis (2-3 sentences) of the likely misconception."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=analysis_prompt)
        ]
        
        response = llm.invoke(messages)
        
        new_state = state.copy()
        new_state["messages"] = state["messages"] + [
            SystemMessage(content=system_prompt),
            HumanMessage(content=analysis_prompt),
            response
        ]
        
        return new_state
    
    def ask_guiding_question(state: CoachingState) -> CoachingState:
        """Ask a Socratic guiding question to help the student think."""
        question = state["question"]
        options = state["options"]
        user_answer_idx = state["user_answer"]
        correct_answer_idx = state["correct_answer"]
        messages = state["messages"]
        
        # Get conversation history
        conversation_history = "\n".join([
            f"{'Student' if isinstance(msg, HumanMessage) else 'Coach'}: {msg.content}"
            for msg in messages[-6:]  # Last few messages for context
        ])
        
        prompt = f"""Based on the conversation so far, ask ONE thoughtful Socratic question that will:
1. Help the student think about the problem differently
2. Guide them toward understanding the concept
3. Not directly reveal the answer

Question: {question}
Options: {options}
Student's wrong answer: {chr(65 + user_answer_idx)}. {options[user_answer_idx]}
Correct answer: {chr(65 + correct_answer_idx)}. {options[correct_answer_idx]}

Conversation so far:
{conversation_history}

Ask ONE open-ended question that guides their thinking. Keep it concise (1-2 sentences max)."""
        
        response = llm.invoke([
            SystemMessage(content="You are a Socratic tutor. Ask ONE guiding question."),
            HumanMessage(content=prompt)
        ])
        
        new_state = state.copy()
        new_state["messages"] = messages + [response]
        
        return new_state
    
    def provide_hint(state: CoachingState) -> CoachingState:
        """Provide a hint without revealing the answer."""
        question = state["question"]
        options = state["options"]
        user_answer_idx = state["user_answer"]
        correct_answer_idx = state["correct_answer"]
        messages = state["messages"]
        
        conversation_history = "\n".join([
            f"{'Student' if isinstance(msg, HumanMessage) else 'Coach'}: {msg.content}"
            for msg in messages[-8:]
        ])
        
        prompt = f"""Provide a helpful hint that:
1. Points the student in the right direction
2. Doesn't directly reveal the answer
3. Helps them understand the concept or method needed

Question: {question}
Options: {options}
Student's wrong answer: {chr(65 + user_answer_idx)}. {options[user_answer_idx]}
Correct answer: {chr(65 + correct_answer_idx)}. {options[correct_answer_idx]}

Conversation so far:
{conversation_history}

Provide a hint (2-3 sentences). Be encouraging."""
        
        response = llm.invoke([
            SystemMessage(content="You are a helpful tutor. Provide a hint without revealing the answer."),
            HumanMessage(content=prompt)
        ])
        
        new_state = state.copy()
        new_state["messages"] = messages + [response]
        
        return new_state
    
    def check_understanding(state: CoachingState) -> CoachingState:
        """Check if the student has understood and is ready for the answer."""
        messages = state["messages"]
        
        # Check if student has been engaged in conversation
        student_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
        
        if len(student_messages) >= 2:
            # Student has responded, check if they understand
            last_student_msg = student_messages[-1].content.lower()
            
            # Keywords that suggest understanding
            understanding_keywords = [
                "i understand", "i see", "i get it", "now i know", 
                "ah", "oh", "yes", "correct", "right", "got it"
            ]
            
            # Keywords that suggest they want the answer
            want_answer_keywords = [
                "what is", "tell me", "show me", "give me", 
                "the answer is", "i think it's"
            ]
            
            understood = any(keyword in last_student_msg for keyword in understanding_keywords)
            wants_answer = any(keyword in last_student_msg for keyword in want_answer_keywords)
            
            new_state = state.copy()
            new_state["student_understood"] = understood or wants_answer
            
            return new_state
        
        new_state = state.copy()
        new_state["student_understood"] = False
        return new_state
    
    def reveal_answer(state: CoachingState) -> CoachingState:
        """Reveal the correct answer with explanation."""
        question = state["question"]
        options = state["options"]
        correct_answer_idx = state["correct_answer"]
        messages = state["messages"]
        
        conversation_history = "\n".join([
            f"{'Student' if isinstance(msg, HumanMessage) else 'Coach'}: {msg.content}"
            for msg in messages[-10:]
        ])
        
        prompt = f"""The student has been guided through Socratic questioning and is ready to see the answer.

Question: {question}
Options: {options}
Correct Answer: {chr(65 + correct_answer_idx)}. {options[correct_answer_idx]}

Conversation so far:
{conversation_history}

Provide:
1. The correct answer clearly
2. A brief explanation of why it's correct
3. A summary of the key concept they should remember
4. Encouragement for their effort

Keep it concise and encouraging (3-4 sentences)."""
        
        response = llm.invoke([
            SystemMessage(content="You are a supportive tutor revealing the answer after Socratic guidance."),
            HumanMessage(content=prompt)
        ])
        
        new_state = state.copy()
        new_state["messages"] = messages + [response]
        new_state["coaching_complete"] = True
        
        return new_state
    
    def should_continue_coaching(state: CoachingState) -> Literal["ask_question", "provide_hint", "reveal_answer"]:
        """Decide the next step in coaching."""
        if state.get("coaching_complete", False):
            return "reveal_answer"
        
        messages = state["messages"]
        coach_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        student_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
        
        # If student hasn't responded yet, ask a question
        if len(student_messages) == 0:
            return "ask_question"
        
        # If we've asked 2+ questions, provide a hint
        if len(coach_messages) >= 2:
            return "provide_hint"
        
        # Otherwise, continue asking questions
        return "ask_question"
    
    # Build the graph
    workflow = StateGraph(CoachingState)
    
    # Add nodes
    workflow.add_node("analyze", analyze_answer)
    workflow.add_node("ask_question", ask_guiding_question)
    workflow.add_node("provide_hint", provide_hint)
    workflow.add_node("check_understanding", check_understanding)
    workflow.add_node("reveal_answer", reveal_answer)
    
    # Set entry point
    workflow.set_entry_point("analyze")
    
    # Add edges
    workflow.add_edge("analyze", "ask_question")
    workflow.add_conditional_edges(
        "ask_question",
        should_continue_coaching,
        {
            "ask_question": "ask_question",
            "provide_hint": "provide_hint",
            "reveal_answer": "reveal_answer"
        }
    )
    workflow.add_conditional_edges(
        "provide_hint",
        should_continue_coaching,
        {
            "ask_question": "ask_question",
            "provide_hint": "provide_hint",
            "reveal_answer": "reveal_answer"
        }
    )
    workflow.add_edge("reveal_answer", END)
    
    return workflow.compile()

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
            return "Coaching service configuration issue. Please ensure all LangChain packages are up to date. Try: pip install --upgrade langchain langchain-core langgraph"
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

