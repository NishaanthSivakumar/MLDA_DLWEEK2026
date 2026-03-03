import requests
from bs4 import BeautifulSoup

url = "https://www.stat.nus.edu.sg/our-people/faculty-members/"
resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(resp.text, "html.parser")

# Try to find professor name and research interest patterns
# Look for typical WordPress people listing structures
for tag in soup.find_all(["h2", "h3", "h4", "h5", "p", "span", "a"]):
    text = tag.get_text(strip=True)
    cls = " ".join(tag.get("class", []))
    if text and len(text) > 5 and len(text) < 300:
        href = tag.get("href", "")
        if "stat.nus" in href or "Professor" in text or "Assoc" in text or "Asst" in text or "interest" in text.lower() or "research" in text.lower():
            print(f"TAG: {tag.name} | CLASS: {cls} | HREF: {href}")
            print(f"TEXT: {text}")
            print("---")
