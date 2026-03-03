import requests
from bs4 import BeautifulSoup

url = "https://www.stat.nus.edu.sg/our-people/faculty-members/"
print(f"Fetching {url}...")
resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
print(f"Status: {resp.status_code}, Length: {len(resp.text)}")
soup = BeautifulSoup(resp.text, "html.parser")

# Print all h2-h5 tags
print("\n=== ALL HEADINGS ===")
for tag in soup.find_all(["h2", "h3", "h4", "h5"]):
    text = tag.get_text(strip=True)
    if text:
        print(f"{tag.name}: {text[:150]}")

# Print all links with stat.nus
print("\n=== STAT.NUS LINKS ===")
for a in soup.find_all("a", href=True):
    if "stat.nus" in a["href"]:
        print(f"LINK: {a['href']} -> {a.get_text(strip=True)[:100]}")

# Print first 5000 chars of HTML to understand structure  
print("\n=== FIRST PART OF BODY ===")
body = soup.find("body")
if body:
    print(str(body)[:5000])
