from google import genai
from app.config import settings
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from cohere import ClientV2

import certifi
import os
# tell Python where to find trusted CA certs
os.environ["SSL_CERT_FILE"] = certifi.where()

# now safe to import network stuff
from dotenv import load_dotenv
from app.prompts import REWRITE_PROMPT, SYSTEM_PROMPT

load_dotenv()

embed = genai.Client(api_key=settings.gemini_api_key)

chat = OpenAI(api_key=settings.groq_api_key,
               base_url=settings.groq_url).chat.completions.create


rerank_client = ClientV2(
    api_key=settings.cohere_api_key
)

pc = Pinecone(api_key=settings.db_api_key)

index = pc.index(name='rag-chatbot')

def get_dense_embeddings(content):
    embeddings = embed.models.embed_content(model=settings.embed_llm, contents=content)
    return [
        embedding.values
        for embedding in embeddings.embeddings
    ]

def get_sparse_embeddings(content, input_type):
    embeddings = pc.inference.embed(
        model="pinecone-sparse-english-v0",
        inputs=content,
        parameters={
            "input_type": input_type
        }
    )
    sparsed_embeddings =[]
    for s in embeddings.data:
        each = {
            "indices": s["sparse_indices"],
            "values": s["sparse_values"]
        }
        sparsed_embeddings.append(each)
    
    return sparsed_embeddings

def rewrite_query(query: str):
    result = chat(model=settings.rewrite_llm,
                  messages=[{
                      "role": "system", 
                      "content": REWRITE_PROMPT.format(query=query)
                  }],
                  temperature=0.3)
    
    all = result.choices[0].message.content.split("\n")
    return all
    
    
def ask_llm(history, context):
    stream = chat(model=settings.chat_llm,
                  messages=[
                      {"role": "system",
                       "content": SYSTEM_PROMPT.format(context=context)},
                       *history
                  ], stream=True, temperature=0.3)
    return stream

def get_reranking(query: str, documents):
    results = rerank_client.rerank(
        model="rerank-v3.5",
        query=query,
        documents=documents,
        top_n=5
    )
    return results
