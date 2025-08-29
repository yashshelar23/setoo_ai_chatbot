import json
import re
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
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


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str):
        response = genai.GenerativeModel(self.model).generate_content(prompt)
        if hasattr(response, "candidates") and len(response.candidates) > 0:
            candidate = response.candidates[0]
            content = candidate.content
            text = ""
            if hasattr(content, "parts"):
                for part in content.parts:
                    text += part.text + "\n"
            elif isinstance(content, str):
                text = content
            return text.strip()
        return "Sorry, I couldn't generate a response."


class ChatHandler:
    def __init__(self, system_prompt, gemini_client):
        self.chat_history = []
        self.system_prompt = system_prompt
        self.gemini_client = gemini_client

    def get_prompt(self, user_message):
        prompt = self.system_prompt + "\n\n"
        for msg in self.chat_history:
            prompt += f"User: {msg['user']}\nAI: {msg['bot']}\n"
        prompt += f"User: {user_message}\nAI:"
        return prompt

    def process_message(self, user_message):
        prompt = self.get_prompt(user_message)
        bot_answer = self.gemini_client.generate_response(prompt)
        if bot_answer.strip() == "":
            bot_answer = "Sorry, I don't have an answer for that based on the website data."
        self.chat_history.append({"user": user_message, "bot": bot_answer})
        return bot_answer

class GeminiScraperSDK:
    def __init__(self, api_key, system_prompt):
        self.scraper = WebScraper()
        self.cleaner = DataCleaner()
        self.gemini_client = GeminiClient(api_key)
        self.chat_handler = ChatHandler(system_prompt, self.gemini_client)

    def scrape_and_clean(self, url):
        scraped_data = self.scraper.scrape_website(url)
        return self.cleaner.clean_scraped_data(scraped_data)

    def chat(self, user_message):
        return self.chat_handler.process_message(user_message)


app = FastAPI()

# File where history will be stored
CHAT_FILE = Path("chat_history.jsonl")

class ChatCreate(BaseModel):
    username: str
    message: str

# ✅ Save message (append to file)
@app.post("/chat/")
def add_message(chat: ChatCreate):
    with CHAT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(chat.dict(), ensure_ascii=False) + "\n")
    return {"status": "Message saved"}

# ✅ Get all messages
@app.get("/chat/")
def get_messages():
    messages = []
    if CHAT_FILE.exists():
        with CHAT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                messages.append(json.loads(line))
    return {"messages": messages}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

sdk = GeminiScraperSDK(api_key="AIzaSyAytoOd44cqWsUHp2rOtl0EeeJ51bKDYSI", system_prompt=system_prompt)

@app.get("/")
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




@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            user_message = await websocket.receive_text()
            # ✅ Load fresh scraped data every time
            scraped_data = get_latest_data()
            context_text = json.dumps(scraped_data)

            # ✅ Combine user message with latest context
            prompt = f"""
            Your are AI assistant and title of {context_text}
            Markdown formatting and bulleted points.
            With emojis for engagement.
            Give introduction to you.
            Every response should be concise and to the point.
            Every response should be next line. 
            Not need to introducetion on every response.
{context_text}

User: {user_message}
"""

            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)

                
                answer = getattr(response, 'text', "No response from AI.")
                await websocket.send_text(answer)

            except Exception as e:
                await websocket.send_text(f"Error: {str(e)}")
    except WebSocketDisconnect:
        print("Client disconnected")