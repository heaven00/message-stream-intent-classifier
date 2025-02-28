#!/bin/bash

# Create required directories if they don't exist
mkdir -p model results
# bert classifier folder if its not present
mkdir -p model/bert_classifier_v1

S3_BASE_URL="https://message-stream-classifier.s3.ca-central-1.amazonaws.com/model/bert-classifier-v1/"

# if the required files are not present download them
for file in "config.json" "model.safetensors" "training_args.bin"; do
    local_path="model/bert_classifier_v1/$file"
    s3_url="${S3_BASE_URL}/$file"
    
    if [ ! -f "$local_path" ]; then
        echo "Downloading $file from S3..."
        wget -q -O "$local_path" "$s3_url"
        if [ $? -ne 0 ]; then
            echo "Error downloading $file"
            exit 1
        fi
    else
        echo "$file already exists, skipping download"
    fi
done

# Check if container exists and remove it if necessary
if [ "$(docker ps -aq -f name=message-stream-classifier)" ]; then
    echo "Removing existing container..."
    docker rm -f message-stream-classifier
fi

# Build and run the container
echo "Building image..."
docker build -t assignment/message-stream-classifier .

echo "Running container..."
docker run -it --rm \
    -v $(pwd)/model:/app/model \
    -v $(pwd)/results:/app/results \
    --name message-stream-classifier \
    assignment/message-stream-classifier