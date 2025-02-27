# What pipeline do I need to build

For the ingestion pipeline, I first want to understand the throughput of the websocket .i.e. for what scale I am building for.


a simple and non elegant way to get ballpark
```python
    async with websockets.connect(url) as websocket:
        timestamps = []
        n = 300.0
        decode = True
        while len(timestamps) < n:
            t1 = datetime.now().timestamp()
            await websocket.recv(decode=decode)
            t2 = datetime.now().timestamp()
            timestamps.append((t2 - t1) * 1000)
        avg_ms = sum(timestamps) / len(timestamps)
        print(f"Decode: {decode}")
        print(f"Average time taken for 1 message from a sample of {n} messages:", avg_ms, 'ms')
        time_seconds = avg_ms / 1000
        print(f"Messages per second:", 1 / time_seconds)
```

The numbers

```
Decode: False
Average time taken for 1 message from a sample of 300.0 messages: 88.71140559514363 ms
Messages per second: 11.272507670138229


Decode: True
Average time taken for 1 message from a sample of 300.0 messages: 88.98049354553223 ms
Messages per second: 11.238418221273292
```
decoding did not affect a lot in the sample runs I did and the ballpark is around 10-12 messages per second. So, I just probably need to do a simple a pipeline

validate message -> clean -> async write to results folder

Ideally it would be nice to separate out the model in a different docker and fast api wrapper so that it becomes easier to scale that part alone as needed but I am going to start with everything together for now.