import requests
from bs4 import BeautifulSoup 
import re
from urllib.parse import urljoin, urlparse
import json
from google.genai import Client  


client = Client(api_key="AIzaSyAytoOd44cqWsUHp2rOtl0EeeJ51bKDYSI") 

def clean_text(text):
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

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
        
        if 'title' in page and page['title']:
            cleaned_page['title'] = page['title']
        else:
            cleaned_page['title'] = None

        cleaned_headings = {}
        if 'headings' in page:
            for key in page['headings']:
                headings_list = page['headings'][key]
                new_list = []
                for h in headings_list:
                    if h not in new_list:
                        new_list.append(h)
                if new_list:
                    cleaned_headings[key] = new_list
        cleaned_page['headings'] = cleaned_headings
        paragraphs = []
        if 'paragraphs' in page:
            for p in page['paragraphs']:
                if p not in paragraphs:
                    paragraphs.append(p)
        cleaned_page['paragraphs'] = paragraphs

        links = []
        if 'links' in page:
            for link in page['links']:
                if link not in links:
                    if base_domain:
                        if urlparse(link)    == base_domain:
                            links.append(link)
                    else:
                        links.append(link)
        cleaned_page['links'] = links

        images = []
        if 'images' in page:
            for img in page['images']:
                if img not in images:
                    images.append(img)
        cleaned_page['images'] = images

        if cleaned_page['title'] or cleaned_page['paragraphs']:
            cleaned_data.append(cleaned_page)
    print("data cleaned successfully")
    return cleaned_data
url = "https://webscraper.io/test-sites"
result = scrape_website(url)
base_domain = urlparse(url).netloc
cleaned_result = clean_scraped_data(result, base_domain)


with open("cleaned_scraped_data.json", "w", encoding="utf-8") as f:
    json.dump(cleaned_result, f, indent=4, ensure_ascii=False)

system_prompt =f"""
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


response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=final_prompt 
)

print(response)

