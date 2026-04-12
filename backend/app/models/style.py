"""
Style/mood classifier for images
"""

def classify_style(image):
    """
    Classify the style and mood of an image
    
    In a real implementation, this would use a pre-trained model
    specifically trained to recognize photographic styles and moods
    
    For this example, we'll return mock styles and moods
    """
    # Mock implementation
    import random
    
    # Common photographic styles
    styles = [
        "Minimalist", "Vibrant", "Monochrome", "Vintage", "HDR", 
        "Documentary", "Abstract", "Long Exposure", "Macro", 
        "Portrait", "Landscape", "Street", "Architectural"
    ]
    
    # Common moods in photography
    moods = [
        "Calm", "Energetic", "Melancholic", "Joyful", "Mysterious",
        "Dramatic", "Peaceful", "Tense", "Romantic", "Nostalgic",
        "Hopeful", "Gloomy", "Serene", "Chaotic"
    ]
    
    # Randomly select a style and mood
    style = random.choice(styles)
    mood = random.choice(moods)
    
    return style, mood
