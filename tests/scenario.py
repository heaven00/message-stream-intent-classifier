from pydantic import BaseModel, Field
from typing import List
from datatypes import Message, Conversation


class Scenario(BaseModel):
    initial_state: List[Conversation]
    new_message: Message
    expected_state: List[Conversation]
