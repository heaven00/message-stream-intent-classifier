import asyncio
import os
import websockets
from transformers import pipeline
from transformers import BertTokenizer
from text_utils import clean_text
from datatypes import Message, CalendarClassification
from dotenv import load_dotenv

# Define cleaning functions
THRESHOLD = 0.85
model_path = "model/bert_classifier_v1"
classifier = pipeline(
    "text-classification", 
    model=model_path, 
    tokenizer=BertTokenizer.from_pretrained('bert-base-uncased')
)


def is_calendar_event(data: Message, threshold: float) -> CalendarClassification:
    cleaned_text = clean_text(data.message)
    # Classify the cleaned message
    return CalendarClassification.model_validate(classifier(cleaned_text)[0])


async def listen(url):
    async with websockets.connect(url) as websocket:
        while True:
            message = await websocket.recv(decode=True)
            data = Message.model_validate_json(message)
            classification = is_calendar_event(data, THRESHOLD)
            print(data.message, classification)


def main():
    load_dotenv()
    asyncio.run(listen(os.getenv("WS_SOCK")))
