import urllib3
import json

http = urllib3.PoolManager()

"""# Find all of the objects with the word "cat" in the title and return only a few fields per record
r = http.request('GET', 'https://api.harvardartmuseums.org/object',
    fields = {
        'apikey': '',
        'size': "100",
        'fields': 'url',
        'page': '1'
    })

print(r.data)"""

def scrap(link):
    r = http.request('GET', link)
    # Convert bytes to string
    data_str = r.data.decode('utf-8')

    # Load JSON data
    data = json.loads(data_str)

    # Extract "next" value
    link = data['info']['next']

    # Extract and append urls to the txt file
    with open('urls.txt', 'a') as file:
        for record in data['records']:
            url = record['url']
            file.write(url + '\n')

    print(data['info']['page'])

    scrap(link)

link = "https://api.harvardartmuseums.org/object?apikey=48e32981-8e12-4922-b543-3a8a60f896a6&size=100&fields=url&page=1520"

"""def scrap(page):
    
    link = f"https://api.harvardartmuseums.org/object?apikey=48e32981-8e12-4922-b543-3a8a60f896a6&size=100&fields=url&page={page}"
    
    r = http.request('GET', link)
    # Convert bytes to string
    data_str = r.data.decode('utf-8')

    # Load JSON data
    data = json.loads(data_str)

    # Extract and append urls to the txt file
    with open('urls.txt', 'a') as file:
        for record in data['records']:
            url = record['url']
            file.write(url + '\n')

    print(data['info']['page'])

    scrap(page+1)"""

scrap(link)
