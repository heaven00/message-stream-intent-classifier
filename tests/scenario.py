from pydantic import BaseModel, Field
from typing import List
from datatypes import ClassifiedMessage, Conversation


class Scenario(BaseModel):
    initial_state: List[Conversation]
    new_message: ClassifiedMessage
    expected_state: List[Conversation]
