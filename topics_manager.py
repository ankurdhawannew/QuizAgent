"""
Topics Manager Module
Handles prepopulation and storage of topics and subtopics for each grade and curriculum combination.
"""

import os
import json
import google.generativeai as genai
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# File to store topics and subtopics
TOPICS_FILE = "topics_subtopics.json"


def load_topics() -> Dict:
    """Load topics and subtopics from JSON file."""
    if os.path.exists(TOPICS_FILE):
        try:
            with open(TOPICS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading topics file: {e}")
            return {}
    return {}


def save_topics(topics_data: Dict):
    """Save topics and subtopics to JSON file."""
    try:
        with open(TOPICS_FILE, 'w', encoding='utf-8') as f:
            json.dump(topics_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving topics file: {e}")


def get_topics_key(grade: int, board: str) -> str:
    """Generate a key for storing topics by grade and board."""
    return f"Grade_{grade}_{board}"


def get_topics_for_grade_board(grade: int, board: str) -> Dict[str, List[str]]:
    """
    Get topics and subtopics for a specific grade and board.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        
    Returns:
        Dictionary with topics as keys and lists of subtopics as values
        Format: {"Topic Name": ["Sub topic 1", "Sub topic 2", ...]}
    """
    topics_data = load_topics()
    key = get_topics_key(grade, board)
    return topics_data.get(key, {})


def fetch_topics_from_gemini(grade: int, board: str) -> Dict[str, List[str]]:
    """
    Fetch topics and subtopics from Gemini API for a specific grade and curriculum.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        
    Returns:
        Dictionary with topics as keys and lists of subtopics as values
    """
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    prompt = f"""Give me the list of topics taught as per the maths curriculum of Grade {grade} {board} in the below JSON format {{"Topic": ["Sub topic", "Sub Topic"]}} e.g. {{"Knowing Your Number":["Comparing Large Numbers", "Roman Numerals","Estimation"],"Whole Numbers":["Number Line","Properties of whole number"]}}

Return ONLY valid JSON without any markdown formatting, code blocks, or additional text. The response should be a valid JSON object where each key is a topic name and each value is an array of subtopic strings."""

    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(prompt)
        
        # Extract JSON from response
        response_text = response.text.strip()
        
        # Try to extract JSON if it's wrapped in markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        topics_dict = json.loads(response_text)
        
        # Validate structure
        if not isinstance(topics_dict, dict):
            raise ValueError("Response is not a dictionary")
        
        # Ensure all values are lists
        validated_dict = {}
        for topic, subtopics in topics_dict.items():
            if isinstance(subtopics, list):
                validated_dict[topic] = subtopics
            elif isinstance(subtopics, str):
                validated_dict[topic] = [subtopics]
            else:
                validated_dict[topic] = []
        
        return validated_dict
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from Gemini: {e}")
        print(f"Raw response: {response_text}")
        raise ValueError(f"Failed to parse JSON response from Gemini: {e}")
    except Exception as e:
        print(f"Error fetching topics from Gemini: {e}")
        raise


def prepopulate_topics(grade: int, board: str, force_refresh: bool = False) -> Dict[str, List[str]]:
    """
    Prepopulate topics for a grade and board combination.
    If topics already exist and force_refresh is False, returns existing topics.
    Otherwise, fetches from Gemini and saves them.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        force_refresh: If True, fetch from Gemini even if topics exist
        
    Returns:
        Dictionary with topics as keys and lists of subtopics as values
    """
    topics_data = load_topics()
    key = get_topics_key(grade, board)
    
    # Check if topics already exist
    if key in topics_data and not force_refresh:
        return topics_data[key]
    
    # Fetch from Gemini
    try:
        topics_dict = fetch_topics_from_gemini(grade, board)
        
        # Save to file
        topics_data[key] = topics_dict
        save_topics(topics_data)
        
        return topics_dict
    except Exception as e:
        print(f"Error prepopulating topics: {e}")
        # Return existing topics if available, otherwise empty dict
        return topics_data.get(key, {})


def add_topic(grade: int, board: str, topic: str, subtopics: Optional[List[str]] = None):
    """
    Add a new topic (and optionally subtopics) to the list for a grade and board.
    If the topic already exists, it will be updated with new subtopics.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Topic name to add
        subtopics: Optional list of subtopics (defaults to empty list)
    """
    if not topic or not topic.strip():
        return
    
    topics_data = load_topics()
    key = get_topics_key(grade, board)
    
    # Initialize if doesn't exist
    if key not in topics_data:
        topics_data[key] = {}
    
    # Add or update topic
    topic_name = topic.strip()
    if subtopics is None:
        subtopics = []
    
    # If topic exists, merge subtopics (avoid duplicates)
    if topic_name in topics_data[key]:
        existing_subtopics = topics_data[key][topic_name]
        # Merge and remove duplicates while preserving order
        merged = list(dict.fromkeys(existing_subtopics + subtopics))
        topics_data[key][topic_name] = merged
    else:
        topics_data[key][topic_name] = subtopics
    
    # Save to file
    save_topics(topics_data)


def get_topic_list(grade: int, board: str) -> List[str]:
    """
    Get a simple list of topic names for a grade and board.
    Useful for dropdown/selectbox options.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        
    Returns:
        List of topic names
    """
    topics_dict = get_topics_for_grade_board(grade, board)
    return list(topics_dict.keys())


def get_subtopics_for_topic(grade: int, board: str, topic: str) -> List[str]:
    """
    Get subtopics for a specific topic.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        topic: Topic name
        
    Returns:
        List of subtopic names
    """
    topics_dict = get_topics_for_grade_board(grade, board)
    return topics_dict.get(topic, [])


def get_topic_subtopic_pairs(grade: int, board: str) -> List[str]:
    """
    Get a list of topic-subtopic pairs in "Topic - Subtopic" format.
    Useful for dropdown/selectbox options.
    
    Args:
        grade: Grade level (6-12)
        board: Education board (CBSE, ICSE, IB)
        
    Returns:
        List of strings in "Topic - Subtopic" format
    """
    topics_dict = get_topics_for_grade_board(grade, board)
    pairs = []
    
    for topic, subtopics in topics_dict.items():
        if subtopics:
            # Create a pair for each subtopic
            for subtopic in subtopics:
                pairs.append(f"{topic} - {subtopic}")
        else:
            # If no subtopics, just add the topic
            pairs.append(topic)
    
    return sorted(pairs)


def parse_topic_from_pair(topic_subtopic_pair: str) -> str:
    """
    Parse the topic name from a "Topic - Subtopic" format string.
    If the string doesn't contain " - ", returns the string as-is.
    
    Args:
        topic_subtopic_pair: String in "Topic - Subtopic" format
        
    Returns:
        Topic name (part before " - ")
    """
    if " - " in topic_subtopic_pair:
        return topic_subtopic_pair.split(" - ", 1)[0]
    return topic_subtopic_pair


def parse_subtopic_from_pair(topic_subtopic_pair: str) -> str:
    """
    Parse the subtopic name from a "Topic - Subtopic" format string.
    If the string doesn't contain " - ", returns the string as-is (assuming it's just a topic).
    
    Args:
        topic_subtopic_pair: String in "Topic - Subtopic" format
        
    Returns:
        Subtopic name (part after " - "), or the full string if no " - " separator
    """
    if " - " in topic_subtopic_pair:
        return topic_subtopic_pair.split(" - ", 1)[1]
    return topic_subtopic_pair

