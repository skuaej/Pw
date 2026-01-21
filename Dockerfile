# Base Image: Python 3.10 (Lightweight version)
FROM python:3.10-slim

# Environment Variables set karo
# PYTHONUNBUFFERED=1 ka matlab logs turant dikhenge (Koyeb logs ke liye zaroori)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# System Dependencies update aur install karo
# ffmpeg aur git zaroori ho sakte hain media processing ke liye
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Working Directory set karo
WORKDIR /app

# Sabse pehle requirements copy karo (Caching ke liye fast hota hai)
COPY requirements.txt .

# Python Libraries install karo
RUN pip install --no-cache-dir -r requirements.txt

# Baaki saara code copy karo
COPY . .

# Port Expose karo (Documentation ke liye, Koyeb waise bhi detect kar leta hai)
EXPOSE 8080

# Bot start karne ka command
CMD ["python", "app.py"]
