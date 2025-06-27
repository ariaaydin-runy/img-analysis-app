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

def parse_structured_analysis(response_text):
    """Parse the GPT response into structured JSON format"""
    try:
        # Initialize the structured data
        structured_data = {
            "scores": {
                "kitchen_quality": None,
                "bathroom_quality": None,
                "natural_light": None,
                "overall_condition": None,
                "living_space_quality": None,
                "size_space": None,
                "building_quality": None
            },
            "property_details": {
                "property_type": None,
                "furnishing_status": None,
                "is_furnished": False,
                "digital_staging": None,
                "outdoor_space": False,
                "estimated_sqft": None
            },
            "amenities": [],
            "assessment_notes": {
                "total_images_analyzed": None,
                "areas_unable_to_assess": [],
                "scoring_confidence": None
            },
            "image_usage": {
                "kitchen_images": [],
                "bathroom_images": [],
                "living_space_images": [],
                "building_exterior_images": []
            },
            "raw_analysis_text": response_text
        }
        
        lines = response_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse scores (looking for "Category: X/10" pattern)
            if '/10' in line and ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    category = parts[0].strip().lower()
                    score_text = parts[1].strip()
                    
                    # Extract score number
                    try:
                        # Handle formats like "[8]/10" or "8/10" or "8.5/10"
                        score_part = score_text.split('/')[0].strip().strip('[]')
                        score = float(score_part)
                        
                        # Map to our score categories
                        if 'kitchen' in category:
                            structured_data["scores"]["kitchen_quality"] = score
                        elif 'bathroom' in category:
                            structured_data["scores"]["bathroom_quality"] = score
                        elif 'natural light' in category or 'light' in category:
                            structured_data["scores"]["natural_light"] = score
                        elif 'overall condition' in category or 'condition' in category:
                            structured_data["scores"]["overall_condition"] = score
                        elif 'living space' in category or 'space quality' in category:
                            structured_data["scores"]["living_space_quality"] = score
                        elif 'size' in category or 'space score' in category:
                            structured_data["scores"]["size_space"] = score
                        elif 'building' in category:
                            structured_data["scores"]["building_quality"] = score
                    except (ValueError, IndexError):
                        continue
            
            # Parse property details
            elif line.startswith('Property Type:'):
                structured_data["property_details"]["property_type"] = line.split(':', 1)[1].strip()
            elif line.startswith('Furnishing Status:'):
                status = line.split(':', 1)[1].strip()
                structured_data["property_details"]["furnishing_status"] = status
                structured_data["property_details"]["is_furnished"] = 'furnished' in status.lower() and 'unfurnished' not in status.lower()
            elif line.startswith('Digital Staging:'):
                staging = line.split(':', 1)[1].strip().lower()
                structured_data["property_details"]["digital_staging"] = staging == 'yes'
            elif line.startswith('Outdoor Space:'):
                outdoor = line.split(':', 1)[1].strip().lower()
                structured_data["property_details"]["outdoor_space"] = outdoor == 'yes'
            elif line.startswith('Estimated Square Footage:'):
                try:
                    sqft_text = line.split(':', 1)[1].strip()
                    # Extract number from text like "800 sq ft"
                    sqft_number = ''.join(filter(str.isdigit, sqft_text))
                    if sqft_number:
                        structured_data["property_details"]["estimated_sqft"] = int(sqft_number)
                except:
                    pass
            
            # Parse amenities
            elif line.startswith('AMENITIES OBSERVED:'):
                amenities_text = line.split(':', 1)[1].strip()
                if amenities_text and amenities_text.lower() not in ['none', 'none clearly visible', '']:
                    # Split by commas and clean up
                    amenities = [a.strip() for a in amenities_text.split(',') if a.strip()]
                    structured_data["amenities"] = amenities
            
            # Parse assessment notes
            elif line.startswith('Total Images Analyzed:'):
                try:
                    count = int(''.join(filter(str.isdigit, line)))
                    structured_data["assessment_notes"]["total_images_analyzed"] = count
                except:
                    pass
            elif line.startswith('Scoring Confidence:'):
                confidence = line.split(':', 1)[1].strip()
                structured_data["assessment_notes"]["scoring_confidence"] = confidence
            elif line.startswith('Areas Unable to Assess:'):
                areas_text = line.split(':', 1)[1].strip()
                if areas_text and areas_text.lower() not in ['none', '']:
                    areas = [a.strip() for a in areas_text.split(',') if a.strip()]
                    structured_data["assessment_notes"]["areas_unable_to_assess"] = areas
            
            # Parse image usage breakdown
            elif line.startswith('Images used for Kitchen scoring:'):
                images_text = line.split(':', 1)[1].strip()
                if images_text and images_text.lower() not in ['none', 'none visible']:
                    try:
                        # Parse image numbers like "1, 2, 3"
                        image_nums = [int(x.strip()) for x in images_text.split(',') if x.strip().isdigit()]
                        structured_data["image_usage"]["kitchen_images"] = image_nums
                    except:
                        pass
            elif line.startswith('Images used for Bathroom scoring:'):
                images_text = line.split(':', 1)[1].strip()
                if images_text and images_text.lower() not in ['none', 'none visible']:
                    try:
                        image_nums = [int(x.strip()) for x in images_text.split(',') if x.strip().isdigit()]
                        structured_data["image_usage"]["bathroom_images"] = image_nums
                    except:
                        pass
            elif line.startswith('Images used for Living Space scoring:'):
                images_text = line.split(':', 1)[1].strip()
                if images_text and images_text.lower() not in ['none', 'none visible']:
                    try:
                        image_nums = [int(x.strip()) for x in images_text.split(',') if x.strip().isdigit()]
                        structured_data["image_usage"]["living_space_images"] = image_nums
                    except:
                        pass
            elif line.startswith('Images used for Building/Exterior scoring:'):
                images_text = line.split(':', 1)[1].strip()
                if images_text and images_text.lower() not in ['none', 'none visible']:
                    try:
                        image_nums = [int(x.strip()) for x in images_text.split(',') if x.strip().isdigit()]
                        structured_data["image_usage"]["building_exterior_images"] = image_nums
                    except:
                        pass
        
        return structured_data
        
    except Exception as e:
        print(f"Error parsing structured analysis: {e}")
        return {
            "scores": {},
            "property_details": {},
            "amenities": [],
            "assessment_notes": {},
            "image_usage": {},
            "raw_analysis_text": response_text,
            "parsing_error": str(e)
        }

def tag_images_with_analysis(image_urls, structured_data):
    """Tag images based on GPT's analysis and intelligent fallback logic"""
    tagged_images = {
        "all_images": [{"url": url, "index": i} for i, url in enumerate(image_urls)],
        "kitchen_images": [],
        "bathroom_images": [],
        "living_space_images": [],
        "building_images": [],
        "exterior_images": [],
        "bedroom_images": [],
        "other_images": []
    }
    
    # First, try to use the image usage data from GPT's analysis
    image_usage = structured_data.get("image_usage", {})
    
    # Map GPT's image numbers (1-based) to our 0-based indices and URLs
    if image_usage.get("kitchen_images"):
        for img_num in image_usage["kitchen_images"]:
            idx = img_num - 1  # Convert to 0-based index
            if 0 <= idx < len(image_urls):
                tagged_images["kitchen_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": True})
    
    if image_usage.get("bathroom_images"):
        for img_num in image_usage["bathroom_images"]:
            idx = img_num - 1
            if 0 <= idx < len(image_urls):
                tagged_images["bathroom_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": True})
    
    if image_usage.get("living_space_images"):
        for img_num in image_usage["living_space_images"]:
            idx = img_num - 1
            if 0 <= idx < len(image_urls):
                tagged_images["living_space_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": True})
    
    if image_usage.get("building_exterior_images"):
        for img_num in image_usage["building_exterior_images"]:
            idx = img_num - 1
            if 0 <= idx < len(image_urls):
                tagged_images["building_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": True})
                tagged_images["exterior_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": True})
    
    # If GPT didn't identify specific images for categories that got scores, 
    # try to parse from the raw analysis text as a backup
    scores = structured_data.get("scores", {})
    raw_text = structured_data.get("raw_analysis_text", "")
    
    # Parse raw text for image references if GPT data is missing
    if not tagged_images["kitchen_images"] and scores.get("kitchen_quality"):
        kitchen_imgs = parse_images_from_text(raw_text, "kitchen")
        for idx in kitchen_imgs:
            if 0 <= idx < len(image_urls):
                tagged_images["kitchen_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": False, "text_parsed": True})
    
    if not tagged_images["bathroom_images"] and scores.get("bathroom_quality"):
        bathroom_imgs = parse_images_from_text(raw_text, "bathroom")
        for idx in bathroom_imgs:
            if 0 <= idx < len(image_urls):
                tagged_images["bathroom_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": False, "text_parsed": True})
    
    if not tagged_images["living_space_images"] and scores.get("living_space_quality"):
        living_imgs = parse_images_from_text(raw_text, "living")
        for idx in living_imgs:
            if 0 <= idx < len(image_urls):
                tagged_images["living_space_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": False, "text_parsed": True})
    
    if not tagged_images["building_images"] and scores.get("building_quality"):
        building_imgs = parse_images_from_text(raw_text, "building")
        for idx in building_imgs:
            if 0 <= idx < len(image_urls):
                tagged_images["building_images"].append({"url": image_urls[idx], "index": idx, "gpt_identified": False, "text_parsed": True})
    
    # As a last resort, use conservative fallback logic only for scored categories
    used_indices = set()
    for category_images in [tagged_images["kitchen_images"], tagged_images["bathroom_images"], 
                           tagged_images["living_space_images"], tagged_images["building_images"]]:
        for img in category_images:
            used_indices.add(img["index"])
    
    # Only assign fallback images if we have scores but no identified images
    if scores.get("kitchen_quality") and not tagged_images["kitchen_images"]:
        # Conservative: assign only first 2 images as potential kitchen
        for i in range(min(2, len(image_urls))):
            if i not in used_indices:
                tagged_images["kitchen_images"].append({"url": image_urls[i], "index": i, "gpt_identified": False, "fallback": True})
                used_indices.add(i)
                break
    
    if scores.get("bathroom_quality") and not tagged_images["bathroom_images"]:
        # Look for unused images, prefer middle indices for bathrooms
        for i in range(len(image_urls)):
            if i not in used_indices and len(tagged_images["bathroom_images"]) < 1:
                tagged_images["bathroom_images"].append({"url": image_urls[i], "index": i, "gpt_identified": False, "fallback": True})
                used_indices.add(i)
    
    if scores.get("living_space_quality") and not tagged_images["living_space_images"]:
        # Conservative: assign first unused image
        for i in range(len(image_urls)):
            if i not in used_indices:
                tagged_images["living_space_images"].append({"url": image_urls[i], "index": i, "gpt_identified": False, "fallback": True})
                used_indices.add(i)
                break
    
    return tagged_images

def parse_images_from_text(analysis_text, category_keyword):
    """Parse image numbers from analysis text for a specific category"""
    if not analysis_text:
        return []
    
    import re
    
    # Look for patterns like "Images used for Kitchen scoring: 1, 2, 3"
    pattern = rf"Images used for {category_keyword}[^:]*:\s*([0-9, ]+)"
    match = re.search(pattern, analysis_text, re.IGNORECASE)
    
    if match:
        try:
            # Extract numbers and convert to 0-based indices
            numbers_text = match.group(1)
            numbers = [int(x.strip()) - 1 for x in numbers_text.split(',') if x.strip().isdigit()]
            return numbers
        except:
            pass
    
    # Alternative: look for mentions of the category with image numbers nearby
    lines = analysis_text.split('\n')
    for line in lines:
        line_lower = line.lower()
        if category_keyword.lower() in line_lower and any(char.isdigit() for char in line):
            # Extract numbers from this line
            numbers = re.findall(r'\b(\d+)\b', line)
            try:
                # Convert to 0-based indices, limit to reasonable range
                indices = [int(n) - 1 for n in numbers if 1 <= int(n) <= 20]
                if indices:
                    return indices[:3]  # Limit to 3 images max
            except:
                continue
    
    return []

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
    """Analyze property images using GPT-4o with structured output"""
    
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
        
        # Parse the response into structured format
        structured_data = parse_structured_analysis(response_text)
        
        # Tag images with analysis categories
        tagged_images = tag_images_with_analysis(limited_urls, structured_data)
        
        # Successful analysis
        return {
            "success": True,
            "structured_analysis": structured_data,
            "tagged_images": tagged_images,
            "images_analyzed": len(limited_urls),
            "raw_image_urls": limited_urls,
            "timestamp": datetime.now().isoformat(),
            "analysis_method": "structured_rubric_based",
            # Keep legacy field for compatibility
            "analysis": response_text
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
    """Analyze a single property using structured scoring"""
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
    
    # Analyze with GPT-4o using structured approach
    result = analyze_property_with_gpt4v(photo_urls, display_index)
    result["original_property_index"] = original_index
    result["display_index"] = display_index
    result["total_images_available"] = len(photo_urls)
    
    return result

def add_new_analyses(count):
    """Add new analyses to the rolling file using structured scoring"""
    
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
    print("Using structured analysis for filtering and sorting capabilities")
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
    
    # Print structured scores
    structured = result.get("structured_analysis", {})
    scores = structured.get("scores", {})
    
    print("SCORES:")
    for category, score in scores.items():
        if score is not None:
            print(f"  {category.replace('_', ' ').title()}: {score}/10")
    
    property_details = structured.get("property_details", {})
    print(f"\nPROPERTY DETAILS:")
    print(f"  Type: {property_details.get('property_type', 'Unknown')}")
    print(f"  Furnished: {property_details.get('is_furnished', False)}")
    print(f"  Estimated Sq Ft: {property_details.get('estimated_sqft', 'Unknown')}")
    
    amenities = structured.get("amenities", [])
    if amenities:
        print(f"\nAMENITIES: {', '.join(amenities)}")
    
    # Print tagged images summary
    tagged = result.get("tagged_images", {})
    print(f"\nIMAGE CATEGORIES:")
    for category, images in tagged.items():
        if category != "all_images" and images:
            print(f"  {category.replace('_', ' ').title()}: {len(images)} images")
    
    print(f"\n{'-'*50}")

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
        
        # Show structured analysis stats
        structured_count = len([a for a in successful_analyses if a.get("structured_analysis")])
        print(f"Properties with structured analysis: {structured_count}")
        
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
                        "structured_analysis": found_analysis.get("structured_analysis", {}),
                        "tagged_images": found_analysis.get("tagged_images", {}),
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
        
        # Compare structured scores
        original_scores = test_analysis.get("structured_analysis", {}).get("scores", {})
        new_scores = new_result.get("structured_analysis", {}).get("scores", {})
        
        print("\nSCORE COMPARISON:")
        print("-" * 30)
        for category in original_scores.keys():
            orig_score = original_scores.get(category)
            new_score = new_scores.get(category)
            if orig_score is not None and new_score is not None:
                diff = abs(orig_score - new_score)
                status = "✅ CONSISTENT" if diff <= 1 else "⚠️ INCONSISTENT"
                print(f"  {category.replace('_', ' ').title()}: {orig_score} → {new_score} (diff: {diff:.1f}) {status}")
        
        print("\nCOMPARE THE AMENITIES AND DETAILS MANUALLY TO CHECK CONSISTENCY")
        print("Ideally, scores should be identical or very close for the same property.")
    else:
        print(f"Re-analysis failed: {new_result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    print("Property Image Analyzer (Structured Analysis System)")
    print("===================================================")
    
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
        print("6. Create calibration set")
        print("7. Test consistency")
        print("8. Exit")
        
        try:
            choice = input("\nSelect an option (1-8): ").strip()
            
            if choice == "1":
                show_status()
            
            elif choice == "2":
                add_new_analyses(1)
            
            elif choice == "3":
                add_new_analyses(3)
            
            elif choice == "4":
                add_new_analyses(5)
            
            elif choice == "5":
                add_new_analyses(50)
            
            elif choice == "6":
                create_calibration_set()
            
            elif choice == "7":
                test_consistency()
            
            elif choice == "8":
                print("Goodbye!")
                break
            
            else:
                print("Invalid choice. Please select 1-8.")
                
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Please try again.")