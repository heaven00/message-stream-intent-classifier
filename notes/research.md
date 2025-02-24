# Detecting Conversations

This problem is called **conversation disentanglement**

- https://paperswithcode.com/task/conversation-disentanglement
- dataset: https://github.com/jkkummerfeld/irc-disentanglement 


## Overall understanding of conversation disentanglement

- we are looking at message pairs and classifying whether they are part of the same converation or not
- though how do they handle delayed async messages? more reading required


- Looking at the data some of the patterns for disentanglement
    - indivduals usually reply to particular users
    - the ones starting a conversations usually start with hi etc and then ask a question

Session -> a conversation that is going on

Whenever a message flows in, it can either 
- start a new session
- add to an existing session
    - when adding they usually mention one of the users in the session

people do type the whole message in parts, so need to take that into account

## Alternative approach

build a binary classifier to say whether there is intent to meet on a virtual call or not
- generate dummy conversational data using LLMs for these conversations
- build a classifier
- test it out on the stream

this approach focuses only on the problem at hand and narrows down the scope of things to be done. 

