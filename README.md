# 📚 Math Quiz Agent

An intelligent, AI-powered math quiz application built with Streamlit that generates personalized quizzes and provides Socratic method-based coaching to help students learn from their mistakes.

## ✨ Features

### 🎯 Quiz Generation
- **Personalized Quizzes**: Generate math quizzes tailored to grade level (6-12), education board (CBSE, ICSE, IB), and specific topics
- **Difficulty Distribution**: Customize the mix of Easy, Medium, and Hard questions
- **Question Database**: SQLite database stores questions for reuse, reducing API calls and improving performance
- **Question Tracking**: Automatically tracks previously asked questions to ensure variety
- **Adaptive Scoring**: Points system based on difficulty (Easy: 1pt, Medium: 2pts, Hard: 4pts)
- **Error Reporting**: Users can report invalid questions, which are verified and marked as invalid

### 🎓 Intelligent Coaching
- **Socratic Method**: When students answer incorrectly, they can opt for personalized coaching
- **Interactive Learning**: Chat-based coaching session that guides students to discover the correct answer
- **Patient Guidance**: AI tutor asks thoughtful questions and provides hints without directly revealing answers
- **Concept Understanding**: Helps students understand underlying concepts, not just memorize answers

### 📊 Progress Tracking
- **User History**: Tracks quiz history per user, grade, board, and topic
- **Detailed Results**: Comprehensive review of all questions with correct/incorrect answers
- **Score Breakdown**: See points earned per question based on difficulty level

### 🗄️ Database Features
- **Question Storage**: Questions are stored in SQLite database for efficient retrieval
- **Smart Caching**: Reuses existing questions from database before generating new ones
- **Partial Question Handling**: Returns available questions even if full distribution isn't met, then generates only missing questions
- **Question Validation**: Invalid questions are marked (not deleted) for quality tracking

## 🚀 Getting Started

### Prerequisites

- Python 3.11.0 or higher
- Google API Key for Gemini (get one from [Google AI Studio](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   cd QuizAgent
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```bash
   touch .env
   ```
   
   Add your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

### Running the Application

Start the Streamlit app:
```bash
streamlit run QuizAgent.py
```

The application will open in your default web browser at `http://localhost:8501`.

## 📖 Usage Guide

### Creating a Quiz

1. **Enter Your Name**: Provide your name in the sidebar to track your quiz history
2. **Select Grade**: Choose your grade level (6-12)
3. **Choose Board**: Select your education board (CBSE, ICSE, or IB)
4. **Enter Topic**: Type the math topic you want to practice (e.g., "Simple Equations", "Mensuration", "Geometry", "Trigonometry")
5. **Set Difficulty**: Adjust the percentage sliders for Easy, Medium, and Hard questions (must total 100%)
6. **Choose Question Count**: Select how many questions you want (1-20)
7. **Generate Quiz**: Click the "Generate Quiz" button

### Taking the Quiz

1. **Answer Questions**: Click on one of the four answer options (A, B, C, or D)
2. **Get Feedback**: 
   - If correct: See a success message and earn points
   - If incorrect: See the error and optionally get coaching
3. **Coaching Option**: When you answer incorrectly, you can:
   - Click "🎓 Get Coaching" for personalized Socratic method guidance
   - Click "Skip to Answer" to see the correct answer immediately
4. **Continue**: After reviewing feedback (and optionally coaching), click "Next Question"
5. **View Results**: At the end, see your total score and detailed question review

### Using the Coaching Feature

When you answer incorrectly and choose coaching:

1. **Initial Question**: The AI tutor will ask you a thoughtful question to guide your thinking
2. **Interactive Chat**: Type your responses or questions in the chat input
3. **Guided Discovery**: The tutor will continue asking questions and providing hints
4. **Answer Revelation**: Once you understand or ask for it, the correct answer will be revealed with explanation
5. **Skip Option**: You can skip to the answer at any time using the "Show Answer" button

## 🏗️ Project Structure

```
QuizAgent/
├── QuizAgent.py              # Main Streamlit application
├── coaching_agent.py         # Socratic method coaching agent
├── question_database.py      # SQLite database operations for question storage
├── test_e2e.py              # End-to-end test suite
├── run_tests.py             # Test runner script
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create this)
├── quiz_questions.db        # SQLite database (auto-generated)
├── user_quiz_history.json   # User quiz history storage (auto-generated)
└── README.md                 # This file
```

## 🛠️ Technologies Used

- **Streamlit**: Web application framework
- **Google Gemini AI**: Question generation and coaching (via `google-generativeai` and `langchain-google-genai`)
- **LangChain**: LLM orchestration and conversation management for coaching
- **SQLite**: Local database for question storage and retrieval
- **Python-dotenv**: Environment variable management

## 📋 Key Components

### QuizAgent.py
- Main application interface
- Quiz generation using Gemini AI
- User history tracking
- Quiz taking interface
- Score calculation and results display
- Error reporting and validation

### coaching_agent.py
- Socratic method coaching implementation
- Interactive chat interface for student-tutor conversation
- Adaptive coaching responses based on student understanding
- Uses Gemini AI for personalized guidance

### question_database.py
- SQLite database operations
- Question storage and retrieval by grade, board, topic, and difficulty
- Partial question handling for efficient quiz generation
- Question validation and invalidation tracking
- Database initialization and management

## 🔧 Configuration

### Environment Variables

The application requires the following environment variable:

- `GOOGLE_API_KEY`: Your Google Gemini API key (required)

### File Storage

- `user_quiz_history.json`: Automatically created to store user quiz history. Contains:
  - User names
  - Quiz metadata (grade, board, topic, timestamp)
  - Previously asked questions (to avoid duplicates)

- `quiz_questions.db`: SQLite database automatically created to store quiz questions. Contains:
  - Questions organized by grade, board, topic, and difficulty
  - Question options and correct answers
  - Validation status (valid/invalid)
  - Timestamps for tracking

## 🎯 Features in Detail

### Question Uniqueness
The system tracks all previously asked questions for each user, grade, board, and topic combination. When generating new quizzes, it ensures questions are unique and different from previous ones.

### Database-Driven Question Management
- Questions are stored in SQLite database for efficient retrieval
- When generating a quiz, the system first checks the database for existing questions
- If sufficient questions exist, they are reused (reducing API calls)
- If insufficient questions exist, only the missing questions are generated
- This approach improves performance and reduces API costs

### Scoring System
- **Easy questions**: 1 point
- **Medium questions**: 2 points
- **Hard questions**: 4 points

Points are only awarded for correct answers.

### Coaching Philosophy
The coaching agent uses the Socratic method:
- Asks open-ended questions
- Breaks down problems into smaller parts
- Guides students to identify mistakes
- Helps understand underlying concepts
- Never directly reveals answers (unless student is ready)

## 🐛 Troubleshooting

### API Key Issues
- Ensure your `.env` file is in the project root
- Verify your `GOOGLE_API_KEY` is correctly set
- Check that the API key has proper permissions

### Import Errors
If you encounter LangChain import errors:
```bash
pip install --upgrade langchain langchain-core langchain-google-genai
```

### Database Issues
- The database file (`quiz_questions.db`) is automatically created on first run
- If you encounter database errors, you can safely delete `quiz_questions.db` to recreate it
- Database schema is automatically initialized when the application starts

### Question Generation Fails
- Check your internet connection
- Verify your API key is valid and has quota remaining
- Try reducing the number of questions

## 📝 Notes

- The application uses `gemini-2.5-pro` model for question generation and error verification
- The application uses `gemini-2.5-flash` model for coaching (faster responses)
- Quiz history is stored locally in JSON format
- Questions are stored in SQLite database for efficient reuse
- The coaching feature requires an active internet connection for AI responses
- Questions are cached in the database to reduce API calls and improve performance

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## 📄 License

This project is open source and available for educational purposes.

---

**Happy Learning! 🎓**
