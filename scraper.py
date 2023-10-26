from bs4 import BeautifulSoup
import requests
import requests.exceptions
from urllib.parse import urlsplit
from urllib.parse import urlparse
from collections import deque
import re

print("Hi! Welcome to the web crawler!")

url = input("Input your urls: ")

# A queue of URLs to be crawled
new_urls = deque([url])

# A set of URLs that have already been processed 
processed_urls = set()

# A set of domains inside the target website
local_urls = set()

# A set of domains outside the target website
foreign_urls = set()

# A set of broken URLs
broken_urls = set()

# A list to store file URLs (PDF, TXT, etc.)
file_urls = []

# Process URLs one by one until we exhaust the queue
while len(new_urls):
    # Move the next URL from the queue to the set of processed URLs
    url = new_urls.popleft()
    processed_urls.add(url)

    # Get the URL's content
    print("Processing %s" % url)
    try:
        response = requests.get(url)
    except (
        requests.exceptions.MissingSchema,
        requests.exceptions.ConnectionError,
        requests.exceptions.InvalidURL,
        requests.exceptions.InvalidSchema,
    ):
        # Add broken URLs to their own set, then continue
        broken_urls.add(url)
        continue

    # Extract base URL to resolve relative links
    parts = urlsplit(url)
    base = "{0.netloc}".format(parts)
    strip_base = base.replace("www.", "")
    base_url = "{0.scheme}://{0.netloc}".format(parts)
    path = url[: url.rfind("/") + 1] if "/" in parts.path else url

    # Create a Beautiful Soup object for the HTML document
    soup = BeautifulSoup(response.text, "lxml")

    for link in soup.find_all("a"):
        # Extract the link URL from the anchor
        anchor = link.attrs["href"] if "href" in link.attrs else ""

        if anchor.endswith((".pdf", ".txt")):
            # Save file URLs to the file_urls list
            file_urls.append(anchor)
        elif anchor.startswith("/"):
            local_link = base_url + anchor
            local_urls.add(local_link)
        elif strip_base in anchor:
            local_urls.add(anchor)
        elif not anchor.startswith("http"):
            local_link = path + anchor
            local_urls.add(local_link)
        else:
            foreign_urls.add(anchor)

        for i in local_urls:
            if i not in new_urls and i not in processed_urls:
                new_urls.append(i)

# Save all links to a text file
with open(url+".txt", "w") as f:
    f.write("\n--------\nLocal URLs\n--------\n")
    for url in local_urls:
        f.write(url + "\n")

    f.write("\n--------\nForeign URLs\n--------\n")
    for url in foreign_urls:
        f.write(url + "\n")

    f.write("\n--------\nFile URLs\n--------\n")
    for url in file_urls:
        f.write(url + "\n")

print("Finished! Links saved to the file" + url+".txt. Other links (including broken):", broken_urls, new_urls)
print(processed_urls)

