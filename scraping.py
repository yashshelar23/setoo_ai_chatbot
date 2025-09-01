import requests
from bs4 import BeautifulSoup 
import re
from urllib.parse import urljoin, urlparse
import json


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


def clean_text(text):
    text = text.strip()
    return re.sub(r'\s+', ' ', text)

visited = set()

def scrape_page(url, base_url):
    print(f"Scraping: {url}")
    try:
        response = requests.get(url, timeout=10)
    except requests.exceptions.RequestException:
        return None

    if response.status_code != 200:
        print(f"Non-200 status for {url}: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    scraped_data = {}

    scraped_data['title'] = clean_text(soup.title.string) if soup.title else "No title"
    headings = {}
    for i in range(1, 4):
        found = [clean_text(h.get_text()) for h in soup.find_all(f'h{i}') if clean_text(h.get_text())]
        headings[f'h{i}'] = list(dict.fromkeys(found))
    scraped_data['headings'] = headings

    paragraphs = [clean_text(p.get_text()) for p in soup.find_all('p') if clean_text(p.get_text())]
    scraped_data['paragraphs'] = list(dict.fromkeys(paragraphs))

    links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True)]
    links = [link.split('#')[0] for link in links]
    scraped_data['links'] = list(dict.fromkeys(links))

    images = [urljoin(url, img['src']) for img in soup.find_all('img', src=True)]
    scraped_data['images'] = list(dict.fromkeys(images))

    for link in scraped_data['links']:
        if urlparse(link).netloc == urlparse(base_url).netloc:
            if link not in visited:
                visited.add(link)
                scrape_page(link, base_url)

    return scraped_data

def scrape_website(base_url):
    visited.add(base_url)
    all_data = []
    data = scrape_page(base_url, base_url)
    if data:
        all_data.append(data)
    return all_data

def clean_scraped_data(scraped_data, base_domain=None):
    cleaned_data = []

    for page in scraped_data:
        cleaned_page = {}
        cleaned_page['title'] = page.get('title', None)
        cleaned_page['headings'] = {k: list(dict.fromkeys(v)) for k, v in page.get('headings', {}).items()}
        cleaned_page['paragraphs'] = list(dict.fromkeys(page.get('paragraphs', [])))
        cleaned_page['links'] = list(dict.fromkeys(page.get('links', [])))
        cleaned_page['images'] = list(dict.fromkeys(page.get('images', [])))
        if cleaned_page['title'] or cleaned_page['paragraphs']:
            cleaned_data.append(cleaned_page)
    print("Data cleaned successfully")
    return cleaned_data


url = "https://webscraper.io/test-sites"
result = scrape_website(url)
base_domain = urlparse(url).netloc
cleaned_result = clean_scraped_data(result, base_domain)

with open("cleaned_scraped_data.json", "w", encoding="utf-8") as f:
    json.dump(cleaned_result, f, indent=4, ensure_ascii=False)


system_prompt = f"""
You are a helpful AI assistant.
Use ONLY this website data to answer user questions:
{json.dumps(cleaned_result)}
"""

user_message = f"""
Here is the cleaned website data:
{json.dumps(cleaned_result, indent=4)}

Please summarize the website content and highlight main services, headings, and key points.
"""

final_prompt = system_prompt + "\n\n" + user_message

OPENROUTER_API_KEY = "" 
client = OpenRouterClient(api_key=OPENROUTER_API_KEY, model="gpt-4o-mini")

response_text = client.generate_response(final_prompt)

print(response_text)
