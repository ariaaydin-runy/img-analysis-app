import json
import time
import random
import openai
from datetime import datetime
from config import OPENAI_API_KEY, MAX_IMAGES_PER_PROPERTY, ANALYSIS_DELAY
from prompt import PROPERTY_ANALYSIS_PROMPT

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Rolling file configuration
ROLLING_FILE = "property_analyses.json"
CALIBRATION_FILE = "calibration_properties.json"

def is_refusal_response(response_text):
    """Check if the response is a refusal to analyze images"""
    refusal_indicators = [
        "I'm unable to provide detailed assessments",
        "I can't analyze these images",
        "I'm not able to score",
        "I cannot provide specific scores",
        "I'm unable to analyze",
        "I can't provide detailed analysis",
        "I'm not able to provide",
        "However, I can offer some general guidance",
        "I can offer some general guidance on what to consider"
    ]
    
    response_lower = response_text.lower()
    return any(indicator.lower() in response_lower for indicator in refusal_indicators)

def load_rolling_file():
    """Load existing analyses from the rolling file"""
    try:
        with open(ROLLING_FILE, 'r') as f:
            data = json.load(f)
        print(f"Loaded {len(data)} existing analyses from {ROLLING_FILE}")
        return data
    except FileNotFoundError:
        print(f"No existing {ROLLING_FILE} found - will create new one")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {ROLLING_FILE}")
        return []

def save_rolling_file(analyses):
    """Save analyses to the rolling file"""
    with open(ROLLING_FILE, 'w') as f:
        json.dump(analyses, f, indent=2)
    print(f"Saved {len(analyses)} analyses to {ROLLING_FILE}")

def load_calibration_properties():
    """Load calibration properties for reference scoring"""
    try:
        with open(CALIBRATION_FILE, 'r') as f:
            data = json.load(f)
        print(f"Loaded {len(data)} calibration properties")
        return data
    except FileNotFoundError:
        print("No calibration file found - will create empty one")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {CALIBRATION_FILE}")
        return []

def save_calibration_properties(calibration_data):
    """Save calibration properties"""
    with open(CALIBRATION_FILE, 'w') as f:
        json.dump(calibration_data, f, indent=2)
    print(f"Saved calibration properties to {CALIBRATION_FILE}")

def get_analyzed_property_indices(existing_analyses):
    """Get set of property indices that have already been analyzed successfully"""
    analyzed_indices = set()
    for analysis in existing_analyses:
        if analysis.get("success", False) and not analysis.get("refusal", False):
            original_index = analysis.get("original_property_index")
            if original_index is not None:
                analyzed_indices.add(original_index)
    return analyzed_indices

def analyze_property_with_gpt4v(photo_urls, property_index=None):
    """Analyze property images using GPT-4o with rubric-based scoring"""
    
    # Limit number of images to control costs
    limited_urls = photo_urls[:MAX_IMAGES_PER_PROPERTY]
    
    print(f"Analyzing property {property_index or 'unknown'} with {len(limited_urls)} images...")
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": PROPERTY_ANALYSIS_PROMPT
                }
            ] + [
                {
                    "type": "image_url",
                    "image_url": {"url": url}
                }
                for url in limited_urls
            ]
        }
    ]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=2000,
            temperature=0.0  # Set to 0 for maximum consistency
        )
        
        response_text = response.choices[0].message.content
        
        # Check if this is a refusal response
        if is_refusal_response(response_text):
            print(f"🚫 Refusal detected for property {property_index} - will be skipped")
            return {
                "success": False,
                "error": "Model refused to analyze images",
                "refusal": True,
                "images_analyzed": 0,
                "raw_image_urls": limited_urls,
                "timestamp": datetime.now().isoformat(),
                "response_text": response_text[:200] + "..." if len(response_text) > 200 else response_text
            }
        
        # Successful analysis
        return {
            "success": True,
            "analysis": response_text,
            "images_analyzed": len(limited_urls),
            "raw_image_urls": limited_urls,
            "timestamp": datetime.now().isoformat(),
            "analysis_method": "rubric_based"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "refusal": False,
            "images_analyzed": 0,
            "raw_image_urls": limited_urls,
            "timestamp": datetime.now().isoformat()
        }

def load_properties_data(filename="images.json"):
    """Load property data from JSON file"""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        print(f"Loaded {len(data)} properties from {filename}")
        return data
    except FileNotFoundError:
        print(f"Error: {filename} not found!")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {filename}")
        return []

def parse_image_urls(images_string):
    """Parse the images string from JSON format"""
    try:
        # Remove outer quotes and parse as JSON array
        return json.loads(images_string)
    except:
        print(f"Error parsing images string: {images_string}")
        return []

def analyze_single_property(property_data, original_index, display_index):
    """Analyze a single property using rubric-based scoring"""
    images_string = property_data.get("images", "[]")
    photo_urls = parse_image_urls(images_string)
    
    if not photo_urls:
        return {
            "success": False,
            "error": "No valid image URLs found",
            "refusal": False,
            "original_property_index": original_index,
            "display_index": display_index
        }
    
    print(f"\nProperty {display_index} (Original Index: {original_index}): Found {len(photo_urls)} images")
    
    # Analyze with GPT-4o using rubric-based approach
    result = analyze_property_with_gpt4v(photo_urls, display_index)
    result["original_property_index"] = original_index
    result["display_index"] = display_index
    result["total_images_available"] = len(photo_urls)
    
    return result

def add_new_analyses(count):
    """Add new analyses to the rolling file using rubric-based scoring"""
    
    # Load existing analyses
    existing_analyses = load_rolling_file()
    analyzed_indices = get_analyzed_property_indices(existing_analyses)
    
    # Load all available properties
    properties_data = load_properties_data()
    if not properties_data:
        print("No properties data found!")
        return
    
    # Find unanalyzed properties
    unanalyzed_properties = []
    for i, prop_data in enumerate(properties_data):
        if i not in analyzed_indices:
            unanalyzed_properties.append((i, prop_data))
    
    if not unanalyzed_properties:
        print("All properties have already been analyzed!")
        return
    
    print(f"Found {len(unanalyzed_properties)} unanalyzed properties")
    print(f"Will attempt to add {count} new successful analyses")
    print("Using rubric-based analysis for consistent scoring")
    print("✨ Each analysis will be saved immediately to prevent data loss")
    
    # Randomly select properties to analyze
    if len(unanalyzed_properties) > count * 2:
        selected_properties = random.sample(unanalyzed_properties, min(count * 2, len(unanalyzed_properties)))
    else:
        selected_properties = unanalyzed_properties.copy()
        random.shuffle(selected_properties)
    
    new_analyses = []
    attempts = 0
    successful_count = 0
    refusal_count = 0
    error_count = 0
    
    # Generate the next display index
    next_display_index = len(existing_analyses) + 1
    
    i = 0
    while i < len(selected_properties) and successful_count < count:
        
        original_index, property_data = selected_properties[i]
        display_index = next_display_index + len(new_analyses)
        
        attempts += 1
        
        print(f"\n{'='*60}")
        print(f"ANALYZING PROPERTY (Attempt #{attempts})")
        print(f"Original Index: {original_index}, Display Index: {display_index}")
        print(f"Target: {successful_count + 1}/{count} successful analyses")
        print(f"{'='*60}")
        
        result = analyze_single_property(property_data, original_index, display_index)
        
        # Add result to our tracking list
        new_analyses.append(result)
        
        # IMMEDIATELY save to file after each analysis (successful or not)
        current_all_analyses = existing_analyses + new_analyses
        save_rolling_file(current_all_analyses)
        print(f"💾 Analysis #{len(new_analyses)} saved to file immediately")
        
        if result["success"]:
            print(f"✅ Success! Analysis #{successful_count + 1} completed")
            successful_count += 1
            print_formatted_result(result)
        elif result.get("refusal", False):
            print(f"🚫 Refusal detected - continuing to next property")
            refusal_count += 1
        else:
            print(f"❌ Analysis failed: {result.get('error', 'Unknown error')} - continuing to next property")
            error_count += 1
        
        i += 1
        
        # Rate limiting - wait between requests (but not after the last one)
        if successful_count < count and i < len(selected_properties):
            print(f"\nWaiting {ANALYSIS_DELAY} seconds before next analysis...")
            time.sleep(ANALYSIS_DELAY)
    
    # Print summary (file is already saved)
    total_in_file = len(existing_analyses) + len(new_analyses)
    print_final_summary(successful_count, attempts, refusal_count, error_count, count, total_in_file)
    
    return new_analyses

def print_formatted_result(result):
    """Print analysis result in organized format"""
    if not result["success"]:
        return
    
    print(f"\n{'-'*50}")
    print(f"PROPERTY {result['display_index']} ANALYSIS")
    print(f"(Original Index: {result['original_property_index']})")
    print(f"Method: {result.get('analysis_method', 'unknown')}")
    print(f"{'-'*50}")
    
    analysis_text = result["analysis"]
    print(analysis_text)
    
    print(f"\n{'-'*30}")
    print("RAW IMAGE URLS:")
    print(f"{'-'*30}")
    for url in result["raw_image_urls"]:
        print(url)
    print(f"{'-'*50}")

def print_final_summary(successful_count, total_attempts, refusal_count, error_count, target_count, total_in_file):
    """Print final summary of the analysis process"""
    print(f"\n{'='*60}")
    print(f"ANALYSIS SESSION SUMMARY")
    print(f"{'='*60}")
    print(f"Target new analyses: {target_count}")
    print(f"Successful new analyses: {successful_count}")
    print(f"Properties attempted: {total_attempts}")
    print(f"Refusals encountered: {refusal_count}")
    print(f"Errors encountered: {error_count}")
    print(f"Total analyses now in file: {total_in_file}")
    
    if successful_count > 0:
        success_rate = successful_count / max(total_attempts, 1) * 100
        print(f"Session success rate: {success_rate:.1f}%")
        
        if successful_count == target_count:
            print(f"🎉 Target achieved! Added all {target_count} new analyses")
        else:
            print(f"⚠️  Only added {successful_count}/{target_count} target analyses")
    
    print(f"\n📊 Rolling file now contains analyses for {total_in_file} properties")

def show_status():
    """Show current status of analyses"""
    existing_analyses = load_rolling_file()
    properties_data = load_properties_data()
    
    if not properties_data:
        print("No properties data found!")
        return
    
    analyzed_indices = get_analyzed_property_indices(existing_analyses)
    successful_analyses = [a for a in existing_analyses if a.get("success", False) and not a.get("refusal", False)]
    
    print(f"\n{'='*60}")
    print(f"CURRENT STATUS")
    print(f"{'='*60}")
    print(f"Total properties available: {len(properties_data)}")
    print(f"Properties successfully analyzed: {len(successful_analyses)}")
    print(f"Properties remaining: {len(properties_data) - len(analyzed_indices)}")
    print(f"Total entries in rolling file: {len(existing_analyses)}")
    
    # Show some stats about successful analyses
    if successful_analyses:
        total_images = sum(a.get("images_analyzed", 0) for a in successful_analyses)
        avg_images = total_images / len(successful_analyses)
        print(f"Total images processed: {total_images}")
        print(f"Average images per property: {avg_images:.1f}")
        
        # Show latest analysis timestamp
        timestamps = [a.get("timestamp") for a in successful_analyses if a.get("timestamp")]
        if timestamps:
            latest = max(timestamps)
            print(f"Latest analysis: {latest}")

def create_calibration_set():
    """Interactive creation of calibration properties"""
    print("\nCalibration Set Creation")
    print("========================")
    print("This will help you select reference properties for consistent scoring.")
    
    properties_data = load_properties_data()
    if not properties_data:
        print("No properties data found!")
        return
    
    existing_analyses = load_rolling_file()
    successful_analyses = [a for a in existing_analyses if a.get("success", False) and not a.get("refusal", False)]
    
    if len(successful_analyses) < 10:
        print(f"You need at least 10 analyzed properties to create a calibration set.")
        print(f"Currently have {len(successful_analyses)} successful analyses.")
        return
    
    print(f"Found {len(successful_analyses)} analyzed properties to choose from.")
    print("Please review your analyses and identify:")
    print("1. 2-3 luxury/high-end properties (would score 9-10)")
    print("2. 2-3 above-average properties (would score 7-8)")
    print("3. 2-3 average properties (would score 5-6)")
    print("4. 2-3 below-average properties (would score 3-4)")
    print("5. 2-3 basic/poor properties (would score 1-2)")
    
    calibration_properties = []
    
    tiers = [
        ("luxury", "9-10", "high-end"),
        ("above_average", "7-8", "above-average"),
        ("average", "5-6", "average market"),
        ("below_average", "3-4", "below-average"),
        ("basic", "1-2", "basic/poor")
    ]
    
    for tier_name, score_range, description in tiers:
        print(f"\n--- Selecting {description} properties (score {score_range}) ---")
        
        while True:
            display_index = input(f"Enter display index for a {description} property (or 'done' to finish this tier): ").strip()
            
            if display_index.lower() == 'done':
                break
            
            try:
                display_index = int(display_index)
                # Find the analysis with this display index
                found_analysis = None
                for analysis in successful_analyses:
                    if analysis.get("display_index") == display_index:
                        found_analysis = analysis
                        break
                
                if found_analysis:
                    calibration_properties.append({
                        "tier": tier_name,
                        "score_range": score_range,
                        "display_index": display_index,
                        "original_property_index": found_analysis.get("original_property_index"),
                        "image_urls": found_analysis.get("raw_image_urls", []),
                        "analysis": found_analysis.get("analysis", ""),
                        "timestamp": datetime.now().isoformat()
                    })
                    print(f"✅ Added property {display_index} as {description}")
                else:
                    print(f"❌ Could not find analysis with display index {display_index}")
                    
            except ValueError:
                print("Please enter a valid number or 'done'")
    
    if calibration_properties:
        save_calibration_properties(calibration_properties)
        print(f"\n✅ Created calibration set with {len(calibration_properties)} properties")
        
        # Show summary
        tier_counts = {}
        for prop in calibration_properties:
            tier = prop["tier"]
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        print("\nCalibration set summary:")
        for tier_name, score_range, description in tiers:
            count = tier_counts.get(tier_name, 0)
            print(f"  {description} ({score_range}): {count} properties")
    else:
        print("No calibration properties selected.")

def test_consistency():
    """Test consistency by re-analyzing a property that was already analyzed"""
    existing_analyses = load_rolling_file()
    successful_analyses = [a for a in existing_analyses if a.get("success", False) and not a.get("refusal", False)]
    
    if not successful_analyses:
        print("No successful analyses found to test consistency!")
        return
    
    # Select a random successful analysis
    test_analysis = random.choice(successful_analyses)
    original_index = test_analysis.get("original_property_index")
    display_index = test_analysis.get("display_index")
    
    print(f"\nTesting consistency by re-analyzing Property {display_index} (Original Index: {original_index})")
    print("This will help verify that the rubric produces consistent scores for the same property.")
    
    # Get the property data
    properties_data = load_properties_data()
    if original_index >= len(properties_data):
        print("Error: Original index out of range!")
        return
    
    property_data = properties_data[original_index]
    
    # Re-analyze the property
    new_result = analyze_single_property(property_data, original_index, f"{display_index}_retest")
    
    if new_result["success"]:
        print("\n" + "="*60)
        print("CONSISTENCY TEST RESULTS")
        print("="*60)
        print("\nORIGINAL ANALYSIS:")
        print("-" * 30)
        print(test_analysis["analysis"][:500] + "..." if len(test_analysis["analysis"]) > 500 else test_analysis["analysis"])
        
        print("\nNEW ANALYSIS:")
        print("-" * 30)
        print(new_result["analysis"][:500] + "..." if len(new_result["analysis"]) > 500 else new_result["analysis"])
        
        print("\nCOMPARE THE SCORES MANUALLY TO CHECK CONSISTENCY")
        print("Ideally, scores should be identical or very close for the same property.")
    else:
        print(f"Re-analysis failed: {new_result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    print("Property Image Analyzer (Rubric-Based Consistent Scoring)")
    print("========================================================")
    
    # Check if API key is set
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not found!")
        print("Make sure your API key is set in config.py")
        exit(1)
    
    while True:
        print("\nOptions:")
        print("1. Show current status")
        print("2. Add 1 new analysis")
        print("3. Add 3 new analyses")
        print("4. Add 5 new analyses")
        print("5. Add 10 new analyses")
        print("6. Add custom number of analyses")
        print("7. Create calibration set")
        print("8. Test consistency (re-analyze existing property)")
        print("9. Exit")
        
        choice = input("\nEnter your choice (1-9): ").strip()
        
        if choice == "1":
            show_status()
        elif choice == "2":
            add_new_analyses(1)
        elif choice == "3":
            add_new_analyses(3)
        elif choice == "4":
            add_new_analyses(5)
        elif choice == "5":
            add_new_analyses(10)
        elif choice == "6":
            try:
                count = int(input("How many new analyses to add? "))
                if count > 0:
                    add_new_analyses(count)
                else:
                    print("Please enter a positive number")
            except ValueError:
                print("Please enter a valid number")
        elif choice == "7":
            create_calibration_set()
        elif choice == "8":
            test_consistency()
        elif choice == "9":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")