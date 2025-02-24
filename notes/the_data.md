# Capturing data for understanding

`uv run python client.py ws://143.110.238.245:8000/stream > stream_capture.jsonl`

# Notes

- The data seems to be an IRC channel (this brings back memories)
- The text is a mixture of emojis, user_id mentions 
- they are in order, but there are multiple conversations going on and at varying topics .i.e. there is a lot of noise in the data
- There are a lot of conversations, some starting, continuing and dying or someone restarting an older conversation, since this is all asychronous conversation


## Decomposing the problem
- What I need to do is just detect calendar events from the data. 

Idea solution
    - keep track of conversations that are being created, continuing and ending
    - Parse coming messages into these conversations 
    - within these conversations detect calendar events 


Alternative brute force solution
- from the stream of messages detect a message that initiates a calendar event
- This triggers a search through message "around" to create the "Event" and 
