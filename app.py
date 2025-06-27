from flask import Flask, render_template, jsonify, request
import json
import os
from datetime import datetime
import re

app = Flask(__name__)

# Rolling file configuration
ROLLING_FILE = "property_analyses.json"

# Add custom Jinja2 functions
@app.template_global()
def any_func(iterable):
    """Custom any function for Jinja2"""
    return any(iterable)

@app.template_global()
def len_func(obj):
    """Custom len function for Jinja2"""
    return len(obj) if obj else 0

def is_valid_analysis(analysis_data):
    """Check if the analysis data contains valid structured analysis"""
    if not analysis_data:
        return False
    
    # Check for new structured format
    if analysis_data.get("structured_analysis"):
        structured = analysis_data["structured_analysis"]
        scores = structured.get("scores", {})
        
        # Check if we have at least some valid scores
        valid_scores = [v for v in scores.values() if v is not None and isinstance(v, (int, float))]
        return len(valid_scores) >= 3  # Require at least 3 categories scored
    
    # Fallback to old text-based validation
    analysis_text = analysis_data.get("analysis", "")
    if not analysis_text or len(analysis_text.strip()) < 100:
        return False
    
    # Check for common error patterns
    error_patterns = [
        "I'm unable to provide",
        "I cannot provide",
        "I can't provide",
        "I'm not able to",
        "I cannot analyze",
        "I can't analyze",
        "However, I can offer a general analysis",
        "I can offer general observations",
        "I apologize, but I cannot",
        "I'm sorry, but I cannot"
    ]
    
    analysis_lower = analysis_text.lower()
    for pattern in error_patterns:
        if pattern.lower() in analysis_lower:
            return False
    
    # Check for presence of scoring patterns (X/10)
    score_pattern = r'\d+(?:\.\d+)?/10'
    if not re.search(score_pattern, analysis_text):
        return False
    
    return True

def load_rolling_file():
    """Load analyses from the rolling file"""
    try:
        with open(ROLLING_FILE, 'r') as f:
            data = json.load(f)
        
        # Filter to only successful analyses with valid content
        valid_analyses = []
        for analysis in data:
            if (analysis.get('success', False) and 
                not analysis.get('refusal', False) and
                is_valid_analysis(analysis)):
                valid_analyses.append(analysis)
        
        print(f"Loaded {len(data)} total entries, {len(valid_analyses)} valid analyses from {ROLLING_FILE}")
        return valid_analyses
        
    except FileNotFoundError:
        print(f"Rolling file {ROLLING_FILE} not found!")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {ROLLING_FILE}")
        return []

def get_score_from_structured(structured_data, score_category):
    """Get a specific score from structured analysis data"""
    if not structured_data:
        return None
    
    scores = structured_data.get("scores", {})
    return scores.get(score_category)

def get_property_details(analysis_data):
    """Extract property details from analysis data"""
    structured = analysis_data.get("structured_analysis", {})
    
    if structured:
        details = structured.get("property_details", {})
        return {
            "property_type": details.get("property_type"),
            "is_furnished": details.get("is_furnished", False),
            "estimated_sqft": details.get("estimated_sqft"),
            "outdoor_space": details.get("outdoor_space", False),
            "furnishing_status": details.get("furnishing_status"),
            "digital_staging": details.get("digital_staging")
        }
    
    # Fallback to parsing text analysis
    return parse_legacy_analysis_text(analysis_data.get("analysis", ""))

def get_amenities(analysis_data):
    """Extract amenities from analysis data"""
    structured = analysis_data.get("structured_analysis", {})
    
    if structured:
        return structured.get("amenities", [])
    
    # Fallback to parsing text analysis
    analysis_text = analysis_data.get("analysis", "")
    lines = analysis_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith('AMENITIES OBSERVED:') or line.startswith('['):
            if ':' in line:
                amenities_text = line.split(':', 1)[1].strip()
            else:
                amenities_text = line.strip()
            
            amenities_text = amenities_text.strip('[]')
            if amenities_text and amenities_text != 'None':
                return [a.strip() for a in amenities_text.split(',') if a.strip()]
    
    return []

def parse_legacy_analysis_text(analysis_text):
    """Parse legacy text-based analysis for property details"""
    if not analysis_text:
        return {}
    
    details = {}
    lines = analysis_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('Property Type:'):
            details["property_type"] = line.split(':', 1)[1].strip()
        elif line.startswith('Furnishing Status:'):
            status = line.split(':', 1)[1].strip()
            details["furnishing_status"] = status
            details["is_furnished"] = 'furnished' in status.lower()
        elif line.startswith('Outdoor Space:'):
            outdoor = line.split(':', 1)[1].strip().lower()
            details["outdoor_space"] = outdoor in ['yes', 'true']
        elif line.startswith('Estimated Square Footage:'):
            try:
                sqft_text = line.split(':', 1)[1].strip()
                sqft_number = ''.join(filter(str.isdigit, sqft_text))
                if sqft_number:
                    details["estimated_sqft"] = int(sqft_number)
            except:
                pass
    
    return details

@app.route('/')
def index():
    """Main page showing all analyzed properties with sorting and viewing options"""
    results = load_rolling_file()
    
    # Get query parameters
    sort_by = request.args.get('sort_by', 'display_index')
    view_mode = request.args.get('view_mode', 'properties')  # 'properties' or 'images'
    score_category = request.args.get('score_category', 'kitchen_quality')
    
    # Add parsed data to each result
    for result in results:
        result['property_details'] = get_property_details(result)
        result['amenities'] = get_amenities(result)
        
        # Extract all scores for easy template access
        structured = result.get("structured_analysis", {})
        if structured:
            result['scores'] = structured.get("scores", {})
        else:
            result['scores'] = {}
    
    if view_mode == 'images':
        # Return image gallery view grouped by scores
        return render_image_gallery(results, score_category)
    else:
        # Property listing view with sorting
        if sort_by in ['kitchen_quality', 'bathroom_quality', 'natural_light', 'overall_condition', 
                       'living_space_quality', 'size_space', 'building_quality']:
            # Sort by score and group into bins
            scored_properties = []
            unscored_properties = []
            
            for result in results:
                score = get_score_from_structured(result.get("structured_analysis"), sort_by)
                if score is not None:
                    result['sort_score'] = score
                    scored_properties.append(result)
                else:
                    unscored_properties.append(result)
            
            # Sort scored properties by score (highest first)
            scored_properties.sort(key=lambda x: x.get('sort_score', 0), reverse=True)
            
            # Group into score bins
            score_bins = {
                '9-10': [],
                '7-8': [],
                '5-6': [],
                '3-4': [],
                '1-2': [],
                'Unscored': unscored_properties
            }
            
            for prop in scored_properties:
                score = prop['sort_score']
                if score >= 9:
                    score_bins['9-10'].append(prop)
                elif score >= 7:
                    score_bins['7-8'].append(prop)
                elif score >= 5:
                    score_bins['5-6'].append(prop)
                elif score >= 3:
                    score_bins['3-4'].append(prop)
                else:
                    score_bins['1-2'].append(prop)
            
            return render_template('index.html', 
                                 properties=results, 
                                 score_bins=score_bins, 
                                 sort_by=sort_by,
                                 view_mode=view_mode,
                                 score_category=score_category,
                                 score_categories=get_score_categories())
        else:
            # Default sort by display_index
            results.sort(key=lambda x: x.get('display_index', 0))
            return render_template('index.html', 
                                 properties=results, 
                                 sort_by=sort_by,
                                 view_mode=view_mode,
                                 score_category=score_category,
                                 score_categories=get_score_categories())

def render_image_gallery(results, score_category):
    """Render images grouped by score for a specific category"""
    # Collect all images for the specified category
    category_images = []
    
    for result in results:
        structured = result.get("structured_analysis", {})
        tagged_images = result.get("tagged_images", {})
        
        score = get_score_from_structured(structured, score_category)
        if score is None:
            continue
            
        # Map score category to image category
        image_category_map = {
            'kitchen_quality': 'kitchen_images',
            'bathroom_quality': 'bathroom_images',
            'living_space_quality': 'living_space_images',
            'building_quality': 'building_images'
        }
        
        image_category = image_category_map.get(score_category, 'all_images')
        images = tagged_images.get(image_category, [])
        
        # If no specific images, fall back to all images for this property
        if not images and score is not None:
            all_images = tagged_images.get('all_images', [])
            images = all_images[:3]  # Take first 3 as representative
        
        for img in images:
            category_images.append({
                'url': img.get('url'),
                'score': score,
                'property_id': result.get('display_index'),
                'property_type': get_property_details(result).get('property_type'),
                'gpt_identified': img.get('gpt_identified', False)
            })
    
    # Group images by score bins
    image_bins = {
        '9-10': [],
        '7-8': [],
        '5-6': [],
        '3-4': [],
        '1-2': []
    }
    
    for img in category_images:
        score = img['score']
        if score >= 9:
            image_bins['9-10'].append(img)
        elif score >= 7:
            image_bins['7-8'].append(img)
        elif score >= 5:
            image_bins['5-6'].append(img)
        elif score >= 3:
            image_bins['3-4'].append(img)
        else:
            image_bins['1-2'].append(img)
    
    return render_template('image_gallery.html',
                         image_bins=image_bins,
                         score_category=score_category,
                         score_categories=get_score_categories())

def get_score_categories():
    """Get list of available score categories"""
    return {
        'kitchen_quality': 'Kitchen Quality',
        'bathroom_quality': 'Bathroom Quality', 
        'natural_light': 'Natural Light',
        'overall_condition': 'Overall Condition',
        'living_space_quality': 'Living Space Quality',
        'size_space': 'Size/Space',
        'building_quality': 'Building Quality'
    }

@app.route('/property/<int:property_id>')
def property_detail(property_id):
    """Detailed view of a specific property by display_index"""
    results = load_rolling_file()
    
    # Find the property by display_index
    property_data = None
    for result in results:
        if result.get('display_index') == property_id:
            property_data = result
            break
    
    if not property_data:
        return "Property not found", 404
    
    # Add parsed data
    property_data['property_details'] = get_property_details(property_data)
    property_data['amenities'] = get_amenities(property_data)
    
    structured = property_data.get("structured_analysis", {})
    if structured:
        property_data['scores'] = structured.get("scores", {})
        property_data['tagged_images'] = property_data.get("tagged_images", {})
    else:
        property_data['scores'] = {}
        property_data['tagged_images'] = {}
    
    return render_template('property_detail.html', 
                         property=property_data,
                         score_categories=get_score_categories())

@app.route('/api/properties')
def api_properties():
    """API endpoint for property data with filtering"""
    results = load_rolling_file()
    
    # Get filter parameters
    min_score = request.args.get('min_score', type=float)
    max_score = request.args.get('max_score', type=float)
    score_category = request.args.get('score_category', 'kitchen_quality')
    property_type = request.args.get('property_type')
    is_furnished = request.args.get('is_furnished')
    has_outdoor_space = request.args.get('has_outdoor_space')
    min_sqft = request.args.get('min_sqft', type=int)
    max_sqft = request.args.get('max_sqft', type=int)
    amenity = request.args.get('amenity')
    
    # Apply filters
    filtered_results = []
    for result in results:
        # Add parsed data
        result['property_details'] = get_property_details(result)
        result['amenities'] = get_amenities(result)
        
        structured = result.get("structured_analysis", {})
        if structured:
            result['scores'] = structured.get("scores", {})
        else:
            result['scores'] = {}
        
        # Apply score filters
        if min_score is not None or max_score is not None:
            score = get_score_from_structured(structured, score_category)
            if score is None:
                continue
            if min_score is not None and score < min_score:
                continue
            if max_score is not None and score > max_score:
                continue
        
        # Apply property detail filters
        details = result['property_details']
        
        if property_type and details.get('property_type') != property_type:
            continue
        
        if is_furnished is not None:
            furnished_filter = is_furnished.lower() == 'true'
            if details.get('is_furnished', False) != furnished_filter:
                continue
        
        if has_outdoor_space is not None:
            outdoor_filter = has_outdoor_space.lower() == 'true'
            if details.get('outdoor_space', False) != outdoor_filter:
                continue
        
        if min_sqft is not None:
            sqft = details.get('estimated_sqft')
            if sqft is None or sqft < min_sqft:
                continue
        
        if max_sqft is not None:
            sqft = details.get('estimated_sqft')
            if sqft is None or sqft > max_sqft:
                continue
        
        if amenity:
            property_amenities = [a.lower() for a in result['amenities']]
            if amenity.lower() not in property_amenities:
                continue
        
        filtered_results.append(result)
    
    # Sort results
    sort_by = request.args.get('sort_by', 'display_index')
    sort_order = request.args.get('sort_order', 'asc')
    
    if sort_by in ['kitchen_quality', 'bathroom_quality', 'natural_light', 'overall_condition', 
                   'living_space_quality', 'size_space', 'building_quality']:
        # Sort by score
        filtered_results.sort(
            key=lambda x: get_score_from_structured(x.get("structured_analysis"), sort_by) or 0,
            reverse=(sort_order == 'desc')
        )
    elif sort_by == 'estimated_sqft':
        filtered_results.sort(
            key=lambda x: x['property_details'].get('estimated_sqft') or 0,
            reverse=(sort_order == 'desc')
        )
    else:
        # Default sort by display_index
        filtered_results.sort(
            key=lambda x: x.get('display_index', 0),
            reverse=(sort_order == 'desc')
        )
    
    return jsonify({
        'properties': filtered_results,
        'total_count': len(filtered_results),
        'filters_applied': {
            'min_score': min_score,
            'max_score': max_score,
            'score_category': score_category,
            'property_type': property_type,
            'is_furnished': is_furnished,
            'has_outdoor_space': has_outdoor_space,
            'min_sqft': min_sqft,
            'max_sqft': max_sqft,
            'amenity': amenity,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    })

@app.route('/api/images/category/<category>')
def api_images_by_category(category):
    """API endpoint to get all images for a specific category"""
    results = load_rolling_file()
    
    # Get score filters
    min_score = request.args.get('min_score', type=float)
    max_score = request.args.get('max_score', type=float)
    score_category = request.args.get('score_category', category.replace('_images', '') + '_quality')
    
    category_images = []
    
    for result in results:
        structured = result.get("structured_analysis", {})
        tagged_images = result.get("tagged_images", {})
        
        # Apply score filter if specified
        if min_score is not None or max_score is not None:
            score = get_score_from_structured(structured, score_category)
            if score is None:
                continue
            if min_score is not None and score < min_score:
                continue
            if max_score is not None and score > max_score:
                continue
        
        # Get images for this category
        images = tagged_images.get(category, [])
        for img in images:
            category_images.append({
                'url': img.get('url'),
                'index': img.get('index'),
                'property_id': result.get('display_index'),
                'property_score': get_score_from_structured(structured, score_category),
                'property_type': get_property_details(result).get('property_type')
            })
    
    # Sort by score if available
    category_images.sort(key=lambda x: x.get('property_score') or 0, reverse=True)
    
    return jsonify({
        'category': category,
        'images': category_images,
        'total_count': len(category_images),
        'score_category': score_category
    })

@app.route('/api/stats')
def api_stats():
    """API endpoint for analysis statistics"""
    results = load_rolling_file()
    
    if not results:
        return jsonify({'error': 'No data available'})
    
    stats = {
        'total_properties': len(results),
        'total_images': sum(r.get('images_analyzed', 0) for r in results),
        'avg_images_per_property': 0,
        'latest_analysis': None,
        'score_averages': {},
        'score_distributions': {},
        'property_type_distribution': {},
        'amenity_frequency': {},
        'furnished_count': 0,
        'outdoor_space_count': 0,
        'avg_sqft': 0
    }
    
    if stats['total_properties'] > 0:
        stats['avg_images_per_property'] = round(stats['total_images'] / stats['total_properties'], 1)
    
    # Get latest timestamp
    timestamps = [r.get('timestamp') for r in results if r.get('timestamp')]
    if timestamps:
        stats['latest_analysis'] = max(timestamps)
    
    # Calculate statistics from structured data
    all_scores = {}
    property_types = {}
    amenities = {}
    sqfts = []
    furnished_count = 0
    outdoor_count = 0
    
    for result in results:
        structured = result.get("structured_analysis", {})
        
        if structured:
            # Collect scores
            scores = structured.get("scores", {})
            for score_name, score_value in scores.items():
                if score_value is not None:
                    if score_name not in all_scores:
                        all_scores[score_name] = []
                    all_scores[score_name].append(score_value)
            
            # Property details
            details = structured.get("property_details", {})
            prop_type = details.get("property_type")
            if prop_type:
                property_types[prop_type] = property_types.get(prop_type, 0) + 1
            
            if details.get("is_furnished"):
                furnished_count += 1
            
            if details.get("outdoor_space"):
                outdoor_count += 1
            
            sqft = details.get("estimated_sqft")
            if sqft:
                sqfts.append(sqft)
            
            # Amenities
            for amenity in structured.get("amenities", []):
                amenities[amenity] = amenities.get(amenity, 0) + 1
    
    # Calculate score averages and distributions
    for score_name, values in all_scores.items():
        if values:
            stats['score_averages'][score_name] = round(sum(values) / len(values), 1)
            
            # Create score distribution (1-2, 3-4, 5-6, 7-8, 9-10)
            distribution = {'1-2': 0, '3-4': 0, '5-6': 0, '7-8': 0, '9-10': 0}
            for score in values:
                if score <= 2:
                    distribution['1-2'] += 1
                elif score <= 4:
                    distribution['3-4'] += 1
                elif score <= 6:
                    distribution['5-6'] += 1
                elif score <= 8:
                    distribution['7-8'] += 1
                else:
                    distribution['9-10'] += 1
            
            stats['score_distributions'][score_name] = distribution
    
    stats['property_type_distribution'] = property_types
    stats['amenity_frequency'] = dict(sorted(amenities.items(), key=lambda x: x[1], reverse=True)[:20])  # Top 20
    stats['furnished_count'] = furnished_count
    stats['outdoor_space_count'] = outdoor_count
    
    if sqfts:
        stats['avg_sqft'] = round(sum(sqfts) / len(sqfts))
        stats['min_sqft'] = min(sqfts)
        stats['max_sqft'] = max(sqfts)
    
    return jsonify(stats)

@app.route('/debug')
def debug():
    """Debug page to see rolling file status"""
    try:
        with open(ROLLING_FILE, 'r') as f:
            all_data = json.load(f)
        
        # Analyze the data
        total_entries = len(all_data)
        successful_entries = len([d for d in all_data if d.get('success', False)])
        refusal_entries = len([d for d in all_data if d.get('refusal', False)])
        structured_entries = len([d for d in all_data if d.get('structured_analysis')])
        valid_analyses = len([d for d in all_data if is_valid_analysis(d)])
        
        # Get unique original indices
        original_indices = set()
        for entry in all_data:
            if entry.get('original_property_index') is not None:
                original_indices.add(entry['original_property_index'])
        
        file_info = {
            'filename': ROLLING_FILE,
            'exists': True,
            'size': os.path.getsize(ROLLING_FILE),
            'modified': datetime.fromtimestamp(os.path.getmtime(ROLLING_FILE)).isoformat(),
            'total_entries': total_entries,
            'successful_entries': successful_entries,
            'refusal_entries': refusal_entries,
            'structured_entries': structured_entries,
            'valid_analyses': valid_analyses,
            'unique_properties_covered': len(original_indices),
            'latest_timestamp': max([d.get('timestamp', '') for d in all_data]) if all_data else None
        }
        
    except FileNotFoundError:
        file_info = {
            'filename': ROLLING_FILE,
            'exists': False,
            'error': 'File not found'
        }
    except Exception as e:
        file_info = {
            'filename': ROLLING_FILE,
            'exists': True,
            'error': str(e)
        }
    
    return jsonify({
        'rolling_file_info': file_info,
        'current_working_directory': os.getcwd(),
        'app_loads': len(load_rolling_file()),
        'validation_info': {
            'new_structured_format_support': True,
            'legacy_format_support': True,
            'validation_checks': [
                "Structured analysis presence",
                "Score validation (min 3 categories)",
                "Legacy text analysis fallback",
                "Error message detection"
            ]
        }
    })

@app.route('/validate')
def validate_analyses():
    """Endpoint to validate all analyses in the rolling file"""
    try:
        with open(ROLLING_FILE, 'r') as f:
            results = json.load(f)
    except FileNotFoundError:
        return jsonify({'error': f'Rolling file {ROLLING_FILE} not found'})
    
    validation_results = []
    for i, result in enumerate(results):
        is_valid = is_valid_analysis(result)
        
        structured = result.get("structured_analysis", {})
        has_structured = bool(structured)
        score_count = len([v for v in structured.get("scores", {}).values() if v is not None]) if structured else 0
        
        validation_results.append({
            'entry_index': i,
            'display_index': result.get('display_index'),
            'original_property_index': result.get('original_property_index'),
            'success_flag': result.get('success', False),
            'refusal_flag': result.get('refusal', False),
            'has_structured_analysis': has_structured,
            'structured_score_count': score_count,
            'is_valid_analysis': is_valid,
            'analysis_method': result.get('analysis_method', 'unknown'),
            'timestamp': result.get('timestamp')
        })
    
    valid_count = len([r for r in validation_results if r['is_valid_analysis']])
    structured_count = len([r for r in validation_results if r['has_structured_analysis']])
    
    return jsonify({
        'total_entries': len(results),
        'valid_analyses': valid_count,
        'structured_analyses': structured_count,
        'success_entries': len([r for r in validation_results if r['success_flag']]),
        'refusal_entries': len([r for r in validation_results if r['refusal_flag']]),
        'entries': validation_results
    })

if __name__ == '__main__':
    print("Starting Flask app with Structured Analysis Support...")
    print("Available endpoints:")
    print("- / : Main property listing with filtering")
    print("- /property/<property_id> : Individual property details with tagged images")
    print("- /api/properties : JSON API with filtering and sorting")
    print("- /api/images/category/<category> : Images by category with score filtering")
    print("- /api/stats : Comprehensive analysis statistics")
    print("- /debug : Debug information about rolling file")
    print("- /validate : Validate all analyses in rolling file")
    print(f"- Rolling file: {ROLLING_FILE}")
    print("\nNew features:")
    print("- Structured score filtering and sorting")
    print("- Image category browsing")
    print("- Property detail filtering")
    print("- Amenity-based filtering")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)