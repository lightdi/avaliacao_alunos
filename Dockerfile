# Usar imagem base Python leve e oficial
FROM python:3.10-slim

# Definir o diretório de trabalho no container
WORKDIR /app

# Instalar dependências de sistema necessárias para compilação (se necessário)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar apenas os arquivos de dependência primeiro para aproveitar a cache de build do Docker
COPY requirements.txt .

# Instalar as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o código-fonte da aplicação para o container
COPY . .

# Definir variáveis de ambiente padrão para o container
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=8020
ENV FLASK_DEBUG=False

# Expor a porta em que a aplicação rodará
EXPOSE 8020

# Comando para rodar a aplicação
CMD ["python", "app.py"]
