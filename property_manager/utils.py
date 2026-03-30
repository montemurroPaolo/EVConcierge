def geocode_address(address):
    """
    Geocode an address to get latitude and longitude coordinates
    Returns a tuple of (latitude, longitude) or (None, None) if geocoding fails
    """
    if not address:
        return None, None
        
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderServiceError, GeocoderTimedOut
        
        # Create a geocoder with a better user agent
        geolocator = Nominatim(user_agent="efisio_geocoder/1.0")
        
        # Add a timeout to avoid hanging
        location = geolocator.geocode(address, timeout=5)
        
        if location:
            return location.latitude, location.longitude
        else:
            print(f"No results found for address: {address}")
            return None, None
            
    except (GeocoderServiceError, GeocoderTimedOut) as e:
        print(f"Error geocoding address: {str(e)}")
        return None, None
    except Exception as e:
        print(f"Error geocoding address: {str(e)}")
        return None, None 

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points
    on the earth (specified in decimal degrees).
    Returns distance in kilometers.
    """
    from math import radians, cos, sin, asin, sqrt
    
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    
    # Calculate distance
    distance = round(c * r, 2)  # Round to 2 decimal places
    
    return distance 

def get_plan_limits(subscription_plan):
    """Return the property and experience limits for a subscription plan"""
    limits = {
        'free': {'properties': 1, 'experiences': 1},
        'casual_renter': {'properties': 5, 'experiences': 5},
        'property_manager': {'properties': 20, 'experiences': 20},
        'big_boss': {'properties': 100, 'experiences': 100},
    }
    
    return limits.get(subscription_plan, limits['free'])

def check_plan_limits(user, item_type):
    """
    Check if a user has reached their plan limits for properties or experiences
    
    Args:
        user: The user to check
        item_type: Either 'property' or 'experience'
        
    Returns:
        tuple: (has_reached_limit, current_count, max_allowed)
    """
    if not hasattr(user, 'profile'):
        from .models import UserProfile
        UserProfile.objects.create(user=user)
    
    subscription_plan = user.profile.subscription_plan
    limits = get_plan_limits(subscription_plan)
    
    if item_type == 'property':
        current_count = user.properties.filter(is_active=True).count()
        max_allowed = limits['properties']
    elif item_type == 'experience':
        current_count = user.experiences.filter(is_active=True).count()
        max_allowed = limits['experiences']
    else:
        raise ValueError(f"Invalid item_type: {item_type}. Must be 'property' or 'experience'")
    
    # If max_allowed is infinity (for 'big_boss' plan), user hasn't reached limit
    if max_allowed == float('inf'):
        return False, current_count, "unlimited"
    
    return current_count >= max_allowed, current_count, max_allowed

def update_items_visibility(user):
    """
    Update visibility of properties and experiences based on the user's subscription plan
    
    This function is called when a user changes their subscription plan.
    It will hide excess properties and experiences if the user downgrades their plan
    and unhide them if the user upgrades.
    
    Args:
        user: The user to update items for
    """
    from .models import Property, Experience
    
    subscription_plan = user.profile.subscription_plan
    limits = get_plan_limits(subscription_plan)
    
    # Get the property limit for this plan
    property_limit = limits['properties']
    
    # Handle properties visibility
    # Get all user properties ordered by creation date (oldest first)
    all_properties = Property.objects.filter(owner=user).order_by('created_at')
    
    # Make the properties within the limit active
    active_count = 0
    inactive_count = 0
    for i, prop in enumerate(all_properties):
        if i < property_limit:
            if not prop.is_active:
                prop.is_active = True
                prop.save()
                active_count += 1
        else:
            if prop.is_active:
                prop.is_active = False
                prop.save()
                inactive_count += 1
    
    print(f"Updated property visibility for user {user.username}: activated {active_count}, deactivated {inactive_count}")
    
    # Get the experience limit for this plan
    experience_limit = limits['experiences']
    
    # Handle experiences visibility
    # Get all user experiences ordered by creation date (oldest first)
    all_experiences = Experience.objects.filter(owner=user).order_by('created_at')
    
    # Make the experiences within the limit active
    active_count = 0
    inactive_count = 0
    for i, exp in enumerate(all_experiences):
        if i < experience_limit:
            if not exp.is_active:
                exp.is_active = True
                exp.save()
                active_count += 1
        else:
            if exp.is_active:
                exp.is_active = False
                exp.save()
                inactive_count += 1
    
    print(f"Updated experience visibility for user {user.username}: activated {active_count}, deactivated {inactive_count}")

def get_facebook_pixel_config():
    """Get Facebook Pixel configuration from settings"""
    from django.conf import settings
    return getattr(settings, 'FACEBOOK_PIXEL', {})

def should_track_facebook_pixel():
    """Check if Facebook Pixel tracking is enabled"""
    config = get_facebook_pixel_config()
    return config.get('ENABLED', False) and config.get('PIXEL_ID', '')

def get_plan_value_for_tracking(plan_name):
    """Get the plan value for Facebook Pixel tracking"""
    plan_values = {
        'casual_renter': 199,
        'property_manager': 399,
        'big_boss': 999,
        'free': 0
    }
    return plan_values.get(plan_name, 0)

def prepare_purchase_tracking_data(user, plan_name, is_trial=False):
    """Prepare purchase tracking data for Facebook Pixel"""
    if not should_track_facebook_pixel():
        return None
    
    value = get_plan_value_for_tracking(plan_name)
    property_count = user.properties.count() if hasattr(user, 'properties') else 0
    
    return {
        'value': value,
        'currency': 'EUR',
        'subscription_plan': plan_name,
        'subscription_type': 'annual',
        'trial_period': 14 if is_trial else 0,
        'user_properties_count': property_count
    }

def prepare_content_tracking_data(content_type, content_id, content_name, content_category=None, value=None):
    """Prepare content view tracking data for Facebook Pixel"""
    if not should_track_facebook_pixel():
        return None
    
    return {
        'content_type': content_type,
        'content_ids': [str(content_id)],
        'content_name': content_name,
        'content_category': content_category or '',
        'value': value or 0,
        'currency': 'EUR'
    } 

def compress_image(image_path, max_size_kb=300, quality=85):
    """
    Compress an image if it exceeds the specified maximum size.
    
    Args:
        image_path: Path to the image file
        max_size_kb: Maximum file size in kilobytes
        quality: JPEG compression quality (1-100)
        
    Returns:
        bool: True if image was compressed, False otherwise
    """
    from PIL import Image, UnidentifiedImageError
    import os
    import math
    
    # Check if file exists and get its size
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return False
        
    # Get file size in KB
    file_size_kb = os.path.getsize(image_path) / 1024
    
    # If file is already smaller than max_size_kb, no need to compress
    if file_size_kb <= max_size_kb:
        print(f"Skipping {image_path} - already under {max_size_kb}KB ({file_size_kb:.1f}KB)")
        return False
    
    # Declare temp_path outside try block so it's available in the except block
    temp_path = f"{image_path}.temp"
    
    try:
        # Open the image
        print(f"Opening image: {image_path}")
        img = Image.open(image_path)
        
        # Print image details for debugging
        print(f"Image details: Format={img.format}, Mode={img.mode}, Size={img.size}")
        
        # Get original format (defaulting to JPEG if unknown)
        img_format = img.format
        if img_format is None:
            print(f"Warning: Could not determine image format for {image_path}, defaulting to JPEG")
            img_format = 'JPEG'
        
        # Try multiple quality settings if needed
        current_quality = quality
        
        # Safely get EXIF data if present
        exif_data = None
        try:
            if 'exif' in img.info:
                exif_data = img.info['exif']
                print(f"EXIF data present in {image_path}, length: {len(exif_data) if exif_data else 0}")
        except Exception as exif_err:
            print(f"Warning: Error reading EXIF data from {image_path}: {str(exif_err)}")
        
        # Prepare save parameters based on format
        save_kwargs = {
            'format': img_format,
            'optimize': True
        }
        
        # Add quality parameter for JPEG and similar formats
        if img_format in ['JPEG', 'JPG']:
            save_kwargs['quality'] = current_quality
        
        # Add exif data only if it's actually available
        if exif_data:
            save_kwargs['exif'] = exif_data
        
        print(f"Saving with parameters: {save_kwargs}")
        
        # First attempt: just reduce quality
        img.save(temp_path, **save_kwargs)
        
        # Check if we reached target size
        temp_size_kb = os.path.getsize(temp_path) / 1024
        
        # If still too big, try reducing dimensions
        if temp_size_kb > max_size_kb:
            # Calculate new dimensions while maintaining aspect ratio
            width, height = img.size
            ratio = min(1.0, math.sqrt(max_size_kb / file_size_kb))
            
            # Resize image with high-quality resampling
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            print(f"Resizing from {width}x{height} to {new_width}x{new_height}")
            
            try:
                img = img.resize((new_width, new_height), Image.LANCZOS)
            except Exception as resize_err:
                print(f"Error during resize: {str(resize_err)}, trying BICUBIC instead")
                # Fall back to a simpler resampling method
                img = img.resize((new_width, new_height), Image.BICUBIC)
            
            # Save again with reduced dimensions
            img.save(temp_path, **save_kwargs)
            
            temp_size_kb = os.path.getsize(temp_path) / 1024
        
        # If successful, replace the original file
        if temp_size_kb < file_size_kb:
            os.replace(temp_path, image_path)
            compression_ratio = (1 - temp_size_kb / file_size_kb) * 100
            print(f"Compressed {image_path}: {file_size_kb:.1f}KB → {temp_size_kb:.1f}KB ({compression_ratio:.1f}% reduction)")
            return True
        else:
            # If compression didn't reduce size, discard temp file
            os.remove(temp_path)
            print(f"Could not compress {image_path} effectively")
            return False
            
    except UnidentifiedImageError as uie:
        print(f"Error: Cannot identify image file {image_path}: {str(uie)}")
        # This is likely not a valid image file or it's corrupted
        return False
        
    except OSError as ose:
        print(f"OS Error while processing {image_path}: {str(ose)}")
        # This could be due to file permissions, disk space, etc.
        return False
        
    except ValueError as ve:
        print(f"Value Error while processing {image_path}: {str(ve)}")
        # This could be due to invalid parameters
        return False
        
    except Exception as e:
        print(f"Unexpected error compressing {image_path}: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_err:
                print(f"Error cleaning up temp file {temp_path}: {str(cleanup_err)}")

def get_container_info(instance):
    """
    Get the container object and type for an image instance
    
    Args:
        instance: Image model instance (PropertyImage, ExperienceImage, etc.)
        
    Returns:
        tuple: (container_object, container_type) or (None, None) if not found
    """
    try:
        if hasattr(instance, 'property'):
            return instance.property, 'property'
        elif hasattr(instance, 'experience'):
            return instance.experience, 'experience'
        elif hasattr(instance, 'instruction'):
            return instance.instruction, 'instruction'
        else:
            return None, None
    except Exception:
        return None, None

def get_container_field_name(model_class):
    """
    Get the container field name for an image model class
    
    Args:
        model_class: The image model class (PropertyImage, ExperienceImage, etc.)
        
    Returns:
        str: Field name or None if not found
    """
    class_name = model_class.__name__.lower()
    
    if 'property' in class_name:
        return 'property'
    elif 'experience' in class_name:
        return 'experience'
    elif 'instruction' in class_name:
        return 'instruction'
    else:
        return None

def detect_and_remove_duplicate_images(instance, created, image_field_name='image'):
    """
    Detect and remove duplicate images within the same container (property, experience, etc.)
    This function is called automatically when new images are uploaded via Django signals.
    
    Args:
        instance: The image model instance (PropertyImage, ExperienceImage, etc.)
        created: Boolean indicating if this is a new instance
        image_field_name: Name of the image field (default: 'image')
        
    Returns:
        bool: True if duplicate was found and removed, False otherwise
    """
    import os
    import logging
    from django.core.files.storage import default_storage
    
    # Get logger for duplicate detection
    logger = logging.getLogger('duplicate_detection')
    
    # Simple logging
    print(f"🔍 Duplicate detection started for {type(instance).__name__} ID={instance.id}")
    logger.info(f"🔍 Duplicate detection started for {type(instance).__name__} ID={instance.id}")
    
    try:
        # Get the image field
        image_field = getattr(instance, image_field_name)
        if not image_field:
            message = f"⚠️  No image found on {image_field_name} field"
            print(message)
            logger.warning(message)
            return False
    
        # Get the image path
        if hasattr(image_field, 'path'):
            image_path = image_field.path
        else:
            image_path = default_storage.path(image_field.name)
            
        if not os.path.exists(image_path):
            message = f"⚠️  Image file not found: {image_path}"
            print(message)
            logger.warning(message)
            return False
            
        message = f"📁 Processing image: {os.path.basename(image_path)}"
        print(message)
        logger.info(message)
        
        # Calculate hash for the new image
        new_hash = calculate_image_hash(image_path, hash_algorithm='perceptual')
        if not new_hash:
            message = f"❌ Failed to calculate hash"
            print(message)
            logger.error(message)
            return False
            
        message = f"🔢 Hash calculated: {new_hash[:12]}..."
        print(message)
        logger.info(message)
        
        # Get container object and type
        container_obj, container_type = get_container_info(instance)
        if not container_obj:
            message = f"⚠️  No container found"
            print(message)
            logger.warning(message)
            return False
            
        message = f"📦 Container: {container_type} ID={container_obj.id}"
        print(message)
        logger.info(message)
        
        # Find all images in the same container
        model_class = type(instance)
        container_field = get_container_field_name(model_class)
        
        if not container_field:
            message = f"⚠️  No container field found"
            print(message)
            logger.warning(message)
            return False
            
        # Get all other images in the same container (excluding current instance)
        other_images = model_class.objects.filter(
            **{container_field: container_obj}
        ).exclude(id=instance.id)
        
        message = f"🔍 Checking against {other_images.count()} existing images"
        print(message)
        logger.info(message)
        
        duplicates_found = 0
        for other_image in other_images:
            other_image_field = getattr(other_image, image_field_name)
            if not other_image_field:
                continue
                
            # Get other image path
            if hasattr(other_image_field, 'path'):
                other_path = other_image_field.path
            else:
                other_path = default_storage.path(other_image_field.name)
                    
            if not os.path.exists(other_path):
                continue
                    
            # Calculate hash for existing image
            other_hash = calculate_image_hash(other_path, hash_algorithm='perceptual')
            if not other_hash:
                continue
                    
            # Compare hashes
            if new_hash == other_hash:
                message = f"🎯 DUPLICATE FOUND! Removing {type(instance).__name__} ID={other_image.id}"
                print(message)
                logger.warning(message)
                try:
                    # Delete the file
                    if os.path.exists(other_path):
                        os.remove(other_path)
                    # Delete the database record
                    other_image.delete()
                    duplicates_found += 1
                except Exception as e:
                    error_msg = f"❌ Error removing duplicate: {e}"
                    print(error_msg)
                    logger.error(error_msg)
                    
        if duplicates_found > 0:
            message = f"✅ Removed {duplicates_found} duplicate(s)"
            print(message)
            logger.info(message)
            return True
        else:
            message = f"✅ No duplicates found"
            print(message)
            logger.info(message)
            return False
        
    except Exception as e:
        error_msg = f"❌ Error in duplicate detection: {e}"
        print(error_msg)
        logger.error(error_msg)
        return False

def calculate_image_hash(image_path, hash_algorithm='md5'):
    """
    Calculate hash of an image file
    
    Args:
        image_path: Path to the image file
        hash_algorithm: Algorithm to use ('md5', 'sha256', or 'perceptual')
        
    Returns:
        str: Hash string, or None if error
    """
    import hashlib
    import os
    
    try:
        if not os.path.exists(image_path):
            return None
            
        if hash_algorithm == 'perceptual':
            # Use perceptual hashing for better duplicate detection
            return calculate_perceptual_hash(image_path)
        else:
            # Use file-based hashing (MD5 or SHA256)
            hash_func = hashlib.md5() if hash_algorithm == 'md5' else hashlib.sha256()
            
            with open(image_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)
                    
            result = hash_func.hexdigest()
            print(f"    🔢 Hash: {result[:12]}... ({hash_algorithm})")
            return result
            
    except Exception as e:
        print(f"    ❌ Hash calculation failed: {e}")
        return None

def calculate_perceptual_hash(image_path):
    """
    Calculate perceptual hash to detect similar images (not just exact duplicates)
    This can detect images that are the same but compressed differently, resized, etc.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        str: Perceptual hash string, or None if error
    """
    try:
        from PIL import Image
        import hashlib
        
        # Open and standardize the image
        with Image.open(image_path) as img:
            # Convert to grayscale
            img = img.convert('L')
            
            # Resize to 8x8 for simplicity (reduces to 64 pixels)
            img = img.resize((8, 8), Image.LANCZOS)
            
            # Get pixel values
            pixels = list(img.getdata())
            
            # Calculate average pixel value
            avg = sum(pixels) / len(pixels)
            
            # Create hash based on pixels above/below average
            hash_bits = ['1' if pixel > avg else '0' for pixel in pixels]
            hash_string = ''.join(hash_bits)
            
            # Convert binary string to hex
            hash_hex = hex(int(hash_string, 2))[2:].zfill(16)
            
            return hash_hex
            
    except Exception as e:
        print(f"Error calculating perceptual hash for {image_path}: {str(e)}")
        return None

def find_all_duplicates_in_container(container_obj, container_type, hash_algorithm='md5'):
    """
    Find all duplicate images within a container (property, experience, etc.)
    
    Args:
        container_obj: The container object (Property, Experience, etc.)
        container_type: Type of container ('property', 'experience', 'instruction', 'blog')
        hash_algorithm: Algorithm to use ('md5', 'sha256', or 'perceptual')
        
    Returns:
        list: List of duplicate groups [(original_image, [duplicate_images]), ...]
    """
    import os
    from django.core.files.storage import default_storage
    
    # Get all images for the container
    if container_type == 'property':
        images = container_obj.images.all()
    elif container_type == 'experience':
        images = container_obj.images.all()
    elif container_type == 'instruction':
        images = container_obj.images.all()
    elif container_type == 'blog':
        images = container_obj.images.all()
    else:
        print(f"Unknown container type: {container_type}")
        return []
    
    if not images.exists():
        return []
    
    # Calculate hashes for all images
    image_hashes = {}
    hash_to_images = {}
    
    for image in images:
        try:
            image_field = image.image
            if not image_field:
                continue
                
            if hasattr(image_field, 'path'):
                image_path = image_field.path
            else:
                image_path = default_storage.path(image_field.name)
                
            if not os.path.exists(image_path):
                continue
                
            image_hash = calculate_image_hash(image_path, hash_algorithm)
            if image_hash:
                image_hashes[image.id] = image_hash
                
                if image_hash not in hash_to_images:
                    hash_to_images[image_hash] = []
                hash_to_images[image_hash].append(image)
                
        except Exception as e:
            print(f"Error processing image {image.id}: {str(e)}")
            continue
    
    # Find duplicates (groups with more than one image)
    duplicate_groups = []
    for image_hash, images_list in hash_to_images.items():
        if len(images_list) > 1:
            # Sort by creation date (keep oldest, mark others as duplicates)
            images_list.sort(key=lambda x: x.created_at)
            original = images_list[0]
            duplicates = images_list[1:]
            duplicate_groups.append((original, duplicates))
    
    return duplicate_groups

def generate_ai_summary(property_data, item_type):
    """
    Generate an AI summary of the given property/experience using AI service with fallback
    
    Args:
        property_data: JSON data containing all property/experience information (without sensitive info)
        item_type: Either 'property' or 'experience'
        
    Returns:
        str: The generated summary, or empty string if generation fails
    """
    import time
    import json
    from .ai_service import get_ai_completion
    
    # Skip if data is empty
    if not property_data:
        return ""
    
    try:
        # Create appropriate prompt based on item type
        if item_type == 'property':
            # Create a detailed prompt with all property information
            prompt = f"""Please create a complete and engaging 4-line summary for this property listing. 
The summary should be exactly 4 lines long, with each line being a complete thought.
Focus on the most appealing aspects including location, amenities, and unique features.
Ensure the summary is well-structured and comprehensive. Do not use ellipsis or truncate the summary.

IMPORTANT: If you don't know something and you can't get this information from the provided data, don't invent details. Instead, suggest that guests contact the property manager for more specific information (both in chat with and without password access).

Property details:
{json.dumps(property_data, indent=2)}"""
        elif item_type == 'experience':
            # Create a detailed prompt with all experience information
            prompt = f"""Please create a complete and engaging 4-line summary for this experience.
The summary should be exactly 4 lines long, with each line being a complete thought.
Focus on what makes it special, what activities are involved, and what visitors can expect.
Ensure the summary is well-structured and comprehensive. Do not use ellipsis or truncate the summary.

IMPORTANT: If you don't know something and you can't get this information from the provided data, don't invent details. Instead, suggest that guests contact the property manager for more specific information (both in chat with and without password access).

Experience details:
{json.dumps(property_data, indent=2)}"""
        else:
            prompt = f"Please create a concise summary of this text in exactly 4 lines. The summary should be complete and well-structured with each line being a complete thought.\n\nText: {property_data}"
        
        # Make the API request with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = get_ai_completion(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that creates concise, engaging summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.7,
                    model="gpt-3.5-turbo"
                )
                
                # Extract the summary from the response
                summary = response['content'].strip()
                model_info = f"{response['model_used']} ({response.get('model_name', 'unknown')})"
                print(f"AI summary generated using: {model_info}")
                
                # Return the complete summary without truncation
                return summary
                
            except Exception as e:
                print(f"Error generating AI summary (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    # Wait a bit before retrying
                    time.sleep(2 * (attempt + 1))
                
        # If we've reached here, all attempts failed
        return ""
        
    except Exception as e:
        print(f"Error generating AI summary: {str(e)}")
        return "" 