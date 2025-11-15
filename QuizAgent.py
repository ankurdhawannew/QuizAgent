import streamlit as st
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional
from datetime import datetime
from coaching_agent import get_coaching_response, start_coaching_session
from question_database import (
    initialize_database,
    get_partial_questions_and_missing_counts,
    save_questions,
    count_questions,
    mark_question_invalid,
    get_invalid_questions_report,
    count_invalid_questions
)

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
    Generate or retrieve quiz questions. First checks database for existing questions.
    Filters out questions the user has already seen, then generates new ones if needed.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        num_questions: Total number of questions
        difficulty_distribution: Dictionary with Easy, Medium, Hard percentages
        user_name: Optional user name for tracking
        previous_questions: Optional list of previous question texts the user has already seen
        
    Returns:
        List of question dictionaries
    """
    # Convert previous_questions to a set for faster lookup
    previous_questions_set = set()
    if previous_questions:
        previous_questions_set = set(q.lower().strip() for q in previous_questions)
    
    # Helper function to filter out questions user has already seen
    def filter_user_questions(questions_list: List[Dict]) -> List[Dict]:
        """Filter out questions the user has already seen."""
        if not previous_questions_set:
            return questions_list
        return [
            q for q in questions_list 
            if q.get("question", "").lower().strip() not in previous_questions_set
        ]
    
    # Get partial questions and see what's missing
    # Get more questions than needed to account for filtering out user's previous questions
    # If user has seen questions, we might need 2x to ensure we have enough after filtering
    multiplier = 2 if previous_questions_set else 1
    partial_questions, missing_counts = get_partial_questions_and_missing_counts(
        grade=grade,
        board=board,
        topic=topic,
        difficulty_distribution=difficulty_distribution,
        num_questions=num_questions * multiplier
    )
    
    # Filter out questions user has already seen from partial questions
    partial_questions = filter_user_questions(partial_questions)
    
    # Recalculate missing counts based on filtered questions
    # Count questions by difficulty after filtering
    filtered_by_difficulty = {"Easy": 0, "Medium": 0, "Hard": 0}
    for q in partial_questions:
        diff = q.get("difficulty", "Easy")
        if diff in filtered_by_difficulty:
            filtered_by_difficulty[diff] += 1
    
    # Calculate what we actually need
    easy_count = int(num_questions * difficulty_distribution["Easy"] / 100)
    medium_count = int(num_questions * difficulty_distribution["Medium"] / 100)
    hard_count = num_questions - easy_count - medium_count
    
    # Recalculate missing counts
    missing_counts = {
        "Easy": max(0, easy_count - filtered_by_difficulty["Easy"]),
        "Medium": max(0, medium_count - filtered_by_difficulty["Medium"]),
        "Hard": max(0, hard_count - filtered_by_difficulty["Hard"])
    }
    
    # Calculate total missing questions
    total_missing = sum(missing_counts.values())
    
    if total_missing == 0 and len(partial_questions) >= num_questions:
        # We have all questions from database (after filtering)
        return partial_questions[:num_questions]
    
    # Need to generate missing questions
    if not GOOGLE_API_KEY:
        st.error("GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.")
        return partial_questions if partial_questions else []
    
    # Calculate number of questions per difficulty level for generation
    # We'll generate only the missing ones
    easy_count = missing_counts["Easy"]
    medium_count = missing_counts["Medium"]
    hard_count = missing_counts["Hard"]
    total_to_generate = easy_count + medium_count + hard_count
    
    # Safety check: if somehow total_to_generate is 0, return partial questions
    if total_to_generate == 0:
        st.info(f"📚 Sufficient questions found in database. Reusing existing questions!")
        return partial_questions[:num_questions]
    
    st.info(f"📚 Sufficient question(s) not found in database. Generating additional {total_to_generate} questions to meet requirements.")
    # Create prompt for question generation
    uniqueness_note = ""
    if previous_questions and len(previous_questions) > 0:
        uniqueness_note = f"""

IMPORTANT: The user has already seen questions on this topic. You MUST generate completely NEW and DIFFERENT questions. 
Do NOT repeat or rephrase any of these previously asked questions:
{chr(10).join([f"- {q}" for q in previous_questions[:10]])}  # Show max 10 to avoid prompt bloat
{"... and more" if len(previous_questions) > 10 else ""}

Generate fresh, unique questions that the user has not seen before."""

    prompt = f"""Generate {total_to_generate} multiple-choice math questions for Grade {grade} students following the {board} curriculum.

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

Generate exactly {total_to_generate} questions with the specified difficulty distribution."""

    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        
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
        
        generated_questions = questions[:total_to_generate]
        
        # Save generated questions to database for future reuse
        if generated_questions:
            saved_count, skipped_count = save_questions(
                questions=generated_questions,
                grade=grade,
                board=board,
                topic=topic
            )
            if saved_count > 0:
                st.info(f"💾 Saved {saved_count} new question(s) to database for future reuse")
        
        # Combine existing questions with newly generated ones
        # Sort by difficulty to maintain distribution order
        all_questions = partial_questions + generated_questions
        
        # Reorder to match difficulty distribution: Easy, Medium, Hard
        difficulty_order = {"Easy": 0, "Medium": 1, "Hard": 2}
        all_questions.sort(key=lambda x: difficulty_order.get(x.get("difficulty", "Easy"), 0))
        
        return all_questions[:num_questions]
        
    except json.JSONDecodeError as e:
        st.error(f"Error parsing JSON response: {e}")
        st.text("Raw response:")
        st.text(response_text if 'response_text' in locals() else "No response")
        return []
    except Exception as e:
        st.error(f"Error generating questions: {e}")
        return []

def verify_error_report(
    question: Dict,
    error_type: str,
    grade: int,
    board: str,
    topic: str
) -> bool:
    """
    Verify if the user's error report is valid using LLM.
    
    Args:
        question: Question dictionary with question, options, correct_answer
        error_type: Type of error reported ("missing_answer", "multiple_correct", "incomplete")
        grade: Grade level
        board: Education board
        topic: Math topic
        
    Returns:
        True if error is verified, False otherwise
    """
    if not GOOGLE_API_KEY:
        return False
    
    error_descriptions = {
        "missing_answer": "The correct answer is missing from the provided options",
        "multiple_correct": "More than one option is correct",
        "incomplete": "The question is incomplete or unclear"
    }
    
    error_description = error_descriptions.get(error_type, error_type)
    
    prompt = f"""You are an expert math educator reviewing a quiz question for Grade {grade} students following the {board} curriculum.

Question: {question['question']}
Options:
A. {question['options'][0]}
B. {question['options'][1]}
C. {question['options'][2]}
D. {question['options'][3]}
Marked Correct Answer: {chr(65 + question['correct_answer'])}. {question['options'][question['correct_answer']]}

A student has reported the following error: {error_description}

Please carefully analyze the question and verify if the student's claim is correct. Consider:
1. Is the question complete and clear?
2. Are all options valid and distinct?
3. Is the marked correct answer actually correct?
4. Are there multiple correct answers?
5. Is the correct answer missing from the options?

Respond with ONLY "YES" if the error report is valid and correct, or "NO" if the error report is invalid or incorrect. Do not provide any explanation, just YES or NO."""

    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(prompt)
        response_text = response.text.strip().upper()
        #starts with checks if the response starts with YES instead of hard check response_text == "YES"
        return response_text.startswith("YES") 
    except Exception as e:
        # Don't show error here - let the caller handle it
        # This prevents duplicate error messages
        print(f"Error in verify_error_report: {e}")
        return False

def render_error_reporting_ui(question: Dict, current_q_idx: int):
    """
    Render the error reporting UI component.
    
    Args:
        question: Question dictionary
        current_q_idx: Current question index
    """
    question_reported = current_q_idx in st.session_state.reported_questions
    report_submitted = current_q_idx in st.session_state.submitted_reports
    verification_result = st.session_state.report_verification_results.get(current_q_idx)
    
    # If report has already been submitted (regardless of verification result), don't show reporting UI
    if report_submitted:
        if question_reported:
            st.error("⚠️ **Report Verified:** We apologize for the error in this question. The question has been removed from your quiz and will not count towards your score.")
        elif verification_result is False:
            st.warning("⚠️ **Report Reviewed:** After review, we found that the question is correct. Please continue with the quiz.")
        else:
            st.info("ℹ️ You have already submitted a report for this question. Please continue with the quiz.")
        return
    
    st.divider()
    st.markdown("**Report an Error**")
    
    if not st.session_state.error_report_active:
        if st.button("🚨 Report Error", key=f"report_error_btn_{current_q_idx}"):
            st.session_state.error_report_active = True
            st.rerun()
    else:
        st.info("Please select the type of error:")
        error_type = st.radio(
            "Error Type:",
            options=["missing_answer", "multiple_correct", "incomplete"],
            format_func=lambda x: {
                "missing_answer": "1. Right answer missing in the options",
                "multiple_correct": "2. More than one options are correct",
                "incomplete": "3. Question is incomplete"
            }[x],
            key=f"error_type_radio_{current_q_idx}"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Submit Report", type="primary", use_container_width=True, key=f"submit_error_{current_q_idx}"):
                # Get grade, board, topic from session state
                grade = st.session_state.get("quiz_grade")
                board = st.session_state.get("quiz_board")
                topic = st.session_state.get("quiz_topic")
                
                # Debug: Check if values are set
                if not grade or not board or not topic:
                    st.error(f"⚠️ Quiz configuration missing. Grade: {grade}, Board: {board}, Topic: {topic}. Please restart the quiz.")
                else:
                    # Mark that a report has been submitted for this question
                    st.session_state.submitted_reports.add(current_q_idx)
                    
                    # Verify the error report
                    with st.spinner("Verifying error report..."):
                        try:
                            is_valid = verify_error_report(
                                question=question,
                                error_type=error_type,
                                grade=grade,
                                board=board,
                                topic=topic
                            )
                            
                            # Store verification result in session state
                            st.session_state.report_verification_results[current_q_idx] = is_valid
                            
                            if is_valid:
                                # Error verified - apologize, remove from scoring, mark as invalid in DB
                                # Mark question as reported and verified as invalid
                                st.session_state.reported_questions.add(current_q_idx)
                                
                                # Mark question as invalid in database (instead of deleting)
                                mark_question_invalid(
                                    grade=grade,
                                    board=board,
                                    topic=topic,
                                    question_text=question['question']
                                )
                            
                            # Reset error report state after submission (regardless of verification result)
                            st.session_state.error_report_active = False
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error verifying report: {str(e)}. Please try again.")
                            # Still mark as submitted even if there was an error, to prevent multiple attempts
                            st.session_state.error_report_active = False
                            
        with col2:
            if st.button("Cancel", use_container_width=True, key=f"cancel_error_{current_q_idx}"):
                st.session_state.error_report_active = False
                st.rerun()

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
    if "reported_questions" not in st.session_state:
        st.session_state.reported_questions = set()  # Track question indices that were reported and verified as invalid
    if "submitted_reports" not in st.session_state:
        st.session_state.submitted_reports = set()  # Track question indices that have had reports submitted (regardless of verification result)
    if "report_verification_results" not in st.session_state:
        st.session_state.report_verification_results = {}  # Track verification results: {question_idx: True/False}
    if "error_report_active" not in st.session_state:
        st.session_state.error_report_active = False
    if "quiz_grade" not in st.session_state:
        st.session_state.quiz_grade = None
    if "quiz_board" not in st.session_state:
        st.session_state.quiz_board = None
    if "quiz_topic" not in st.session_state:
        st.session_state.quiz_topic = None

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
    st.session_state.reported_questions = set()
    st.session_state.submitted_reports = set()
    st.session_state.report_verification_results = {}
    st.session_state.error_report_active = False
    st.session_state.quiz_grade = None
    st.session_state.quiz_board = None
    st.session_state.quiz_topic = None
    # Note: user_name is preserved on reset

def main():
    st.set_page_config(page_title="Math Quiz Agent", page_icon="📚", layout="wide")
    
    st.title("📚 Math Quiz Agent")
    st.markdown("Generate and take personalized math quizzes based on your grade, board, and topic!")
    
    # Initialize database on startup
    initialize_database()
    
    initialize_session_state()
    
    # Sidebar for quiz configuration
    with st.sidebar:
        st.header("Quiz Configuration")
        
        # Determine if inputs should be disabled (during active quiz, but not when completed)
        inputs_disabled = st.session_state.quiz_started and not st.session_state.quiz_completed
        
        # User name input
        st.subheader("User Information")
        user_name = st.text_input(
            "Your Name", 
            value=st.session_state.user_name, 
            placeholder="Enter your name",
            disabled=inputs_disabled
        )
        if user_name and not inputs_disabled:
            # Check if name changed before updating
        #    previous_name = st.session_state.get("user_name", "")
            #if user_name != previous_name and previous_name and st.session_state.quiz_started:
                # If name changed, reset quiz
            #    reset_quiz()
            st.session_state.user_name = user_name
        elif not user_name and not inputs_disabled:
            st.warning("⚠️ Please enter your name to start the quiz")
        
        st.divider()
        
        # Use stored values when disabled, otherwise use current selection
        if inputs_disabled:
            # Show stored quiz configuration values
            grade = st.session_state.quiz_grade
            board = st.session_state.quiz_board
            topic = st.session_state.quiz_topic
            # Display as read-only
            st.info(f"**Current Quiz:**\n- Grade: {grade}\n- Board: {board}\n- Topic: {topic}")
            st.info("ℹ️ Quiz in progress. Complete the quiz to modify settings.")
        else:
            # Get stored values if they exist (for default values after quiz completion)
            stored_grade = st.session_state.get("quiz_grade")
            stored_board = st.session_state.get("quiz_board")
            stored_topic = st.session_state.get("quiz_topic")
            
            # Grade selection - use stored grade as default if available
            grade_options = list(range(6, 13))
            grade_index = 0
            if stored_grade is not None and stored_grade in grade_options:
                grade_index = grade_options.index(stored_grade)
            grade = st.selectbox("Grade", options=grade_options, index=grade_index)
            
            # Board selection - use stored board as default if available
            board_options = ["CBSE", "ICSE", "IB"]
            board_index = 0
            if stored_board is not None and stored_board in board_options:
                board_index = board_options.index(stored_board)
            board = st.selectbox("Board", options=board_options, index=board_index)
            
            # Topic input - use stored topic as default if available
            topic = st.text_input(
                "Math Topic", 
                value=stored_topic if stored_topic else "",
                placeholder="e.g., Simple Equations, Mensuration, Geometry, Trigonometry"
            )
        
        # Difficulty distribution
        if not inputs_disabled:
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
        else:
            # Set default values when disabled (won't be used anyway)
            can_start = False
            difficulty_distribution = {"Easy": 20, "Medium": 40, "Hard": 20}
            num_questions = 10
        
        # Generate quiz button
        if not inputs_disabled:
            if st.button("Generate Quiz", type="primary", disabled=not can_start or not topic or not user_name):
                if not user_name:
                    st.error("Please enter your name")
                elif not topic:
                    st.error("Please enter a math topic")
                else:
                    # Reset quiz if there's an existing quiz (to start fresh)
                    if st.session_state.quiz_started:
                        reset_quiz()
                    
                    # Get previous questions for this user to avoid showing them again
                    previous_questions = get_user_previous_questions(user_name, grade, board, topic)
                    
                    # Check database for existing questions
                    total_available = count_questions(grade, board, topic)
                    
                    if previous_questions:
                        st.info(f"📝 You've taken {len([q for q in load_user_history().get(user_name, {}).get('quizzes', []) if q.get('grade') == grade and q.get('board') == board and q.get('topic', '').lower() == topic.lower()])} quiz(zes) on this topic. Will show you new questions!")
                    
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
                            # Store quiz configuration for error reporting
                            st.session_state.quiz_grade = grade
                            st.session_state.quiz_board = board
                            st.session_state.quiz_topic = topic
                            
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
        
        # Calculate total possible score excluding reported questions
        total_possible = sum(
            SCORING.get(q.get("difficulty", "Easy"), 1) 
            for i, q in enumerate(st.session_state.questions)
            if i not in st.session_state.reported_questions
        )
        
        st.metric("Your Score", f"{st.session_state.score} / {total_possible}")
        
        if st.session_state.reported_questions:
            st.info(f"ℹ️ {len(st.session_state.reported_questions)} question(s) were reported and removed from scoring.")
        
        # Detailed breakdown
        st.subheader("Question Review")
        for i, (question, user_answer) in enumerate(zip(st.session_state.questions, st.session_state.user_answers)):
            is_reported = i in st.session_state.reported_questions
            correct_answer_idx = question["correct_answer"]
            # Handle case where user_answer is -1 (reported before answering)
            if user_answer == -1:
                is_correct = False
                user_answered = False
            else:
                is_correct = user_answer == correct_answer_idx
                user_answered = True
            difficulty = question.get("difficulty", "Easy")
            
            if is_reported:
                points = 0
                status_text = "🚨 Reported & Removed"
            else:
                points = SCORING.get(difficulty, 1) if is_correct else 0
                status_text = f"{'✓ Correct' if is_correct else '✗ Incorrect'} - {points} point(s)"
            
            with st.expander(f"Question {i+1} ({difficulty}) - {status_text}"):
                if is_reported:
                    st.warning("⚠️ This question was reported and removed from scoring.")
                st.markdown(f"**{question['question']}**")
                st.markdown("**Options:**")
                for idx, option in enumerate(question["options"]):
                    marker = ""
                    if idx == correct_answer_idx:
                        marker = " ✓ Correct Answer"
                    if user_answered and idx == user_answer and not is_correct and not is_reported:
                        marker = " ✗ Your Answer (Incorrect)"
                    st.markdown(f"{chr(65+idx)}. {option}{marker}")
                
                if not is_correct and not is_reported:
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
            
            # Show error reporting option before user answers
            current_q_idx = st.session_state.current_question_index
            question_reported = current_q_idx in st.session_state.reported_questions
            report_submitted = current_q_idx in st.session_state.submitted_reports
            
            if not st.session_state.show_feedback:
                # Show error reporting UI before answering (only if not already submitted)
                if not report_submitted:
                    render_error_reporting_ui(question, current_q_idx)
                
                # If question was reported before answering, allow skipping
                if question_reported:
                    st.warning("⚠️ This question has been reported and removed from scoring.")
                    st.divider()
                    if st.session_state.current_question_index < len(st.session_state.questions) - 1:
                        if st.button("Next Question", type="primary", key="next_reported"):
                            st.session_state.current_question_index += 1
                            st.session_state.show_feedback = False
                            st.session_state.coaching_active = False
                            st.session_state.coaching_messages = []
                            st.session_state.coaching_complete = False
                            st.session_state.error_report_active = False
                            # Add a placeholder answer (won't count towards score)
                            if len(st.session_state.user_answers) <= current_q_idx:
                                st.session_state.user_answers.append(-1)  # -1 indicates skipped/reported
                            st.rerun()
                    else:
                        if st.button("View Results", type="primary", key="results_reported"):
                            st.session_state.quiz_completed = True
                            st.session_state.coaching_active = False
                            st.session_state.coaching_messages = []
                            st.session_state.coaching_complete = False
                            st.session_state.error_report_active = False
                            # Add a placeholder answer if not already added
                            if len(st.session_state.user_answers) <= current_q_idx:
                                st.session_state.user_answers.append(-1)  # -1 indicates skipped/reported
                            st.rerun()
                elif report_submitted:
                    # Report was submitted - show verification result
                    verification_result = st.session_state.report_verification_results.get(current_q_idx)
                    if question_reported:
                        st.error("⚠️ **Report Verified:** We apologize for the error in this question. The question has been removed from your quiz and will not count towards your score.")
                    elif verification_result is False:
                        st.warning("⚠️ **Report Reviewed:** After review, we found that the question is correct. You can still answer it.")
                    else:
                        st.info("ℹ️ You have already submitted a report for this question. You can still answer it.")
                    # Continue to show options below
                
                # Display options as buttons (show for both cases: no report submitted OR report submitted but not verified)
                if not question_reported:
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
                # Make sure we have an answer for this question
                if len(st.session_state.user_answers) > current_q_idx:
                    user_answer = st.session_state.user_answers[current_q_idx]
                else:
                    # This shouldn't happen, but handle it gracefully
                    user_answer = -1
                
                correct_answer_idx = question["correct_answer"]
                # Handle case where user_answer is -1 (reported before answering)
                if user_answer == -1:
                    is_correct = False
                else:
                    is_correct = user_answer == correct_answer_idx
                
                # Check if question was already reported (current_q_idx already defined above)
                question_reported = current_q_idx in st.session_state.reported_questions
                
                # Initialize points
                points = 0
                
                if question_reported:
                    st.warning("⚠️ This question was reported and removed from scoring.")
                    st.session_state.coaching_complete = True
                elif is_correct:
                    st.success(f"✓ Correct! You selected {chr(65+user_answer)}. {question['options'][user_answer]}")
                    # Calculate points (will be added when moving to next question if not reported)
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
                    
                    # Show coaching conversation in a popup/modal using st.dialog
                    if st.session_state.coaching_active:
                        # Use variables from outer scope - they're available here
                        # Define the dialog function with closure over the question variables
                        @st.dialog("🎓 Coaching Session")
                        def coaching_dialog():
                            # Use variables from outer scope (question, user_answer, correct_answer_idx)
                            # These are captured in the closure
                            coaching_question = question['question']
                            coaching_options = question['options']
                            coaching_user_answer = user_answer
                            coaching_correct_answer = correct_answer_idx
                            
                            # Modal header
                            st.markdown("### 🎓 Coaching Session")
                            
                            st.divider()
                            
                            # Question context
                            st.markdown(f"**Question:** {coaching_question}")
                            st.caption("💬 Chat with your AI tutor to understand the concept better!")
                            st.divider()
                            
                            # Display coaching messages
                            if st.session_state.coaching_messages:
                                for msg in st.session_state.coaching_messages:
                                    if msg["role"] == "coach":
                                        with st.chat_message("assistant"):
                                            st.markdown(msg["content"])
                                    elif msg["role"] == "student":
                                        with st.chat_message("user"):
                                            st.markdown(msg["content"])
                            else:
                                st.info("Starting coaching session...")
                            
                            # If coaching is complete, show the answer
                            if st.session_state.coaching_complete:
                                st.divider()
                                st.success(f"✅ **Correct answer:** {chr(65+coaching_correct_answer)}. {coaching_options[coaching_correct_answer]}")
                                if st.button("Close Coaching", type="primary", use_container_width=True, key="close_complete"):
                                    st.session_state.coaching_active = False
                                    st.rerun()
                            else:
                                st.divider()
                                # Student response input
                                student_response = st.chat_input("Type your response or question here...", key="coaching_chat_input")
                                
                                if student_response:
                                    # Add student message
                                    st.session_state.coaching_messages.append({
                                        "role": "student",
                                        "content": student_response
                                    })
                                    
                                    # Get coaching response
                                    with st.spinner("Coach is thinking..."):
                                        coaching_response = get_coaching_response(
                                            question=coaching_question,
                                            options=coaching_options,
                                            user_answer=coaching_user_answer,
                                            correct_answer=coaching_correct_answer,
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
                                
                                # Options at the bottom
                                col1, col2 = st.columns([1, 1])
                                with col1:
                                    if st.button("Show Answer", key="show_answer", use_container_width=True):
                                        st.session_state.coaching_complete = True
                                        st.rerun()
                                with col2:
                                    if st.button("Close Coaching", key="close_coaching", use_container_width=True):
                                        st.session_state.coaching_active = False
                                        st.rerun()
                        
                        # Call the dialog function
                        coaching_dialog()
                    
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
                    
                # Error reporting section (also available after feedback, but only if not already submitted)
                report_submitted_after = current_q_idx in st.session_state.submitted_reports
                if st.session_state.coaching_complete and not report_submitted_after:
                    render_error_reporting_ui(question, current_q_idx)
                
                # If report was submitted, show verification result
                if st.session_state.coaching_complete and report_submitted_after:
                    verification_result_after = st.session_state.report_verification_results.get(current_q_idx)
                    if question_reported:
                        st.error("⚠️ **Report Verified:** We apologize for the error in this question. The question has been removed from your quiz and will not count towards your score.")
                    elif verification_result_after is False:
                        st.warning("⚠️ **Report Reviewed:** After review, we found that the question is correct. Please continue with the quiz.")
                    else:
                        st.info("ℹ️ You have already submitted a report for this question. Please continue with the quiz.")
                
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
                            st.session_state.error_report_active = False
                            # Only add points if question was not reported
                            if current_q_idx not in st.session_state.reported_questions:
                                st.session_state.score += points
                            st.rerun()
                    else:
                        if st.button("View Results", type="primary", key="results_after_coaching"):
                            st.session_state.quiz_completed = True
                            st.session_state.coaching_active = False
                            st.session_state.coaching_messages = []
                            st.session_state.coaching_complete = False
                            st.session_state.error_report_active = False
                            # Only add points if question was not reported
                            if current_q_idx not in st.session_state.reported_questions:
                                st.session_state.score += points
                            st.rerun()

if __name__ == "__main__":
    main()

