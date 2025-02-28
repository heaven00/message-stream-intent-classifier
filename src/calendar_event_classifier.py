from transformers import pipeline
from transformers import BertTokenizer
from text_utils import clean_text
from datatypes import Message, ClassifiedMessage


model_path = "model/bert_classifier_v1"
classifier = pipeline(
    "text-classification", 
    model=model_path, 
    tokenizer=BertTokenizer.from_pretrained('bert-base-uncased')
)


def is_calendar_event(data: Message) -> ClassifiedMessage:
    cleaned_text = clean_text(data.message)
    return ClassifiedMessage(
        seqid=data.seqid,
        ts=data.ts,
        user=data.user,
        message=data.message,
        classification=classifier(cleaned_text)[0]
    )
