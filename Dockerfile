# Utiliser une image Python 3.12 officielle et légère
FROM python:3.12-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier d'abord le fichier des dépendances (pour profiter du cache Docker)
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le reste du code de votre bot
COPY . .

# (Optionnel mais utile) Créer un utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Définir la variable d'environnement (elle sera remplacée par celle de Render)
ENV DISCORD_TOKEN=${DISCORD_TOKEN}

# La commande pour lancer le bot
CMD ["python", "bot.py"]
