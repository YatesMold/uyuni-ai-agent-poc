# Base Image: openSUSE BCI (Base Container Image) for maximum security and ecosystem alignment
FROM registry.suse.com/bci/python:3.11

# Set working directory
WORKDIR /app

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent logic and main script
COPY agent/ ./agent/
COPY main.py .

# Run the Agent
CMD ["python", "main.py"]
