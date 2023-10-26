from flask import Flask, request, jsonify, render_template, session
import logging
import os
import time
import json
import openai
import requests
from tenacity import retry, wait_random_exponential, stop_after_attempt
import cohere
from qdrant_client import models, QdrantClient
from embed_harvard import embed_text
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import asyncio
import aiohttp
import tg_logger
import uuid


app = Flask(__name__)

# Cohere
co = cohere.Client()

app.secret_key = 

# Qdrant
qdrant_client = QdrantClient(
    url="", 
    prefer_grpc=True,
    api_key="",
)

# Telegram data for the logger
token = ""
users = [201621438]

# Base logger tg-logger
logger = logging.getLogger('foo')
logger.setLevel(logging.INFO)

# Logging bridge setup tg-logger
tg_logger.setup(logger, token=token, users=users)

# Set up logging
logging.basicConfig(level=logging.INFO)

os.environ["BOT_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["COHERE_API_KEY"] = ""

DEEPGRAM_API_KEY = ""


GPT_MODEL = "gpt-3.5-turbo-0613" #gpt-4-0613 #gpt-3.5-turbo-0613

@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(messages, functions=None, function_call=None, model=GPT_MODEL):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + "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",
    }
    json_data = {"model": model, "messages": messages}
    if functions is not None:
        json_data.update({"functions": functions})
    if function_call is not None:
        json_data.update({"function_call": function_call})
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=json_data,
        )
        return response
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        return e
    
functions = [
    {
        "name": "get_results",
        "description": "Always use this function to get information to answer the question",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Full and detailed question to retrieve the data from vector db, taking into context older messages.",
                },
            },
        },
    }]

# Cache to store recent messages for each user session
message_history = {}

def get_results(query):
    vectors = embed_text(query)
    for vector in vectors:
        response = qdrant_client.search(
            collection_name="harvard",
            query_vector=vector,
            limit=5,
        )
    results = [record.payload["content"] for record in response]

    return results


messages = []

def send_message(messages, user_id = None):
    message = messages[-1]["content"]
    chat_response = chat_completion_request(messages, functions=functions)
    #print(chat_response.json())
    response = chat_response.json()["choices"][0]
    if response["finish_reason"] == "function_call":
        fcall = response["message"]["function_call"]
        if fcall["name"] == "get_results":
            arguments = json.loads(fcall["arguments"])
            query = arguments["query"]
            retrieved = str(get_results(query))
            print(f"\n\n\n{retrieved}. The query is {query}\n\n\n")
            comp_message = {"role": "user", "content": f"Question: {message}\n Use only the relevant information from this context:\n " + retrieved}
            messages.append(comp_message)
            second_request = chat_completion_request(messages)
            final_response = second_request.json()["choices"][0]["message"]
            messages.append({"role": "assistant", "content": final_response['content']})
            return final_response['content']
        
    assistant_message = response["message"]
    print(chat_response.json())

    """# If a phone number is provided as the user ID, send an SMS to the user
    if user_id and user_id.startswith("+"):
        send_sms_to_user(user_id, assistant_message["content"])"""

    return assistant_message['content']


@app.route('/')
def index():
    # Dictionary with unique IDs for sessions
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/get_response', methods=['POST'])
def get_response():
    message = request.json['message']
    user_ip = request.json['ip']

    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())  # Generate a unique user_id
    user_id = session['user_id']

    if user_id not in message_history.keys():
        message_history[user_id] = []
        message_history[user_id].append({"role": "system", "content": "You are a helpful chat assistant for visitors at the Harvard Art Museum that speaks like a really interesting charismatic human. You must answer only those questions that the user has about the Harvard Art Musesum. IF THE USER ASKS ANY QUESTION ABOUT THE MUSEUM, I REPEAT ANY QUESTION, CALL the function get_results to get information to answer the question. If the provided context does not have information to answer the question, say that you do not know and direct the user to the appopriate resourse. Always REWRITE the context to write fluent and coherent answers."})
    else:
        if len(message_history[user_id]) > 3:
            message_history[user_id] = message_history[user_id][-3:]
            #message_history[user_id].append({"role": "system", "content": "You are a helpful chat assistant for students at the Harvard Art Museum. Your role is to answer any questions that the user has about the objects in the museum's collection. IF THE USER ASKS ANY IRRELEVANT QUESTION TO THE MUSEUM, I REPEAT ANY QUESTION, CALL the function get_results to get information to answer the question. In cases where you cannot find the answer using the available functions, kindly inform the user that you do not have the answer. Your responses should be in the language of the question—most likely in English. Your aim is to emulate human-like interactions while ensuring helpful and informative assistance."})
    
    user_message = {"role": "user", "content": message}
    message_history[user_id].append(user_message)

    response = send_message(message_history[user_id])
    assistant_message = {"role": "assistant", "content": response}
    message_history[user_id].append(assistant_message)

    logger.info(f'</code>IP: {user_ip}<code> ID: {user_id} asked: \n\n{message} \n\nAnswer: {response}')

    return jsonify(response=response)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Use port 5000 for local development
    app.run(host='0.0.0.0', port=port)
