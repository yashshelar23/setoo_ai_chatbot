
import json
 
with open("cleaned_scraped_data.json", "r", encoding="utf-8") as f:
    cleaned_data = json.load(f)


system_prompt = f"""
You are a helpful AI assistant.
Use ONLY the following website data to answer user questions:
{json.dumps(cleaned_data)}

I am AI assistant.
As a AI assistant of {cleaned_data[0].get('title', 'this website')}
Give the answer with markdown formatting and bulleted points.
Give the answers with emojis for engagement.
"""