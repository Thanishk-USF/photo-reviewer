"""
Utility functions for image processing
"""
from PIL import Image
import numpy as np
import io

def preprocess_image(image_path, target_size=(224, 224)):
    """
    Preprocess an image for ML models
    
    Args:
        image_path: Path to the image file
        target_size: Target size for resizing
        
    Returns:
        Preprocessed image as a PIL Image object
    """
    # Open the image
    img = Image.open(image_path)
    
    # Convert to RGB if needed
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Resize the image
    img = img.resize(target_size, Image.LANCZOS)
    
    return img

def save_image(img, output_path, size=None):
    """
    Save an image to disk
    
    Args:
        img: PIL Image object
        output_path: Path to save the image
        size: Optional size to resize the image
    """
    # Create a copy of the image
    output_img = img.copy()
    
    # Resize if needed
    if size:
        output_img = output_img.resize(size, Image.LANCZOS)
    
    # Save the image
    output_img.save(output_path)

def image_to_bytes(img, format='JPEG'):
    """
    Convert a PIL Image to bytes
    
    Args:
        img: PIL Image object
        format: Image format (JPEG, PNG, etc.)
        
    Returns:
        Image as bytes
    """
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format=format)
    return img_byte_arr.getvalue()

def bytes_to_image(img_bytes):
    """
    Convert bytes to a PIL Image
    
    Args:
        img_bytes: Image as bytes
        
    Returns:
        PIL Image object
    """
    return Image.open(io.BytesIO(img_bytes))
