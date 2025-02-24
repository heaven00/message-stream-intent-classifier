# Understanding the problem statement


### source data
we have a real time stream of text messages from communication applications, the data includes

```
Field: Description
seqid: A unique identifier for the message.
ts: A timestamp, corresponding to the time the message was sent to the channel.
user: The username that has sent the message to the channel.
message: The content of the message itself.
```

### Problem statement
convert messages and conversations to calendar events

> Scattered throughout the stream, will be messages or conversations that can be converted into a calendar event. For example, a conversation participant may propose a meeting for a specific date, possibly a time, and that involves one or more participants. Note that these calendar events may span one or more messages; it should not be expected that they will be self contained in one specific message.

Train a model that will monitor the message stream, and detect conversations that can be converted to calendar events.

The model + code should create events_{id}.json file under results folder that contain the lines that lead to event creation


### Initial thoughts
- The data is not going to be in sequence, since it's a stream of messages and they could be coming in any order
- The data does not contain information to whom the message is being sent, instead the participants can vary.
- This stream, is it just assumed to be a single #channel? `simulating a multi-person conversation in a chat application like Slack or IRC` this is a single multi person conversation that is being emulated so let's assume that for the rest of the process 

### Next steps
get to know the data a bit more run the client.py file and store the data for analysis of the stream
