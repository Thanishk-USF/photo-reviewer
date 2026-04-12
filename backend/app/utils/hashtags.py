"""
Utility functions for converting tags to hashtags
"""

def tags_to_hashtags(tags):
    """
    Convert a list of tags to hashtags for social media
    
    Args:
        tags: List of tags
        
    Returns:
        List of hashtags
    """
    # Basic implementation: add # and remove spaces
    basic_hashtags = ["#" + tag.replace(" ", "") for tag in tags]
    
    # Add some common photography hashtags
    common_hashtags = [
        "#photography", "#photooftheday", "#instagood", "#picoftheday",
        "#beautiful", "#art", "#photo", "#photographer", "#naturephotography",
        "#travelphotography", "#portraitphotography", "#streetphotography"
    ]
    
    # Combine and remove duplicates
    all_hashtags = list(set(basic_hashtags + common_hashtags[:5]))
    
    return all_hashtags
