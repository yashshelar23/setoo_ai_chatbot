import json
import re
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pathlib import Path
from prompt import system_prompt


class WebScraper:
    def __init__(self):
        self.visited = set()

    def clean_text(self, text):
        text = text.strip()
        return re.sub(r'\s+', ' ', text)

    def scrape_page(self, url, base_url):
        try:
            response = requests.get(url, timeout=10)
        except requests.exceptions.RequestException:
            return None

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        scraped_data = {
            'title': self.clean_text(soup.title.string) if soup.title else "No title",
            'headings': {},
            'paragraphs': [],
            'links': [],
            'images': []
        }

        for i in range(1, 4):
            found = [self.clean_text(h.get_text()) for h in soup.find_all(f'h{i}') if self.clean_text(h.get_text())]
            scraped_data['headings'][f'h{i}'] = list(dict.fromkeys(found))

        scraped_data['paragraphs'] = list(dict.fromkeys(
            [self.clean_text(p.get_text()) for p in soup.find_all('p') if self.clean_text(p.get_text())]
        ))

        links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True)]
        links = [link.split('#')[0] for link in links]
        scraped_data['links'] = list(dict.fromkeys(links))

        scraped_data['images'] = list(dict.fromkeys(
            [urljoin(url, img['src']) for img in soup.find_all('img', src=True)]
        ))

        for link in scraped_data['links']:
            if urlparse(link).netloc == urlparse(base_url).netloc:
                if link not in self.visited:
                    self.visited.add(link)
                    self.scrape_page(link, base_url)

        return scraped_data

    def scrape_website(self, base_url):
        self.visited.clear()
        self.visited.add(base_url)
        all_data = []
        data = self.scrape_page(base_url, base_url)
        if data:
            all_data.append(data)
        return all_data


class DataCleaner:
    @staticmethod
    def clean_scraped_data(scraped_data):
        cleaned_data = []
        for page in scraped_data:
            cleaned_page = {
                'title': page.get('title'),
                'headings': page.get('headings', {}),
                'paragraphs': page.get('paragraphs', []),
                'links': page.get('links', []),
                'images': page.get('images', [])
            }
            if cleaned_page['title'] or cleaned_page['paragraphs']:
                cleaned_data.append(cleaned_page)
        return cleaned_data


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate_response(self, prompt: str):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ]
        }
        try:
            response = requests.post(self.api_url, headers=headers, json=data, timeout=20)
            response.raise_for_status()
            resp_json = response.json()
            return resp_json["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Error from OpenRouter: {str(e)}"


class ChatHandler:
    def __init__(self, system_prompt, ai_client):
        self.chat_history = []
        self.system_prompt = system_prompt
        self.ai_client = ai_client

    def get_prompt(self, user_message):
        prompt = self.system_prompt + "\n\n"
        for msg in self.chat_history:
            prompt += f"User: {msg['user']}\nAI: {msg['bot']}\n"
        prompt += f"User: {user_message}\nAI:"
        return prompt

    def process_message(self, user_message):
        prompt = self.get_prompt(user_message)
        bot_answer = self.ai_client.generate_response(prompt)
        if not bot_answer.strip():
            bot_answer = "Sorry, I don't have an answer for that based on the website data."
        self.chat_history.append({"user": user_message, "bot": bot_answer})
        return bot_answer

class OpenRouterScraperSDK:
    def __init__(self, api_key, system_prompt):
        self.scraper = WebScraper()
        self.cleaner = DataCleaner()
        self.ai_client = OpenRouterClient(api_key)
        self.chat_handler = ChatHandler(system_prompt, self.ai_client)

    def scrape_and_clean(self, url):
        scraped_data = self.scraper.scrape_website(url)
        return self.cleaner.clean_scraped_data(scraped_data)

    def chat(self, user_message):
        return self.chat_handler.process_message(user_message)

app = FastAPI()
CHAT_FILE = Path("chat_history.jsonl")
templates = Jinja2Templates(directory="templates")

# Replace with your OpenRouter API key
OPENROUTER_API_KEY = ""
sdk = OpenRouterScraperSDK(api_key=OPENROUTER_API_KEY, system_prompt=system_prompt)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatCreate(BaseModel):
    username: str
    message: str

@app.post("/chat/")
def add_message(chat: ChatCreate):
    with CHAT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(chat.dict(), ensure_ascii=False) + "\n")
    return {"status": "Message saved"}

@app.get("/chat/")
def get_messages():
    messages = []
    if CHAT_FILE.exists():
        with CHAT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                messages.append(json.loads(line))
    return {"messages": messages}

@app.get("/", response_class=HTMLResponse)
async def get_scrape_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/scrape")
async def scrape_url(url: str = Form(...)):
    try:
        cleaned_result = sdk.scrape_and_clean(url)
        with open("cleaned_scraped_data.json", "w", encoding="utf-8") as f:
            json.dump(cleaned_result, f, indent=4, ensure_ascii=False)
        return JSONResponse({
            "status": "success",
            "message": "Scraping completed",
            "cleaned_data_preview": cleaned_result[:3]
        })
    except Exception:
        return RedirectResponse(url="/chat", status_code=303)

@app.get("/chat", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

def get_latest_data():
    try:
        with open("cleaned_scraped_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

with open("cleaned_scraped_data.json", "r", encoding="utf-8") as f:
    cleaned_data = json.load(f)

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            user_message = await websocket.receive_text()
            scraped_data = get_latest_data()
            context_text = json.dumps(scraped_data)
            prompt = f"""

You are a friendly AI assistant, like ChatGPT. 
Use ONLY the following website data to answer user questions:
{json.dumps(cleaned_data)}
Guidelines:
- Use <b> or <strong> for important keywords instead of Markdown.
- Use <ul> and <li> for lists instead of hyphens.
- Use emojis to make responses friendly.
- Keep answers concise and clear.
- Break text into short paragraphs or lines.
- Avoid repeating greetings unnecessarily.

{context_text}


User: {user_message}
"""
            answer = sdk.chat_handler.process_message(prompt)

            await websocket.send_text(answer)

    except WebSocketDisconnect:
        print("Client disconnected")
