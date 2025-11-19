"""
Script to prepopulate topics for all grade and board combinations.
This script fetches topics from Gemini API for all combinations of:
- Grades: 6-12 (7 grades)
- Boards: CBSE, ICSE, IB (3 boards)
Total: 7 * 3 = 21 combinations
"""

import os
import sys
from dotenv import load_dotenv
from topics_manager import prepopulate_topics

# Load environment variables
load_dotenv()

# Grades and boards to process
GRADES = list(range(6, 13))  # 6 to 12
BOARDS = ["CBSE", "ICSE", "IB"]

def main():
    """Prepopulate topics for all grade/board combinations."""
    print("=" * 60)
    print("Topics Prepopulation Script")
    print("=" * 60)
    print(f"Processing {len(GRADES)} grades × {len(BOARDS)} boards = {len(GRADES) * len(BOARDS)} combinations")
    print()
    
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY not found in environment variables.")
        print("Please set it in your .env file.")
        sys.exit(1)
    
    total_combinations = len(GRADES) * len(BOARDS)
    processed = 0
    successful = 0
    failed = 0
    skipped = 0
    
    # Process each combination
    for grade in GRADES:
        for board in BOARDS:
            processed += 1
            print(f"[{processed}/{total_combinations}] Processing Grade {grade} {board}...", end=" ")
            
            try:
                # Check if topics already exist
                from topics_manager import get_topics_for_grade_board
                existing_topics = get_topics_for_grade_board(grade, board)
                
                if existing_topics:
                    print(f"⏭️  Skipped (already exists with {len(existing_topics)} topics)")
                    skipped += 1
                else:
                    # Fetch topics from Gemini
                    topics_dict = prepopulate_topics(grade, board, force_refresh=False)
                    
                    if topics_dict:
                        total_subtopics = sum(len(subtopics) for subtopics in topics_dict.values())
                        print(f"✅ Success ({len(topics_dict)} topics, {total_subtopics} subtopics)")
                        successful += 1
                    else:
                        print("⚠️  No topics returned")
                        failed += 1
                        
            except Exception as e:
                print(f"❌ Failed: {str(e)}")
                failed += 1
    
    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total combinations: {total_combinations}")
    print(f"✅ Successful: {successful}")
    print(f"⏭️  Skipped (already exist): {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Processed: {processed}")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠️  Some combinations failed. You can run this script again to retry failed ones.")
        sys.exit(1)
    else:
        print("\n✅ All topics prepopulated successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()

