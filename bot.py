import discord
from discord.ext import commands, tasks
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import config

# Charger les variables d'environnement
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

# Création du bot
bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)

# Variable pour stocker les IDs des salons de stats
stats_category_id = None
stats_channels_ids = {}

class StatsManager:
    def __init__(self):
        self.category_id = None
        self.channels_ids = {}
        self.load_config()
    
    def load_config(self):
        try:
            with open('stats_config.json', 'r') as f:
                data = json.load(f)
                self.category_id = data.get('category_id')
                self.channels_ids = data.get('channels_ids', {})
        except FileNotFoundError:
            pass
    
    def save_config(self):
        with open('stats_config.json', 'w') as f:
            json.dump({
                'category_id': self.category_id,
                'channels_ids': self.channels_ids
            }, f)

stats_manager = StatsManager()

def get_server_stats(guild):
    """Récupère les statistiques du serveur"""
    total_members = guild.member_count
    bots = sum(1 for member in guild.members if member.bot)
    
    # Compter les membres en ligne (humains uniquement)
    online = 0
    for member in guild.members:
        if not member.bot and member.status != discord.Status.offline:
            online += 1
    
    return {
        'total': total_members,
        'bots': bots,
        'online': online
    }

def get_channel_name(stat_type, value):
    """Génère le nom du salon avec la valeur"""
    emojis = {
        'total': '👥',
        'bots': '🤖',
        'online': '🟢'
    }
    
    labels = {
        'total': 'Membres',
        'bots': 'Bots',
        'online': 'En ligne'
    }
    
    emoji = emojis.get(stat_type, '📊')
    label = labels.get(stat_type, stat_type)
    
    return f"{emoji} {label} : {value}"

async def create_stats_channels(guild):
    """Crée la catégorie et les salons de stats"""
    global stats_category_id, stats_channels_ids
    
    # Vérifier si la catégorie existe déjà
    if stats_manager.category_id:
        category = guild.get_channel(stats_manager.category_id)
        if category:
            return category
    
    # Créer la catégorie
    category = await guild.create_category("📊 STATS SERVEUR")
    stats_manager.category_id = category.id
    
    # Créer les 3 salons
    channels_to_create = ['total', 'bots', 'online']
    stats_manager.channels_ids = {}
    
    for stat_type in channels_to_create:
        channel = await guild.create_voice_channel(
            name=get_channel_name(stat_type, 0),
            category=category
        )
        # Rendre le salon privé (optionnel)
        await channel.set_permissions(guild.default_role, connect=False)
        stats_manager.channels_ids[stat_type] = channel.id
    
    stats_manager.save_config()
    return category

async def update_stats_channels(guild):
    """Met à jour les noms des salons avec les nouvelles stats"""
    if not stats_manager.category_id or not stats_manager.channels_ids:
        return
    
    stats = get_server_stats(guild)
    
    for stat_type, channel_id in stats_manager.channels_ids.items():
        channel = guild.get_channel(channel_id)
        if channel:
            value = stats.get(stat_type, 0)
            new_name = get_channel_name(stat_type, value)
            if channel.name != new_name:
                await channel.edit(name=new_name)

@tasks.loop(seconds=config.UPDATE_INTERVAL)
async def update_stats():
    """Tâche automatique pour mettre à jour les noms des salons"""
    for guild in bot.guilds:
        if stats_manager.category_id:
            await update_stats_channels(guild)

@bot.event
async def on_ready():
    print(f"Bot connecté")
    
    # Configuration de l'activité
    activity = discord.Streaming(
        name=config.ACTIVITY_NAME,
        url=config.STREAMING_URL
    )
    await bot.change_presence(activity=activity)
    
    # Charger la configuration et démarrer les mises à jour
    if stats_manager.category_id:
        update_stats.start()
        print("Mise à jour automatique des stats démarrée")

@bot.event
async def on_member_join(member):
    if stats_manager.category_id:
        await update_stats_channels(member.guild)

@bot.event
async def on_member_remove(member):
    if stats_manager.category_id:
        await update_stats_channels(member.guild)

@bot.event
async def on_member_update(before, after):
    if before.status != after.status and stats_manager.category_id:
        await update_stats_channels(after.guild)

@bot.command(name="setupstats")
@commands.has_permissions(administrator=True)
async def setup_stats(ctx):
    """Crée la catégorie et les salons de statistiques"""
    
    # Vérifier si les stats existent déjà
    if stats_manager.category_id:
        category = ctx.guild.get_channel(stats_manager.category_id)
        if category:
            await ctx.send("❌ Les salons de stats existent déjà !")
            return
    
    # Créer les salons
    await ctx.send("🔄 Création des salons...")
    
    try:
        category = await create_stats_channels(ctx.guild)
        await update_stats_channels(ctx.guild)
        
        embed = discord.Embed(
            title="✅ Configuration terminée !",
            description=f"Catégorie **{category.name}** créée avec 3 salons :",
            color=config.COLOR_SUCCESS
        )
        embed.add_field(name="Salons", value="👥 Membres\n🤖 Bots\n🟢 En ligne", inline=True)
        embed.add_field(name="Mise à jour", value=f"Toutes les {config.UPDATE_INTERVAL}s", inline=True)
        
        await ctx.send(embed=embed)
        
        # Démarrer les mises à jour automatiques
        if not update_stats.is_running():
            update_stats.start()
            
    except Exception as e:
        await ctx.send(f"❌ Erreur : {e}")

@bot.command(name="updatestats")
@commands.has_permissions(administrator=True)
async def force_update_stats(ctx):
    """Force la mise à jour immédiate"""
    if not stats_manager.category_id:
        await ctx.send("❌ Utilisez d'abord `!setupstats`")
        return
    
    await update_stats_channels(ctx.guild)
    await ctx.send("✅ Stats mises à jour !")

@bot.command(name="deletestats")
@commands.has_permissions(administrator=True)
async def delete_stats(ctx):
    """Supprime la catégorie et les salons"""
    if not stats_manager.category_id:
        await ctx.send("❌ Rien à supprimer.")
        return
    
    category = ctx.guild.get_channel(stats_manager.category_id)
    if category:
        for channel in category.channels:
            await channel.delete()
        await category.delete()
    
    stats_manager.category_id = None
    stats_manager.channels_ids = {}
    stats_manager.save_config()
    
    await ctx.send("✅ Salons supprimés !")

@bot.command(name="stats")
async def show_stats(ctx):
    """Affiche les stats en message"""
    stats = get_server_stats(ctx.guild)
    
    message = (
        f"**📊 Stats de {ctx.guild.name}**\n"
        f"👥 Membres : {stats['total']}\n"
        f"🤖 Bots : {stats['bots']}\n"
        f"🟢 En ligne : {stats['online']}"
    )
    
    await ctx.send(message)

@bot.command(name="aide")
async def help_command(ctx):
    """Affiche l'aide"""
    embed = discord.Embed(
        title="🤖 Aide",
        description="Commandes disponibles :",
        color=config.COLOR_STATS
    )
    
    embed.add_field(name="!setupstats", value="Crée les salons de stats (Admin)", inline=False)
    embed.add_field(name="!updatestats", value="Met à jour manuellement (Admin)", inline=False)
    embed.add_field(name="!deletestats", value="Supprime les salons (Admin)", inline=False)
    embed.add_field(name="!stats", value="Affiche les stats ici", inline=False)
    embed.add_field(name="!aide", value="Affiche ce message", inline=False)
    
    await ctx.send(embed=embed)

@setup_stats.error
@delete_stats.error
@force_update_stats.error
async def admin_commands_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Permission admin requise !")

# Démarrer le bot
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Erreur: Token non trouvé dans .env")
    else:
        bot.run(TOKEN)