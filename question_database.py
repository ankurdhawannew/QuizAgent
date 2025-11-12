"""
Database module for storing and retrieving quiz questions.
Questions are stored by Grade, Topic, Board, and Difficulty level.
"""
import sqlite3
import json
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Database file path
DB_FILE = "quiz_questions.db"

def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def initialize_database():
    """Initialize the database and create tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade INTEGER NOT NULL,
            board TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL CHECK(difficulty IN ('Easy', 'Medium', 'Hard')),
            question TEXT NOT NULL,
            options TEXT NOT NULL,  -- JSON array of options
            correct_answer INTEGER NOT NULL CHECK(correct_answer >= 0 AND correct_answer <= 3),
            is_valid INTEGER DEFAULT 1 CHECK(is_valid IN (0, 1)),  -- 1 = valid, 0 = invalid (reported)
            reported_at TIMESTAMP NULL,  -- Timestamp when question was reported as invalid
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(grade, board, topic, question)  -- Prevent duplicate questions
        )
    """)
    
    # Add is_valid and reported_at columns to existing tables if they don't exist
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN is_valid INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE questions ADD COLUMN reported_at TIMESTAMP NULL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Update existing rows to have is_valid = 1 if NULL
    cursor.execute("UPDATE questions SET is_valid = 1 WHERE is_valid IS NULL")
    
    # Create index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_grade_board_topic_difficulty 
        ON questions(grade, board, topic, difficulty)
    """)
    
    # Create index for filtering valid questions
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_is_valid 
        ON questions(is_valid)
    """)
    
    conn.commit()
    conn.close()

def save_questions(questions: List[Dict], grade: int, board: str, topic: str):
    """
    Save questions to the database.
    
    Args:
        questions: List of question dictionaries with keys:
                   - question: str
                   - options: List[str]
                   - correct_answer: int
                   - difficulty: str
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    saved_count = 0
    skipped_count = 0
    
    for q in questions:
        try:
            # Convert options list to JSON string
            options_json = json.dumps(q.get("options", []))
            
            cursor.execute("""
                INSERT OR IGNORE INTO questions 
                (grade, board, topic, difficulty, question, options, correct_answer)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                grade,
                board,
                topic,
                q.get("difficulty", "Easy"),
                q.get("question", ""),
                options_json,
                int(q.get("correct_answer", 0))
            ))
            
            if cursor.rowcount > 0:
                saved_count += 1
            else:
                skipped_count += 1  # Question already exists
                
        except Exception as e:
            print(f"Error saving question: {e}")
            skipped_count += 1
    
    conn.commit()
    conn.close()
    
    return saved_count, skipped_count

def get_questions(
    grade: int,
    board: str,
    topic: str,
    difficulty: str,
    limit: Optional[int] = None,
    random: bool = False
) -> List[Dict]:
    """
    Retrieve questions from the database.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        difficulty: Difficulty level (Easy, Medium, Hard)
        limit: Maximum number of questions to return
        random: If True, return questions in random order
        
    Returns:
        List of question dictionaries
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    order_clause = "ORDER BY RANDOM()" if random else "ORDER BY id"
    limit_clause = f"LIMIT {limit}" if limit else ""
    
    cursor.execute(f"""
        SELECT question, options, correct_answer, difficulty
        FROM questions
        WHERE grade = ? AND board = ? AND topic = ? AND difficulty = ? AND is_valid = 1
        {order_clause}
        {limit_clause}
    """, (grade, board, topic, difficulty))
    
    rows = cursor.fetchall()
    conn.close()
    
    questions = []
    for row in rows:
        questions.append({
            "question": row["question"],
            "options": json.loads(row["options"]),
            "correct_answer": int(row["correct_answer"]),
            "difficulty": row["difficulty"]
        })
    
    return questions

def count_questions(
    grade: int,
    board: str,
    topic: str,
    difficulty: Optional[str] = None
) -> int:
    """
    Count questions in the database matching the criteria.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        difficulty: Optional difficulty level filter
        
    Returns:
        Number of matching questions
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if difficulty:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM questions
            WHERE grade = ? AND board = ? AND topic = ? AND difficulty = ? AND is_valid = 1
        """, (grade, board, topic, difficulty))
    else:
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM questions
            WHERE grade = ? AND board = ? AND topic = ? AND is_valid = 1
        """, (grade, board, topic))
    
    result = cursor.fetchone()
    conn.close()
    
    return result["count"] if result else 0

def get_questions_by_difficulty_distribution(
    grade: int,
    board: str,
    topic: str,
    difficulty_distribution: Dict[str, int],
    num_questions: int
) -> List[Dict]:
    """
    Get questions matching the difficulty distribution requirements.
    Returns existing questions if sufficient, otherwise returns empty list.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        difficulty_distribution: Dictionary with Easy, Medium, Hard percentages
        num_questions: Total number of questions needed
        
    Returns:
        List of question dictionaries, or empty list if insufficient questions exist
    """
    # Calculate number of questions per difficulty level
    easy_count = int(num_questions * difficulty_distribution["Easy"] / 100)
    medium_count = int(num_questions * difficulty_distribution["Medium"] / 100)
    hard_count = num_questions - easy_count - medium_count
    
    all_questions = []
    
    # Get questions for each difficulty level
    for difficulty, count in [("Easy", easy_count), ("Medium", medium_count), ("Hard", hard_count)]:
        if count > 0:
            available = count_questions(grade, board, topic, difficulty)
            
            if available < count:
                # Not enough questions available
                return []
            
            # Get questions randomly if we have more than needed
            questions = get_questions(
                grade=grade,
                board=board,
                topic=topic,
                difficulty=difficulty,
                limit=count,
                random=True
            )
            
            all_questions.extend(questions)
    
    return all_questions

def get_partial_questions_and_missing_counts(
    grade: int,
    board: str,
    topic: str,
    difficulty_distribution: Dict[str, int],
    num_questions: int
) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Get available questions from database and calculate what's missing.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        difficulty_distribution: Dictionary with Easy, Medium, Hard percentages
        num_questions: Total number of questions needed
        
    Returns:
        Tuple of (available_questions_list, missing_counts_dict)
        missing_counts_dict has keys: "Easy", "Medium", "Hard" with counts needed
    """
    # Calculate number of questions per difficulty level
    easy_count = int(num_questions * difficulty_distribution["Easy"] / 100)
    medium_count = int(num_questions * difficulty_distribution["Medium"] / 100)
    hard_count = num_questions - easy_count - medium_count
    
    all_questions = []
    missing_counts = {"Easy": 0, "Medium": 0, "Hard": 0}
    
    # Get questions for each difficulty level
    for difficulty, count in [("Easy", easy_count), ("Medium", medium_count), ("Hard", hard_count)]:
        if count > 0:
            available = count_questions(grade, board, topic, difficulty)
            
            if available >= count:
                # We have enough, get exactly what we need
                questions = get_questions(
                    grade=grade,
                    board=board,
                    topic=topic,
                    difficulty=difficulty,
                    limit=count,
                    random=True
                )
                all_questions.extend(questions)
            else:
                # Not enough, get what we have and note what's missing
                questions = get_questions(
                    grade=grade,
                    board=board,
                    topic=topic,
                    difficulty=difficulty,
                    limit=available,
                    random=True
                )
                all_questions.extend(questions)
                missing_counts[difficulty] = count - available
    
    return all_questions, missing_counts

def mark_question_invalid(
    grade: int,
    board: str,
    topic: str,
    question_text: str
) -> bool:
    """
    Mark a question as invalid (reported) in the database instead of deleting it.
    This allows tracking of reported questions for quality reports.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Math topic
        question_text: The exact question text to mark as invalid
        
    Returns:
        True if question was marked as invalid, False if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE questions
        SET is_valid = 0, reported_at = CURRENT_TIMESTAMP
        WHERE grade = ? AND board = ? AND topic = ? AND question = ? AND is_valid = 1
    """, (grade, board, topic, question_text))
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated

def get_invalid_questions_report(
    grade: Optional[int] = None,
    board: Optional[str] = None,
    topic: Optional[str] = None
) -> List[Dict]:
    """
    Get a report of all invalid (reported) questions for analysis.
    
    Args:
        grade: Optional grade level filter
        board: Optional board filter
        topic: Optional topic filter
        
    Returns:
        List of dictionaries with question details and when they were reported
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    conditions = ["is_valid = 0"]
    params = []
    
    if grade:
        conditions.append("grade = ?")
        params.append(grade)
    if board:
        conditions.append("board = ?")
        params.append(board)
    if topic:
        conditions.append("topic = ?")
        params.append(topic)
    
    where_clause = " AND ".join(conditions)
    
    cursor.execute(f"""
        SELECT id, grade, board, topic, difficulty, question, options, correct_answer, reported_at, created_at
        FROM questions
        WHERE {where_clause}
        ORDER BY reported_at DESC
    """, params)
    
    rows = cursor.fetchall()
    conn.close()
    
    report = []
    for row in rows:
        report.append({
            "id": row["id"],
            "grade": row["grade"],
            "board": row["board"],
            "topic": row["topic"],
            "difficulty": row["difficulty"],
            "question": row["question"],
            "options": json.loads(row["options"]),
            "correct_answer": int(row["correct_answer"]),
            "reported_at": row["reported_at"],
            "created_at": row["created_at"]
        })
    
    return report

def count_invalid_questions(
    grade: Optional[int] = None,
    board: Optional[str] = None,
    topic: Optional[str] = None
) -> int:
    """
    Count invalid (reported) questions.
    
    Args:
        grade: Optional grade level filter
        board: Optional board filter
        topic: Optional topic filter
        
    Returns:
        Number of invalid questions
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    conditions = ["is_valid = 0"]
    params = []
    
    if grade:
        conditions.append("grade = ?")
        params.append(grade)
    if board:
        conditions.append("board = ?")
        params.append(board)
    if topic:
        conditions.append("topic = ?")
        params.append(topic)
    
    where_clause = " AND ".join(conditions)
    
    cursor.execute(f"""
        SELECT COUNT(*) as count
        FROM questions
        WHERE {where_clause}
    """, params)
    
    result = cursor.fetchone()
    conn.close()
    
    return result["count"] if result else 0

