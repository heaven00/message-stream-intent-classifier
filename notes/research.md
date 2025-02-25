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

**Update (25th Feb)**
https://arxiv.org/pdf/2110.12646v2 - this introduces a MLP (multi layer perceptron) over Bert style models to 

> Our method only requires one additional MLP
> layer attached to the architecture of Li et al. (2020)
> to train on the entangled response selection task,
> hence it is trivial to swap the trained model into a
> production environment. Suppose a dialogue dis-
> entanglement system (Li et al., 2020) is already up
> and running:
> 1. Train a BERT model on the entangled re-
>    sponse selection task (§2.1) with attention su-
>    pervision loss (§3.4). This is also the multi-
>    task loss depicted in Figure 2.
> 2. Copy the weight of the pretrained model into
>    the existing architecture (Li et al., 2020).
> 3. Perform zero-shot dialogue disentanglement
>    (zero-shot section of Table 2) right away, or
>    finetune the model further when more labeled
>    data becomes available (few-shot section of
>    Table 2).
> This strategy will be useful especially when we
> want to bootstrap a system with limited and expen-
> sive labeled data.

It does make certain assumption about the underlying system in place which would need more looking into, but can wait for now.

## Alternative approach

build a binary classifier to say whether there is intent to meet on a virtual call or not
- generate dummy conversational data using LLMs for these conversations
- build a classifier
- test it out on the stream

this approach focuses only on the problem at hand and narrows down the scope of things to be done. 

