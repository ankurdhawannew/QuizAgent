import streamlit as st
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional
from datetime import datetime
from coaching_agent import get_coaching_response, start_coaching_session

# Load environment variables
load_dotenv()

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Scoring system
SCORING = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 4
}

# File to store user quiz history
QUIZ_HISTORY_FILE = "user_quiz_history.json"

def load_user_history() -> Dict:
    """Load user quiz history from JSON file."""
    if os.path.exists(QUIZ_HISTORY_FILE):
        try:
            with open(QUIZ_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_user_history(history: Dict):
    """Save user quiz history to JSON file."""
    try:
        with open(QUIZ_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except IOError as e:
        st.error(f"Error saving quiz history: {e}")

def get_user_previous_questions(user_name: str, grade: int, board: str, topic: str) -> List[str]:
    """Get list of previous question texts for a user with same parameters."""
    history = load_user_history()
    if user_name not in history:
        return []
    
    user_history = history[user_name]
    previous_questions = []
    
    # Collect all questions from previous quizzes with same parameters
    for quiz in user_history.get("quizzes", []):
        if (quiz.get("grade") == grade and 
            quiz.get("board") == board and 
            quiz.get("topic", "").lower() == topic.lower()):
            previous_questions.extend(quiz.get("questions", []))
    
    return previous_questions

def save_user_quiz(user_name: str, grade: int, board: str, topic: str, questions: List[Dict]):
    """Save generated questions for a user."""
    history = load_user_history()
    
    if user_name not in history:
        history[user_name] = {"quizzes": []}
    
    # Extract question texts for tracking
    question_texts = [q.get("question", "") for q in questions]
    
    # Add new quiz entry
    quiz_entry = {
        "grade": grade,
        "board": board,
        "topic": topic,
        "questions": question_texts,
        "timestamp": datetime.now().isoformat()
    }
    
    history[user_name]["quizzes"].append(quiz_entry)
    save_user_history(history)

def generate_questions(
    grade: int,
    board: str,
    topic: str,
    num_questions: int,
    difficulty_distribution: Dict[str, int],
    user_name: Optional[str] = None,
    previous_questions: Optional[List[str]] = None
) -> List[Dict]:
    """
    Generate quiz questions using a LLM.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        num_questions: Total number of questions
        difficulty_distribution: Dictionary with Easy, Medium, Hard percentages
        user_name: Optional user name for tracking
        previous_questions: Optional list of previous question texts to avoid
        
    Returns:
        List of question dictionaries
    """
    if not GOOGLE_API_KEY:
        st.error("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.")
        return []
    
    # Calculate number of questions per difficulty level
    easy_count = int(num_questions * difficulty_distribution["Easy"] / 100)
    medium_count = int(num_questions * difficulty_distribution["Medium"] / 100)
    hard_count = num_questions - easy_count - medium_count  # Ensure total matches
    
    # Create prompt for question generation
    uniqueness_note = ""
    if previous_questions and len(previous_questions) > 0:
        uniqueness_note = f"""

IMPORTANT: The user has already seen questions on this topic. You MUST generate completely NEW and DIFFERENT questions. 
Do NOT repeat or rephrase any of these previously asked questions:
{chr(10).join([f"- {q}" for q in previous_questions[:10]])}  # Show max 10 to avoid prompt bloat
{"... and more" if len(previous_questions) > 10 else ""}

Generate fresh, unique questions that the user has not seen before."""

    prompt = f"""Generate {num_questions} multiple-choice math questions for Grade {grade} students following the {board} curriculum.

Topic: {topic}
Difficulty Distribution:
- Easy: {easy_count} questions
- Medium: {medium_count} questions  
- Hard: {hard_count} questions
{uniqueness_note}

Requirements:
1. Each question must have exactly 4 options (A, B, C, D)
2. Only one option should be correct
3. Questions should be appropriate for Grade {grade} level and {board} curriculum
4. Questions should cover the topic: {topic}
5. Difficulty levels should match the distribution above
6. Questions must be unique and different from any previously asked questions

Return the response as a JSON array with the following structure:
[
  {{
    "question": "Question text here",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": 0,
    "difficulty": "Easy"
  }},
  ...
]

Do not add A, B, C, D to the options.

The correct_answer should be the index (0-3) of the correct option.
The difficulty should be one of: "Easy", "Medium", or "Hard".

Generate exactly {num_questions} questions with the specified difficulty distribution."""

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        response = model.generate_content(prompt)
        
        # Extract JSON from response
        response_text = response.text
        
        # Try to extract JSON if it's wrapped in markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        questions = json.loads(response_text)
        
        # Validate and ensure we have the right number of questions
        if not isinstance(questions, list):
            questions = [questions]
        
        # Ensure correct_answer is an integer index
        for q in questions:
            if isinstance(q.get("correct_answer"), str):
                # Convert "A" -> 0, "B" -> 1, etc.
                q["correct_answer"] = ord(q["correct_answer"].upper()) - ord("A")
            q["correct_answer"] = int(q["correct_answer"])
        
        return questions[:num_questions]
        
    except json.JSONDecodeError as e:
        st.error(f"Error parsing JSON response: {e}")
        st.text("Raw response:")
        st.text(response_text if 'response_text' in locals() else "No response")
        return []
    except Exception as e:
        st.error(f"Error generating questions: {e}")
        return []

def initialize_session_state():
    """Initialize session state variables."""
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "current_question_index" not in st.session_state:
        st.session_state.current_question_index = 0
    if "user_answers" not in st.session_state:
        st.session_state.user_answers = []
    if "score" not in st.session_state:
        st.session_state.score = 0
    if "quiz_started" not in st.session_state:
        st.session_state.quiz_started = False
    if "show_feedback" not in st.session_state:
        st.session_state.show_feedback = False
    if "quiz_completed" not in st.session_state:
        st.session_state.quiz_completed = False
    if "user_name" not in st.session_state:
        st.session_state.user_name = ""
    if "coaching_active" not in st.session_state:
        st.session_state.coaching_active = False
    if "coaching_messages" not in st.session_state:
        st.session_state.coaching_messages = []
    if "coaching_complete" not in st.session_state:
        st.session_state.coaching_complete = False

def reset_quiz():
    """Reset quiz state."""
    st.session_state.questions = []
    st.session_state.current_question_index = 0
    st.session_state.user_answers = []
    st.session_state.score = 0
    st.session_state.quiz_started = False
    st.session_state.show_feedback = False
    st.session_state.quiz_completed = False
    st.session_state.coaching_active = False
    st.session_state.coaching_messages = []
    st.session_state.coaching_complete = False
    # Note: user_name is preserved on reset

def main():
    st.set_page_config(page_title="Math Quiz Agent", page_icon="📚", layout="wide")
    
    st.title("📚 Math Quiz Agent")
    st.markdown("Generate and take personalized math quizzes based on your grade, board, and topic!")
    
    initialize_session_state()
    
    # Sidebar for quiz configuration
    with st.sidebar:
        st.header("Quiz Configuration")
        
        # User name input
        st.subheader("User Information")
        user_name = st.text_input("Your Name", value=st.session_state.user_name, placeholder="Enter your name")
        if user_name:
            # Check if name changed before updating
            previous_name = st.session_state.get("user_name", "")
            if user_name != previous_name and previous_name and st.session_state.quiz_started:
                # If name changed, reset quiz
                reset_quiz()
            st.session_state.user_name = user_name
        else:
            st.warning("⚠️ Please enter your name to start the quiz")
        
        st.divider()
        
        # Grade selection
        grade = st.selectbox("Grade", options=list(range(6, 13)), index=0)
        
        # Board selection
        board = st.selectbox("Board", options=["CBSE", "ICSE", "IB"])
        
        # Topic input
        topic = st.text_input("Math Topic", placeholder="e.g., Simple Equations, Mensuration, Geometry, Trigonometry")
        
        # Difficulty distribution
        st.subheader("Difficulty Distribution")
        easy_pct = st.slider("Easy (%)", min_value=0, max_value=100, value=20, step=5)
        medium_pct = st.slider("Medium (%)", min_value=0, max_value=100, value=40, step=5)
        hard_pct = st.slider("Hard (%)", min_value=0, max_value=100, value=20, step=5)
        
        # Calculate total
        total_pct = easy_pct + medium_pct + hard_pct
        
        # Validation
        if total_pct != 100:
            st.error(f"⚠️ Total must be 100% (Current: {total_pct}%)")
            can_start = False
        else:
            st.success(f"✓ Total: {total_pct}%")
            can_start = True
        
        difficulty_distribution = {
            "Easy": easy_pct,
            "Medium": medium_pct,
            "Hard": hard_pct
        }
        
        # Number of questions
        num_questions = st.number_input("Number of Questions", min_value=1, max_value=20, value=10, step=1)
        
        # Generate quiz button
        if st.button("Generate Quiz", type="primary", disabled=not can_start or not topic or not user_name):
            if not user_name:
                st.error("Please enter your name")
            elif not topic:
                st.error("Please enter a math topic")
            else:
                # Get previous questions for this user
                previous_questions = get_user_previous_questions(user_name, grade, board, topic)
                
                if previous_questions:
                    st.info(f"📝 You've taken {len([q for q in load_user_history().get(user_name, {}).get('quizzes', []) if q.get('grade') == grade and q.get('board') == board and q.get('topic', '').lower() == topic.lower()])} quiz(zes) on this topic. Generating new questions...")
                
                with st.spinner("Generating questions..."):
                    questions = generate_questions(
                        grade=grade,
                        board=board,
                        topic=topic,
                        num_questions=num_questions,
                        difficulty_distribution=difficulty_distribution,
                        user_name=user_name,
                        previous_questions=previous_questions
                    )
                    
                    if questions:
                        st.session_state.questions = questions
                        st.session_state.quiz_started = True
                        st.session_state.current_question_index = 0
                        st.session_state.user_answers = []
                        st.session_state.score = 0
                        st.session_state.show_feedback = False
                        st.session_state.quiz_completed = False
                        
                        # Save quiz to user history
                        save_user_quiz(user_name, grade, board, topic, questions)
                        
                        st.success(f"Generated {len(questions)} questions!")
                        st.rerun()
                    else:
                        st.error("Failed to generate questions. Please try again.")
        
        # Reset quiz button
        if st.session_state.quiz_started:
            if st.button("Reset Quiz"):
                reset_quiz()
                st.rerun()
    
    # Main quiz area
    if not st.session_state.quiz_started:
        st.info("👈 Configure your quiz in the sidebar and click 'Generate Quiz' to start!")
        st.markdown("""
        ### How to use:
        1. Select your grade (6-12)
        2. Choose your education board (CBSE, ICSE, or IB)
        3. Enter a math topic
        4. Adjust difficulty distribution (must total 100%)
        5. Set the number of questions
        6. Click "Generate Quiz"
        """)
    elif st.session_state.quiz_completed:
        # Show final results
        st.header("🎉 Quiz Completed!")
        
        total_possible = sum(
            SCORING.get(q.get("difficulty", "Easy"), 1) 
            for q in st.session_state.questions
        )
        
        st.metric("Your Score", f"{st.session_state.score} / {total_possible}")
        
        # Detailed breakdown
        st.subheader("Question Review")
        for i, (question, user_answer) in enumerate(zip(st.session_state.questions, st.session_state.user_answers)):
            correct_answer_idx = question["correct_answer"]
            is_correct = user_answer == correct_answer_idx
            difficulty = question.get("difficulty", "Easy")
            points = SCORING.get(difficulty, 1) if is_correct else 0
            
            with st.expander(f"Question {i+1} ({difficulty}) - {'✓ Correct' if is_correct else '✗ Incorrect'} - {points} point(s)"):
                st.markdown(f"**{question['question']}**")
                st.markdown("**Options:**")
                for idx, option in enumerate(question["options"]):
                    marker = ""
                    if idx == correct_answer_idx:
                        marker = " ✓ Correct Answer"
                    if idx == user_answer and not is_correct:
                        marker = " ✗ Your Answer (Incorrect)"
                    st.markdown(f"{chr(65+idx)}. {option}{marker}")
                
                if not is_correct:
                    st.info(f"Correct answer: {chr(65+correct_answer_idx)}. {question['options'][correct_answer_idx]}")
        
        if st.button("Take Another Quiz"):
            reset_quiz()
            st.rerun()
    
    else:
        # Show current question
        if st.session_state.current_question_index < len(st.session_state.questions):
            question = st.session_state.questions[st.session_state.current_question_index]
            question_num = st.session_state.current_question_index + 1
            total_questions = len(st.session_state.questions)
            difficulty = question.get("difficulty", "Easy")
            
            # Progress bar
            progress = question_num / total_questions
            st.progress(progress)
            st.caption(f"Question {question_num} of {total_questions} | Difficulty: {difficulty} | Score: {st.session_state.score}")
            
            st.subheader(f"Question {question_num}")
            st.markdown(f"**{question['question']}**")
            st.markdown(f"*Difficulty: {difficulty}*")
            
            if not st.session_state.show_feedback:
                # Display options as buttons
                selected_answer = None
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"A. {question['options'][0]}", key="option_0", use_container_width=True):
                        selected_answer = 0
                    if st.button(f"B. {question['options'][1]}", key="option_1", use_container_width=True):
                        selected_answer = 1
                with col2:
                    if st.button(f"C. {question['options'][2]}", key="option_2", use_container_width=True):
                        selected_answer = 2
                    if st.button(f"D. {question['options'][3]}", key="option_3", use_container_width=True):
                        selected_answer = 3
                
                if selected_answer is not None:
                    st.session_state.user_answers.append(selected_answer)
                    st.session_state.show_feedback = True
                    # Reset coaching state for new answer
                    st.session_state.coaching_active = False
                    st.session_state.coaching_messages = []
                    st.session_state.coaching_complete = False
                    st.rerun()
            else:
                # Show feedback
                user_answer = st.session_state.user_answers[-1]
                correct_answer_idx = question["correct_answer"]
                is_correct = user_answer == correct_answer_idx
                
                if is_correct:
                    st.success(f"✓ Correct! You selected {chr(65+user_answer)}. {question['options'][user_answer]}")
                    # Calculate points
                    points = SCORING.get(difficulty, 1)
                    st.session_state.coaching_complete = True
                    st.balloons()
                else:
                    points = 0
                    # Wrong answer - offer coaching
                    st.error(f"✗ Incorrect. You selected {chr(65+user_answer)}. {question['options'][user_answer]}")
                    
                    # Show all options with markers (but not the correct answer yet)
                    st.markdown("**All Options:**")
                    for idx, option in enumerate(question["options"]):
                        marker = ""
                        if idx == user_answer:
                            marker = " ✗ Your Answer"
                        st.markdown(f"{chr(65+idx)}. {option}{marker}")
                    
                    # Coaching section
                    if not st.session_state.coaching_active and not st.session_state.coaching_complete:
                        st.info("💡 Want to understand why your answer is incorrect? Get personalized coaching using the Socratic method!")
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            if st.button("🎓 Get Coaching", type="primary", use_container_width=True):
                                st.session_state.coaching_active = True
                                st.session_state.coaching_messages = []
                                st.session_state.coaching_complete = False
                                
                                # Start coaching session
                                with st.spinner("Starting coaching session..."):
                                    coaching_session = start_coaching_session(
                                        question=question['question'],
                                        options=question['options'],
                                        user_answer=user_answer,
                                        correct_answer=correct_answer_idx
                                    )
                                    
                                    if coaching_session and coaching_session.get("initial_message"):
                                        st.session_state.coaching_messages.append({
                                            "role": "coach",
                                            "content": coaching_session["initial_message"]
                                        })
                                st.rerun()
                        
                        with col2:
                            if st.button("Skip to Answer", use_container_width=True):
                                st.session_state.coaching_complete = True
                                st.session_state.coaching_active = False
                                st.session_state.coaching_messages = []
                                st.rerun()
                    
                    # Show coaching conversation
                    if st.session_state.coaching_active:
                        st.divider()
                        st.subheader("🎓 Coaching Session")
                        
                        # Display coaching messages
                        for msg in st.session_state.coaching_messages:
                            if msg["role"] == "coach":
                                with st.chat_message("assistant"):
                                    st.markdown(msg["content"])
                            elif msg["role"] == "student":
                                with st.chat_message("user"):
                                    st.markdown(msg["content"])
                        
                        # If coaching is complete, show the answer
                        if st.session_state.coaching_complete:
                            st.success(f"✅ Correct answer: {chr(65+correct_answer_idx)}. {question['options'][correct_answer_idx]}")
                        else:
                            # Student response input
                            student_response = st.chat_input("Type your response or question here...")
                            
                            if student_response:
                                # Add student message
                                st.session_state.coaching_messages.append({
                                    "role": "student",
                                    "content": student_response
                                })
                                
                                # Get coaching response
                                with st.spinner("Coach is thinking..."):
                                    coaching_response = get_coaching_response(
                                        question=question['question'],
                                        options=question['options'],
                                        user_answer=user_answer,
                                        correct_answer=correct_answer_idx,
                                        student_response=student_response,
                                        conversation_history=st.session_state.coaching_messages
                                    )
                                    
                                    if coaching_response:
                                        st.session_state.coaching_messages.append({
                                            "role": "coach",
                                            "content": coaching_response
                                        })
                                        
                                        # Check if answer was revealed
                                        if "correct answer" in coaching_response.lower() or "answer is" in coaching_response.lower():
                                            st.session_state.coaching_complete = True
                                
                                st.rerun()
                            
                            # Option to skip to answer
                            if st.button("Show Answer", key="show_answer"):
                                st.session_state.coaching_complete = True
                                st.rerun()
                        
                        # Show answer if coaching is complete
                        #if st.session_state.coaching_complete:
                        #    st.success(f"✅ Correct answer: {chr(65+correct_answer_idx)}. {question['options'][correct_answer_idx]}")
                    
                    # Show correct answer if coaching was skipped (coaching_complete but not active)
                if st.session_state.coaching_complete and not st.session_state.coaching_active:
                    if not is_correct:
                        st.divider()
                        st.success(f"✅ Correct answer: {chr(65+correct_answer_idx)}. {question['options'][correct_answer_idx]}")
                        
                    # Show all options with markers
                    st.markdown("**All Options:**")
                    for idx, option in enumerate(question["options"]):
                        marker = ""
                        if idx == correct_answer_idx:
                            marker = " ✓ Correct Answer"
                        if idx == user_answer and not is_correct:
                            marker = " ✗ Your Answer (Incorrect)"
                        st.markdown(f"{chr(65+idx)}. {option}{marker}")
                    
                # Next button (only show if coaching is complete or skipped)
                # Show next button only when coaching_complete is True (either through coaching or skip)
                if st.session_state.coaching_complete:
                    st.divider()
                        
                    if st.session_state.current_question_index < len(st.session_state.questions) - 1:
                        if st.button("Next Question", type="primary", key="next_after_coaching"):
                            st.session_state.current_question_index += 1
                            st.session_state.show_feedback = False
                            st.session_state.coaching_active = False
                            st.session_state.coaching_messages = []
                            st.session_state.coaching_complete = False
                            st.session_state.score += points
                            st.rerun()
                    else:
                        if st.button("View Results", type="primary", key="results_after_coaching"):
                            st.session_state.quiz_completed = True
                            st.session_state.coaching_active = False
                            st.session_state.coaching_messages = []
                            st.session_state.coaching_complete = False
                            st.session_state.score += points
                            st.rerun()

if __name__ == "__main__":
    main()

