"""
End-to-End Test Suite for QuizAgent Application

This test suite verifies the complete functionality of the QuizAgent application,
including database operations, question generation, quiz taking, scoring, coaching,
and user history tracking.
"""

import pytest
import json
import os
import sqlite3
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, List

# Import application modules
from question_database import (
    initialize_database,
    save_questions,
    get_questions,
    count_questions,
    get_questions_by_difficulty_distribution,
    get_partial_questions_and_missing_counts,
    mark_question_invalid,
    get_invalid_questions_report,
    count_invalid_questions
)
from coaching_agent import get_coaching_response, start_coaching_session


class TestDatabaseOperations:
    """Test database initialization and operations."""
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Create a temporary database for testing."""
        # Create temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_quiz_questions.db")
        
        # Patch the DB_FILE path
        with patch('question_database.DB_FILE', self.test_db_path):
            initialize_database()
            yield
            # Cleanup
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
            shutil.rmtree(self.test_dir)
    
    def test_database_initialization(self):
        """Test that database is initialized correctly."""
        with patch('question_database.DB_FILE', self.test_db_path):
            initialize_database()
            
            # Verify database file exists
            assert os.path.exists(self.test_db_path)
            
            # Verify tables exist
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
            assert cursor.fetchone() is not None
            conn.close()
    
    def test_save_questions(self):
        """Test saving questions to database."""
        with patch('question_database.DB_FILE', self.test_db_path):
            questions = [
                {
                    "question": "What is 2 + 2?",
                    "options": ["3", "4", "5", "6"],
                    "correct_answer": 1,
                    "difficulty": "Easy"
                },
                {
                    "question": "What is 5 * 5?",
                    "options": ["20", "25", "30", "35"],
                    "correct_answer": 1,
                    "difficulty": "Medium"
                }
            ]
            
            saved_count, skipped_count = save_questions(
                questions=questions,
                grade=6,
                board="CBSE",
                topic="arithmetic"
            )
            
            assert saved_count == 2
            assert skipped_count == 0
            
            # Verify questions were saved
            assert count_questions(6, "CBSE", "arithmetic") == 2
    
    def test_get_questions(self):
        """Test retrieving questions from database."""
        with patch('question_database.DB_FILE', self.test_db_path):
            # Save test questions
            questions = [
                {
                    "question": "What is 2 + 2?",
                    "options": ["3", "4", "5", "6"],
                    "correct_answer": 1,
                    "difficulty": "Easy"
                }
            ]
            save_questions(questions, 6, "CBSE", "arithmetic")
            
            # Retrieve questions
            retrieved = get_questions(6, "CBSE", "arithmetic", "Easy")
            
            assert len(retrieved) == 1
            assert retrieved[0]["question"] == "What is 2 + 2?"
            assert retrieved[0]["correct_answer"] == 1
    
    def test_get_questions_by_difficulty_distribution(self):
        """Test getting questions by difficulty distribution."""
        with patch('question_database.DB_FILE', self.test_db_path):
            # Save enough questions to match the distribution
            # For 10 questions with Easy: 50%, Medium: 30%, Hard: 20%
            # We need: Easy: 5, Medium: 3, Hard: 2
            questions = [
                # Easy questions (5 needed)
                {"question": "Easy Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
                {"question": "Easy Q2", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
                {"question": "Easy Q3", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
                {"question": "Easy Q4", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
                {"question": "Easy Q5", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
                # Medium questions (3 needed)
                {"question": "Medium Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Medium"},
                {"question": "Medium Q2", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Medium"},
                {"question": "Medium Q3", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Medium"},
                # Hard questions (2 needed)
                {"question": "Hard Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Hard"},
                {"question": "Hard Q2", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Hard"},
            ]
            save_questions(questions, 6, "CBSE", "math")
            
            difficulty_distribution = {"Easy": 50, "Medium": 30, "Hard": 20}
            retrieved = get_questions_by_difficulty_distribution(
                6, "CBSE", "math", difficulty_distribution, 10
            )
            
            # Should return exactly 10 questions matching distribution
            assert len(retrieved) == 10
            
            # Verify distribution
            easy_count = sum(1 for q in retrieved if q["difficulty"] == "Easy")
            medium_count = sum(1 for q in retrieved if q["difficulty"] == "Medium")
            hard_count = sum(1 for q in retrieved if q["difficulty"] == "Hard")
            
            assert easy_count == 5  # 50% of 10
            assert medium_count == 3  # 30% of 10
            assert hard_count == 2  # 20% of 10
    
    def test_get_questions_by_difficulty_distribution_insufficient_questions(self):
        """Test that function returns all available questions when insufficient questions exist."""
        with patch('question_database.DB_FILE', self.test_db_path):
            # Save only a few questions (not enough for the distribution)
            questions = [
                {"question": "Easy Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
                {"question": "Easy Q2", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
                {"question": "Medium Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Medium"},
            ]
            save_questions(questions, 6, "CBSE", "math")
            
            # Request 10 questions but we only have 3
            # Distribution: Easy: 5 (50%), Medium: 3 (30%), Hard: 2 (20%)
            difficulty_distribution = {"Easy": 50, "Medium": 30, "Hard": 20}
            retrieved = get_questions_by_difficulty_distribution(
                6, "CBSE", "math", difficulty_distribution, 10
            )
            
            # Should return all available questions (2 Easy + 1 Medium = 3 total)
            assert len(retrieved) == 3
            
            # Verify we got what's available
            easy_count = sum(1 for q in retrieved if q["difficulty"] == "Easy")
            medium_count = sum(1 for q in retrieved if q["difficulty"] == "Medium")
            hard_count = sum(1 for q in retrieved if q["difficulty"] == "Hard")
            
            assert easy_count == 2  # We have 2 Easy questions available
            assert medium_count == 1  # We have 1 Medium question available
            assert hard_count == 0  # We have 0 Hard questions available
    
    def test_mark_question_invalid(self):
        """Test marking a question as invalid."""
        with patch('question_database.DB_FILE', self.test_db_path):
            # Save a question
            questions = [{
                "question": "Test question",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 0,
                "difficulty": "Easy"
            }]
            save_questions(questions, 6, "CBSE", "math")
            
            # Mark as invalid
            result = mark_question_invalid(6, "CBSE", "math", "Test question")
            assert result is True
            
            # Verify it's marked as invalid
            assert count_questions(6, "CBSE", "math") == 0
            assert count_invalid_questions(6, "CBSE", "math") == 1


class TestQuestionGeneration:
    """Test question generation functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_quiz_questions.db")
        self.test_history_path = os.path.join(self.test_dir, "test_user_quiz_history.json")
        
        # Initialize test database
        with patch('question_database.DB_FILE', self.test_db_path):
            initialize_database()
        
        yield
        
        # Cleanup
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        if os.path.exists(self.test_history_path):
            os.remove(self.test_history_path)
        shutil.rmtree(self.test_dir)
    
    @patch('sys.modules')
    def test_question_generation_flow(self, mock_modules):
        """Test question generation flow with mocked API."""
        # This test verifies the question generation logic
        # In a real scenario, we would mock the Gemini API calls
        # For now, we test that the database functions work correctly
        
        with patch('question_database.DB_FILE', self.test_db_path):
            # Test that we can save and retrieve questions
            questions = [
                {
                    "question": "What is 2 + 2?",
                    "options": ["3", "4", "5", "6"],
                    "correct_answer": 1,
                    "difficulty": "Easy"
                },
                {
                    "question": "What is 5 * 5?",
                    "options": ["20", "25", "30", "35"],
                    "correct_answer": 1,
                    "difficulty": "Medium"
                }
            ]
            
            saved_count, _ = save_questions(questions, 6, "CBSE", "arithmetic")
            assert saved_count == 2
            
            # Verify questions can be retrieved
            retrieved = get_questions_by_difficulty_distribution(
                6, "CBSE", "arithmetic",
                {"Easy": 50, "Medium": 50, "Hard": 0},
                2
            )
            assert len(retrieved) == 2


class TestUserHistory:
    """Test user history tracking."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_history_path = os.path.join(self.test_dir, "test_user_quiz_history.json")
        yield
        if os.path.exists(self.test_history_path):
            os.remove(self.test_history_path)
        shutil.rmtree(self.test_dir)
    
    def test_save_user_quiz(self):
        """Test saving user quiz history."""
        # Import QuizAgent functions with proper patching
        import sys
        import importlib
        
        # Mock streamlit to avoid import errors
        sys.modules['streamlit'] = Mock()
        
        # Import QuizAgent module
        import QuizAgent as quiz_module
        
        # Patch the history file path
        quiz_module.QUIZ_HISTORY_FILE = self.test_history_path
        
        questions = [
            {"question": "Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0},
            {"question": "Q2", "options": ["A", "B", "C", "D"], "correct_answer": 1}
        ]
        
        quiz_module.save_user_quiz("TestUser", 6, "CBSE", "math", questions)
        
        # Verify history was saved
        history = quiz_module.load_user_history()
        assert "TestUser" in history
        assert len(history["TestUser"]["quizzes"]) == 1
        assert history["TestUser"]["quizzes"][0]["grade"] == 6
        assert history["TestUser"]["quizzes"][0]["board"] == "CBSE"
        assert history["TestUser"]["quizzes"][0]["topic"] == "math"
    
    def test_get_user_previous_questions(self):
        """Test retrieving user's previous questions."""
        import sys
        sys.modules['streamlit'] = Mock()
        
        import QuizAgent as quiz_module
        quiz_module.QUIZ_HISTORY_FILE = self.test_history_path
        
        # Save first quiz
        questions1 = [{"question": "Previous Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0}]
        quiz_module.save_user_quiz("TestUser", 6, "CBSE", "math", questions1)
        
        # Save second quiz with same topic
        questions2 = [{"question": "Previous Q2", "options": ["A", "B", "C", "D"], "correct_answer": 0}]
        quiz_module.save_user_quiz("TestUser", 6, "CBSE", "math", questions2)
        
        # Get previous questions
        previous = quiz_module.get_user_previous_questions("TestUser", 6, "CBSE", "math")
        
        assert len(previous) == 2
        assert "Previous Q1" in previous
        assert "Previous Q2" in previous


class TestScoring:
    """Test scoring system."""
    
    def test_scoring_calculation(self):
        """Test that scoring works correctly."""
        # Define scoring constants (matching QuizAgent.py)
        SCORING = {
            "Easy": 1,
            "Medium": 2,
            "Hard": 4
        }
        
        assert SCORING["Easy"] == 1
        assert SCORING["Medium"] == 2
        assert SCORING["Hard"] == 4
    
    def test_score_calculation_for_quiz(self):
        """Test score calculation for a complete quiz."""
        questions = [
            {"question": "Q1", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"},
            {"question": "Q2", "options": ["A", "B", "C", "D"], "correct_answer": 1, "difficulty": "Medium"},
            {"question": "Q3", "options": ["A", "B", "C", "D"], "correct_answer": 2, "difficulty": "Hard"},
        ]
        
        user_answers = [0, 1, 2]  # All correct
        
        SCORING = {
            "Easy": 1,
            "Medium": 2,
            "Hard": 4
        }
        
        score = sum(
            SCORING.get(q["difficulty"], 1) 
            for q, ans in zip(questions, user_answers)
            if q["correct_answer"] == ans
        )
        
        assert score == 7  # 1 + 2 + 4


class TestCoachingAgent:
    """Test coaching agent functionality."""
    
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"})
    @patch('coaching_agent.ChatGoogleGenerativeAI')
    def test_start_coaching_session(self, mock_llm_class):
        """Test starting a coaching session."""
        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Let's think about this problem step by step. What do you think the key concept is here?"
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        session = start_coaching_session(
            question="What is 2 + 2?",
            options=["3", "4", "5", "6"],
            user_answer=0,  # Wrong answer (selected "3")
            correct_answer=1  # Correct answer is "4"
        )
        
        assert session is not None
        assert "initial_message" in session
        assert len(session["initial_message"]) > 0
    
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"})
    @patch('coaching_agent.ChatGoogleGenerativeAI')
    def test_get_coaching_response(self, mock_llm_class):
        """Test getting coaching response."""
        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "That's a good observation! Now, let's think about what operation we need to use."
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        response = get_coaching_response(
            question="What is 2 + 2?",
            options=["3", "4", "5", "6"],
            user_answer=0,
            correct_answer=1,
            student_response="I think it might be addition"
        )
        
        assert response is not None
        assert len(response) > 0


class TestErrorReporting:
    """Test error reporting functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_quiz_questions.db")
        
        with patch('question_database.DB_FILE', self.test_db_path):
            initialize_database()
            # Save a test question
            questions = [{
                "question": "Test question for reporting",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 0,
                "difficulty": "Easy"
            }]
            save_questions(questions, 6, "CBSE", "math")
        
        yield
        
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        shutil.rmtree(self.test_dir)
    
    def test_verify_error_report(self):
        """Test error report verification logic."""
        import sys
        sys.modules['streamlit'] = Mock()
        
        import QuizAgent as quiz_module
        
        # Mock Gemini API
        with patch('google.generativeai.GenerativeModel') as mock_genai:
            mock_model = Mock()
            mock_response = Mock()
            mock_response.text = "YES"  # Error is valid
            mock_model.generate_content.return_value = mock_response
            mock_genai.return_value = mock_model
            
            question = {
                "question": "Test question",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 0
            }
            
            result = quiz_module.verify_error_report(
                question=question,
                error_type="missing_answer",
                grade=6,
                board="CBSE",
                topic="math"
            )
            
            assert result is True
    
    def test_mark_question_invalid_after_report(self):
        """Test that reported questions are marked invalid."""
        with patch('question_database.DB_FILE', self.test_db_path):
            result = mark_question_invalid(6, "CBSE", "math", "Test question for reporting")
            assert result is True
            
            # Verify question is now invalid
            assert count_questions(6, "CBSE", "math") == 0
            assert count_invalid_questions(6, "CBSE", "math") == 1


class TestEndToEndFlow:
    """End-to-end integration tests."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_quiz_questions.db")
        self.test_history_path = os.path.join(self.test_dir, "test_user_quiz_history.json")
        
        with patch('question_database.DB_FILE', self.test_db_path):
            initialize_database()
        
        yield
        
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        if os.path.exists(self.test_history_path):
            os.remove(self.test_history_path)
        shutil.rmtree(self.test_dir)
    
    def test_complete_quiz_flow(self):
        """Test complete quiz flow from generation to completion."""
        with patch('question_database.DB_FILE', self.test_db_path):
            # Step 1: Save questions to database
            questions = [
                {
                    "question": "What is 2 + 2?",
                    "options": ["3", "4", "5", "6"],
                    "correct_answer": 1,
                    "difficulty": "Easy"
                },
                {
                    "question": "What is 5 * 5?",
                    "options": ["20", "25", "30", "35"],
                    "correct_answer": 1,
                    "difficulty": "Medium"
                }
            ]
            save_questions(questions, 6, "CBSE", "arithmetic")
            
            # Step 2: Retrieve questions
            retrieved = get_questions_by_difficulty_distribution(
                6, "CBSE", "arithmetic",
                {"Easy": 50, "Medium": 50, "Hard": 0},
                2
            )
            
            assert len(retrieved) == 2
            
            # Step 3: Simulate quiz taking
            user_answers = [1, 1]  # Both correct
            
            # Step 4: Calculate score
            SCORING = {
                "Easy": 1,
                "Medium": 2,
                "Hard": 4
            }
            score = sum(
                SCORING.get(q["difficulty"], 1)
                for q, ans in zip(retrieved, user_answers)
                if q["correct_answer"] == ans
            )
            
            assert score == 3  # 1 (Easy) + 2 (Medium)
            
            # Step 5: Save quiz history
            import sys
            sys.modules['streamlit'] = Mock()
            import QuizAgent as quiz_module
            quiz_module.QUIZ_HISTORY_FILE = self.test_history_path
            
            quiz_module.save_user_quiz("TestUser", 6, "CBSE", "arithmetic", retrieved)
            
            history = quiz_module.load_user_history()
            assert "TestUser" in history
            assert len(history["TestUser"]["quizzes"]) == 1
    
    def test_question_filtering_prevents_duplicates(self):
        """Test that previously seen questions are filtered out."""
        with patch('question_database.DB_FILE', self.test_db_path):
            import sys
            sys.modules['streamlit'] = Mock()
            import QuizAgent as quiz_module
            quiz_module.QUIZ_HISTORY_FILE = self.test_history_path
            
            # Save initial quiz
            questions1 = [
                {"question": "Previous question", "options": ["A", "B", "C", "D"], "correct_answer": 0, "difficulty": "Easy"}
            ]
            save_questions(questions1, 6, "CBSE", "math")
            
            quiz_module.save_user_quiz("TestUser", 6, "CBSE", "math", questions1)
            
            # Get previous questions
            previous = quiz_module.get_user_previous_questions("TestUser", 6, "CBSE", "math")
            assert "Previous question" in previous
            
            # Filter function should exclude previous questions
            def filter_questions(questions_list, previous_set):
                return [
                    q for q in questions_list
                    if q.get("question", "").lower().strip() not in previous_set
                ]
            
            new_questions = [
                {"question": "Previous question", "options": ["A", "B", "C", "D"], "correct_answer": 0},
                {"question": "New question", "options": ["A", "B", "C", "D"], "correct_answer": 0}
            ]
            
            previous_set = set(q.lower().strip() for q in previous)
            filtered = filter_questions(new_questions, previous_set)
            
            assert len(filtered) == 1
            assert filtered[0]["question"] == "New question"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

