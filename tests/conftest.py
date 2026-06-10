import os

# Set required env vars before any module is imported during collection.
os.environ.setdefault("SERVICE_BUS_CONNECTION_STRING", "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=dGVzdA==")
os.environ.setdefault("SERVICE_BUS_QUEUE_NAME", "test-queue")
os.environ.setdefault("BACKEND_BASE_URL", "http://localhost:8000")
os.environ.setdefault("BACKEND_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-10-21")
os.environ.setdefault("WEBPUBSUB_CONNECTION_STRING", "Endpoint=https://test.webpubsub.azure.com;AccessKey=dGVzdA==;Version=1.0;")
os.environ.setdefault("WEBPUBSUB_HUB", "projects")
