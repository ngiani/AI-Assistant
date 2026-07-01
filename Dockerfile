#Start from ubuntu image
FROM ubuntu:latest

#Set dest work dir
WORKDIR /app

#Copy python requirements 
COPY requirements.txt .

#Install python and create virtual environment
RUN apt-get update && apt-get install -y python3.14 python3-pip python3.14-venv && \
    python3.14 -m venv /opt/venv

#Install requirements in virtual environment
ENV PATH="/opt/venv/bin:$PATH"
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

#Install curl and zstd for ollama install script
RUN apt-get install -y curl zstd

#Install ollama
RUN curl -fsSL https://ollama.com/install.sh | sh



#Copy everything inside folder to dest folder
COPY . .

#Note: Model pulling (ollama run qwen3:8b) should happen at runtime, not during build
CMD [ "python3.14", "ai_chatbot.py" ]
