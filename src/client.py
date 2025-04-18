import asyncio
from datetime import datetime, timezone
import os
from pydantic import BaseModel
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError, InvalidURI
from calendar_event_classifier import is_calendar_event
from conversations.ops import disentangle_message, update_completed_conversation, update_suspended_conversation
from conversations.disentanglement.rule_based_classifier import rule_based_classifier
from conversations.disentanglement.llm_based_classifier import llm_based_classifier
from conversations.extract_date_time_llm_model import model as event_datetime_extractor
from datatypes import Message, Conversation
from dotenv import load_dotenv
import aiofiles as aiof
import logging


logger = logging.getLogger(__name__)

class AppState(BaseModel):
    calender_conversations: list[Conversation] = []


async def store_probable_calendar_conversations(conv: Conversation):
    async with aiof.open(f"results/event_{conv.lines[0].seqid}_v1.json", "w") as out:
        await out.write(conv.model_dump_json())
        await out.flush()


def process_message(state: AppState, message: Message) -> AppState:
    classified_message = is_calendar_event(message)
    logger.debug(f"Classified message: {classified_message}")
    
    confident_it_is_a_calendar_event = (
        classified_message.classification.label == "LABEL_1"
        and classified_message.classification.score > 0.8
    )
    
    if confident_it_is_a_calendar_event:
        # TODO: add ollama docker and compose these two together
        try:
            state.calender_conversations = disentangle_message(
                state.calender_conversations, 
                classified_message, 
                llm_based_classifier
            )
        except ConnectionError:
            state.calender_conversations = disentangle_message(
                state.calender_conversations, 
                classified_message, 
                rule_based_classifier
            )
        
        logger.info(
            f"Received new message: '{classified_message.message}'"
            f" with confidence {classified_message.classification.score}"
        )
    return state


def mark_suspended_conversations(state: AppState):
    state.calender_conversations = update_suspended_conversation(
        conversations=state.calender_conversations,
        seconds_lapsed=30,
        current_time=datetime.now(timezone.utc),
    )
    return state


def mark_completed_conversations(state: AppState):
    state.calender_conversations = update_completed_conversation(
        conversations=state.calender_conversations,
        current_time=datetime.now(timezone.utc)
    )
    return state


def extract_calendar_datetime_from_conversations(state: AppState): 
    updated_conversations = []
    for conversation in state.calender_conversations:
        if conversation.suspended:
            conversation.event_datetime = event_datetime_extractor(conversation)
        updated_conversations.append(conversation)
    state.calender_conversations = updated_conversations
    return state


async def write_completed_conversations(conversations: list[Conversation]):
    for conv in list(conversations):
        if conv.completed:
            await store_probable_calendar_conversations(conv)
            logger.debug(f"Stored conversation: {conv.lines[0].message}")

async def listen(url):
    state = AppState()
    try:
        async with websockets.connect(url) as websocket:
            while True:
                message = Message.model_validate_json(
                    await websocket.recv(decode=True)
                )
                
                state = process_message(state, message)
                state = mark_suspended_conversations(state)
                state = extract_calendar_datetime_from_conversations(state)
                state = mark_completed_conversations(state)

                logger.debug(f"Updated State: {state}")
                await write_completed_conversations(state.calender_conversations)

    except (ConnectionClosedOK):
        logger.info("Completed processing messages in WebSocket")
        logger.debug("Writing out any pending conversations")
        await(write_out_partial_conversations(state))

    except ConnectionClosedError as e:
        logger.error(f"Connection closed unexpectedly: {e}", exc_info=True)
        await(write_out_partial_conversations(state))
    
    except InvalidURI:
        logger.error(f"Invalid WebSocket URI: {url}")


async def write_out_partial_conversations(state: AppState):
    for conv in state.calender_conversations:
        await store_probable_calendar_conversations(conv)

def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    asyncio.run(listen(os.getenv("WS_SOCK")))


if __name__ == "__main__":
    main()
