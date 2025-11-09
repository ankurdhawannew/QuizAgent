import streamlit as st
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional

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

def generate_questions(
    grade: int,
    board: str,
    topic: str,
    num_questions: int,
    difficulty_distribution: Dict[str, int]
) -> List[Dict]:
    """
    Generate quiz questions using a LLM.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        num_questions: Total number of questions
        difficulty_distribution: Dictionary with Easy, Medium, Hard percentages
        
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
    prompt = f"""Generate {num_questions} multiple-choice math questions for Grade {grade} students following the {board} curriculum.

Topic: {topic}
Difficulty Distribution:
- Easy: {easy_count} questions
- Medium: {medium_count} questions  
- Hard: {hard_count} questions

Requirements:
1. Each question must have exactly 4 options (A, B, C, D)
2. Only one option should be correct
3. Questions should be appropriate for Grade {grade} level and {board} curriculum
4. Questions should cover the topic: {topic}
5. Difficulty levels should match the distribution above

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

def reset_quiz():
    """Reset quiz state."""
    st.session_state.questions = []
    st.session_state.current_question_index = 0
    st.session_state.user_answers = []
    st.session_state.score = 0
    st.session_state.quiz_started = False
    st.session_state.show_feedback = False
    st.session_state.quiz_completed = False

def main():
    st.set_page_config(page_title="Math Quiz Agent", page_icon="📚", layout="wide")
    
    st.title("📚 Math Quiz Agent")
    st.markdown("Generate and take personalized math quizzes based on your grade, board, and topic!")
    
    initialize_session_state()
    
    # Sidebar for quiz configuration
    with st.sidebar:
        st.header("Quiz Configuration")
        
        # Grade selection
        grade = st.selectbox("Grade", options=list(range(6, 13)), index=0)
        
        # Board selection
        board = st.selectbox("Board", options=["CBSE", "ICSE", "IB"])
        
        # Topic input
        topic = st.text_input("Math Topic", placeholder="e.g., Algebra, Geometry, Trigonometry")
        
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
        num_questions = st.number_input("Number of Questions", min_value=1, max_value=50, value=10, step=1)
        
        # Generate quiz button
        if st.button("Generate Quiz", type="primary", disabled=not can_start or not topic):
            if not topic:
                st.error("Please enter a math topic")
            else:
                with st.spinner("Generating questions..."):
                    questions = generate_questions(
                        grade=grade,
                        board=board,
                        topic=topic,
                        num_questions=num_questions,
                        difficulty_distribution=difficulty_distribution
                    )
                    
                    if questions:
                        st.session_state.questions = questions
                        st.session_state.quiz_started = True
                        st.session_state.current_question_index = 0
                        st.session_state.user_answers = []
                        st.session_state.score = 0
                        st.session_state.show_feedback = False
                        st.session_state.quiz_completed = False
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
                    st.rerun()
            else:
                # Show feedback
                user_answer = st.session_state.user_answers[-1]
                correct_answer_idx = question["correct_answer"]
                is_correct = user_answer == correct_answer_idx
                
                if is_correct:
                    st.success(f"✓ Correct! You selected {chr(65+user_answer)}. {question['options'][user_answer]}")
                    # Add points
                    #points = SCORING.get(difficulty, 1)
                    #st.session_state.score += points
                    st.balloons()
                else:
                    st.error(f"✗ Incorrect. You selected {chr(65+user_answer)}. {question['options'][user_answer]}")
                    st.info(f"Correct answer: {chr(65+correct_answer_idx)}. {question['options'][correct_answer_idx]}")
                
                # Show all options with markers
                st.markdown("**All Options:**")
                for idx, option in enumerate(question["options"]):
                    marker = ""
                    if idx == correct_answer_idx:
                        marker = " ✓ Correct"
                    if idx == user_answer and not is_correct:
                        marker = " ✗ Your Answer"
                    st.markdown(f"{chr(65+idx)}. {option}{marker}")
                
                # Next button
                if st.session_state.current_question_index < len(st.session_state.questions) - 1:
                    if st.button("Next Question", type="primary"):
                        st.session_state.current_question_index += 1
                        st.session_state.show_feedback = False
                        points = SCORING.get(difficulty, 1)
                        st.session_state.score += points
                        st.rerun()
                else:
                    if st.button("View Results", type="primary"):
                        st.session_state.quiz_completed = True
                        points = SCORING.get(difficulty, 1)
                        st.session_state.score += points
                        st.rerun()

if __name__ == "__main__":
    main()

