import json
from google.genai import Client

client = Client(api_key="AIzaSyDX1-V0gchoeOFf9D4GvDwXwD6rg4DnJ-8") 


with open("cleaned_scraped_data.json", "r", encoding="utf-8") as f:
    cleaned_data = json.load(f)

system_prompt = f"""
You are a helpful AI assistant. 
Use ONLY the following website data to answer user questions:
{json.dumps(cleaned_data)}
Answer in clear, friendly, and concise chatbot style.
Answer with the emojis to increase engagement.
Use the modern formatting to answer user questions.
create a space between the user question and the assistant answer.

"""

chat_history = [
    {"role": "system", "content": system_prompt}
]


print("✅ Chatbot ready! Type 'exit' to quit.\n")

while True:
    user_input = input("You: ")
    if user_input.lower() == "exit":
        break
    
    prompt = system_prompt + f"\n\nUser question: {user_input}"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    bot_answer = ""
    if hasattr(response, 'candidates') and len(response.candidates) > 0:
        candidate = response.candidates[0]
        content = candidate.content
        if hasattr(content, 'parts'):
            for part in content.parts:
                bot_answer += part.text + "\n"
        elif isinstance(content, str):
            bot_answer = content

    if bot_answer.strip() == "":
        bot_answer = "Sorry, I don't have an answer for that based on the website data."

    print("Bot:", bot_answer.strip())