import os
import scrapy
from scrapy.crawler import CrawlerProcess
from qdrant_client import models, QdrantClient
import cohere
from qdrant_client.http import models as rest
import pandas as pd
import json
import xml.etree.ElementTree as ET
import requests
import time
import openai
from scrapy import Selector
import re

os.environ["COHERE_API_KEY"] = "TTswjcHtySkELt8HyMaQNDcHhNIamyPaFLB9Gc8V"
os.environ["OPENAI_API_KEY"] = "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"
openai.organization = "org-Us0ibQrQlvTPoy0ujpWm0Sfe"
openai.api_key = os.getenv("OPENAI_API_KEY")

# Qdrant
qdrant = QdrantClient(
    url="https://6767422f-d9ec-4058-b60c-9b9a2e16905f.eu-central-1-0.aws.cloud.qdrant.io:6333", 
    prefer_grpc=True,
    api_key="AcZ67kvwYQJG3965k7cefuE0SyTuqVp_MbyPDrNHUeEAaNGMnpgbKQ",
)

# Scrapy Spider
class ColbySpider(scrapy.Spider):
    print("Started loading the links")
    with open("urls.txt", "r") as f:
        links = f.readlines()
    
    print("Loaded the links!")
    
    name = 'harvard'
    start_urls = links
    
    custom_settings = {
        'FEED_FORMAT': 'json',
        'FEED_URI': 'output.json'
    }

    def clean_text(self, text):
        # Remove multiple spaces and newline characters and replace with a single space
        return re.sub(r'\s+', ' ', text).strip()

    def parse(self, response):
        print("Parsing; ", response.url)
        sel = Selector(response)

        # Extract dt and dd tags
        dt_tags = sel.css('section.w-full.lg\\:max-w-5xl.text-lg.px-4.lg\\:px-0.mx-auto dl dt::text').extract()
        dd_tags = sel.css('section.w-full.lg\\:max-w-5xl.text-lg.px-4.lg\\:px-0.mx-auto dl dd').extract()

        dt_texts = [self.clean_text(dt) for dt in dt_tags]
        dd_texts = []

        # For dd tags, we want to get the innerHTML and remove any HTML tags from it
        for dd in dd_tags:
            dd_sel = Selector(text=dd)
            dd_text = self.clean_text(dd_sel.xpath('string()').get())
            dd_texts.append(dd_text)

        # Combine dt and dd texts
        combined_text = ', '.join([f"{dt}: {dd}" for dt, dd in zip(dt_texts, dd_texts)])

        return {"text": combined_text}



def embed_text(text: list, model='text-embedding-ada-002'):
    """Generate text embeddings using OpenAI's Ada model."""
    if type(text) is str:
        text = [text]
    # Since you are passing a list of texts, you might need to loop through each text item in the list
    vectors = []
    for t in text:
        response = openai.Embedding.create(input=t, model=model)
        embedding = response['data'][0]['embedding']
        vectors.append(list(map(float, embedding)))
    print("Embedded.")
    return vectors

def create_collection(name):
    # Create Qdrant vector database collection
    qdrant.recreate_collection(
        collection_name=name,
        vectors_config=models.VectorParams(
            size=1536, 
            distance=rest.Distance.COSINE
        ),
    )
    print(f"The collection {name} was created!")

def load_from_scrapy_output():
    print("\n\n\nStarted loading from the json file.\n")
    with open("output.json", "r") as f:
        chunks = [item["text"] for item in json.load(f)]

    data = []
    for idx, chunk in enumerate(chunks):
        data.append({
            'id': idx + 1,
            'content': chunk,
            'version': 'v1'
        })

    df = pd.DataFrame(data)
    ids = df["id"].tolist()
    vectors = embed_text(df["content"].tolist())

    qdrant.upsert(
    collection_name="harvard", 
    points=rest.Batch(
        ids=ids,
        vectors=vectors,
        payloads=df.to_dict(orient='records'),
    ))

if __name__ == "__main__":
    create_collection("harvard")
    print("Created a collection")

    # Running Scrapy spider
    """print("Started running the crawler")
    process = CrawlerProcess()
    process.crawl(ColbySpider)
    process.start()"""

    # Load the scraped data to Qdrant
    load_from_scrapy_output()
    print("Successfully uploaded to QDrant")
