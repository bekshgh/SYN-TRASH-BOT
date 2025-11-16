"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ADVANCED TELEGRAM BOT - FULLY FUNCTIONAL                  ║
║                              Ready to Deploy                                 ║
║                      NOW WITH ANONYMOUS MESSAGES! 👤                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 QUICK SETUP (3 STEPS):

1. Install dependencies:
   pip install aiogram==3.3.0 aiosqlite apscheduler

2. Get your bot token from @BotFather and your user ID from @userinfobot
   Replace the values below (lines 35-36)

3. Run the bot:
   python bot.py

4. Add bot to your group as ADMIN and send /start

═══════════════════════════════════════════════════════════════════════════════

✨ FEATURES:
• /start - Activate bot and see menu
• /stats - Top 10 most active users today + your stats
• /crush - Find your random crush (gender-based)
• /comp @user1 @user2 - Check compatibility
• /prediction - Get daily prediction (once per day)
• /joke - Random joke from database
• /anon - Send anonymous messages (DM only) 👤 NEW!
• /punishment - View/manage punishment leaderboard
• /help - Complete help guide
• /admin - Admin panel (DM only, admin only)

🤖 AUTOMATIC FEATURES:
• Daily stats reset at midnight
• Random "Joker of the Day" at 9 AM
• Joker submits joke → bot posts to group
• Users react 👍 or 👎 to jokes
• 20+ 👍 = joke saved to database
• 20+ 👎 = joker gets punishment point
• Message tracking for statistics
• Custom word counting
• Anonymous messages with cooldown

═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
load_dotenv() 
import random
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Set
from collections import defaultdict
from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram import F
import asyncio

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, MessageReactionUpdated, ReactionTypeEmoji
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ═══════════════════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION - EDIT THESE VALUES
# ═══════════════════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

DATABASE_FILE = "bot_database.db"
GOOD_JOKE_THRESHOLD = 5  # Thumbs up needed to save joke
BAD_JOKE_THRESHOLD = 5   # Thumbs down for punishment

# ═══════════════════════════════════════════════════════════════════════════
# 📊 LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# 💾 DATABASE CLASS - ALL DATA MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

class Database:
    """Complete database handler for the bot"""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_database()
    
    def get_connection(self):
        """Create database connection"""
        return sqlite3.connect(self.db_file)
    
    def init_database(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                gender TEXT DEFAULT 'UNKNOWN',
                daily_messages INTEGER DEFAULT 0,
                last_prediction_date TEXT,
                is_punisher INTEGER DEFAULT 0
            )
        ''')
        
        # Messages tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Predictions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
            )
        ''')
        
        # Jokes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jokes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                author_id INTEGER
            )
        ''')
        
        # Punishments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS punishments (
                user_id INTEGER PRIMARY KEY,
                points INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Daily joker
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS joker_daily (
                date TEXT PRIMARY KEY,
                user_id INTEGER,
                joke_sent INTEGER DEFAULT 0,
                joke_text TEXT,
                message_id INTEGER,
                chat_id INTEGER
            )
        ''')
        
        # Word tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS word_tracking (
                user_id INTEGER,
                date TEXT,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        ''')
        
        # Groups - track where bot is added
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                added_date TEXT
            )
        ''')
        
        # Joke reactions tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS joke_reactions (
                message_id INTEGER,
                chat_id INTEGER,
                user_id INTEGER,
                reaction TEXT,
                PRIMARY KEY (message_id, chat_id, user_id)
            )
        ''')
        
        # Anonymous messages tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS anon_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                chat_id INTEGER,
                message_text TEXT,
                sent_date TEXT,
                FOREIGN KEY (sender_id) REFERENCES users(user_id)
            )
        ''')
        
        conn.commit()
        
        # Insert defaults
        self._set_default_settings(cursor)
        self._insert_default_data(cursor)
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database initialized successfully")
    
    def _set_default_settings(self, cursor):
        """Set default bot settings"""
        defaults = {
            'welcome_text': '''👋 **Welcome to the Ultimate Group Bot!**

I'm here to make your group more fun and interactive!

Use /help to see all my commands.

Let's get started! 🚀''',
            'help_text': '''📚 **Bot Commands Guide**

**📊 Statistics & Fun:**
/stats - View top 10 most active users today
/crush - Find your random crush 💘
/comp @user1 @user2 - Check compatibility between two users

**🔮 Daily Features:**
/prediction - Get your prediction for today (once per day)
/joke - Get a random joke 😄

**👤 Anonymous Messages:**
/anon - Send anonymous messages to the group (use in DM)

**⚠️ Punishment System:**
/punishment - View punishment leaderboard

**ℹ️ Other:**
/help - Show this help message
/start - Restart the bot

**🎭 Daily Joker System:**
Every day at 9 AM, I randomly pick a "Joker of the Day"!
• The joker receives a DM notification
• They must send their best joke to me in private
• I post the joke to the group
• Everyone reacts with 👍 or 👎
• 20+ 👍 = Joke gets saved to database!
• 20+ 👎 = Joker gets punishment points!

**📈 Stats Tracking:**
I track your messages and count how many times you use specific words!

**👨‍💼 Admin Features:**
Admins can access /admin in private chat to:
• Edit bot texts
• Manage predictions and jokes
• Set tracked words
• Manage user genders for crush system
• Manage anonymous messages settings
• View and reset leaderboards

Enjoy using the bot! 🎉''',
            'tracked_word': 'lol',
            'crush_mode': 'opposite',
            'anon_enabled': 'true',
            'anon_group_message': '💬 Use this command in DM with me to send anonymous messages to the group!',
            'anon_dm_instruction': '''📝 **Send Anonymous Message**

To send an anonymous message to the group, use:
`/anon Your message here`

Example:
`/anon This is a secret message!`

Your identity will remain hidden! 🕵️''',
            'anon_prefix': '👤 Anonymous',
            'anon_cooldown': '60',
        }
        
        for key, value in defaults.items():
            cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', 
                          (key, value))
    
    def _insert_default_data(self, cursor):
        """Insert default predictions and jokes"""
        
        # Check if we need to add defaults
        cursor.execute('SELECT COUNT(*) FROM predictions')
        if cursor.fetchone()[0] == 0:
            predictions = [
                "✨ Today you will find something you lost long ago!",
                "🎁 A pleasant surprise awaits you today!",
                "💬 Be careful with your words today - they have special power!",
                "💭 Someone special is thinking about you right now!",
                "🍀 Today is your lucky day! Take that risk!",
                "📱 An old friend will reach out to you soon!",
                "💪 Your hard work will finally pay off this week!",
                "🎭 A mysterious opportunity will present itself today!",
                "🔮 Trust your intuition today - it won't fail you!",
                "⏰ Something you've been waiting for will finally happen!",
                "🌟 New opportunities are coming your way!",
                "💖 Love is in the air today!",
                "🎯 Your goals are closer than you think!",
                "🌈 After the storm comes the rainbow!",
                "🔥 Your passion will ignite something amazing today!"
            ]
            for pred in predictions:
                cursor.execute('INSERT INTO predictions (text) VALUES (?)', (pred,))
        
        cursor.execute('SELECT COUNT(*) FROM jokes')
        if cursor.fetchone()[0] == 0:
            jokes = [
                "Why don't scientists trust atoms? Because they make up everything! 😄",
                "I told my wife she was drawing her eyebrows too high. She looked surprised. 😮",
                "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
                "I'm reading a book about anti-gravity. It's impossible to put down! 📚",
                "Why don't eggs tell jokes? They'd crack each other up! 🥚",
                "What do you call a bear with no teeth? A gummy bear! 🐻",
                "Why did the math book look sad? Because it had too many problems! 📖",
                "What do you call a fake noodle? An impasta! 🍝",
                "Why can't you hear a pterodactyl go to the bathroom? Because the 'P' is silent! 🦕",
                "What did the ocean say to the beach? Nothing, it just waved! 🌊"
            ]
            for joke in jokes:
                cursor.execute('INSERT INTO jokes (text, author_id) VALUES (?, ?)', 
                             (joke, None))

# Initialize database
db = Database(DATABASE_FILE)

# ═══════════════════════════════════════════════════════════════════════════
# 🛠️ HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_setting(key: str) -> Optional[str]:
    """Get setting value"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_setting(key: str, value: str):
    """Update setting"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', 
                  (key, value))
    conn.commit()
    conn.close()

def track_user(user_id: int, username: str, first_name: str):
    """Track user activity"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, daily_messages)
        VALUES (?, ?, ?, 
            COALESCE((SELECT daily_messages FROM users WHERE user_id = ?), 0) + 1)
    ''', (user_id, username, first_name, user_id))
    conn.commit()
    conn.close()

def track_message(user_id: int, chat_id: int):
    """Track message for stats"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (user_id, chat_id, date) VALUES (?, ?, ?)',
                   (user_id, chat_id, today))
    conn.commit()
    conn.close()

def track_word(user_id: int, count: int = 1):
    """Track custom word usage"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO word_tracking (user_id, date, count)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET count = count + ?
    ''', (user_id, today, count, count))
    conn.commit()
    conn.close()

def track_group(chat_id: int, title: str):
    """Track group where bot is added"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO groups (chat_id, title, added_date)
        VALUES (?, ?, ?)
    ''', (chat_id, title, today))
    conn.commit()
    conn.close()
    logger.info(f"📝 Group tracked: {title} (ID: {chat_id})")

def get_all_groups() -> List[tuple]:
    """Get all groups bot is in"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, title FROM groups')
    results = cursor.fetchall()
    conn.close()
    return results

def get_daily_stats(chat_id: int) -> List[tuple]:
    """Get top 10 users by messages today"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, COUNT(m.id) as msg_count
        FROM users u
        JOIN messages m ON u.user_id = m.user_id
        WHERE m.date = ? AND m.chat_id = ?
        GROUP BY u.user_id
        ORDER BY msg_count DESC
        LIMIT 10
    ''', (today, chat_id))
    results = cursor.fetchall()
    conn.close()
    return results

def get_user_stats(user_id: int, chat_id: int) -> Dict:
    """Get user's stats for today"""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) FROM messages
        WHERE user_id = ? AND chat_id = ? AND date = ?
    ''', (user_id, chat_id, today))
    msg_count = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT count FROM word_tracking
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))
    word_result = cursor.fetchone()
    word_count = word_result[0] if word_result else 0
    
    conn.close()
    return {'messages': msg_count, 'words': word_count}

def reset_daily_stats():
    """Reset daily statistics"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET daily_messages = 0')
    conn.commit()
    conn.close()
    logger.info("📊 Daily stats reset")

def get_chat_users(chat_id: int, gender_filter: Optional[str] = None) -> List[tuple]:
    """Get users from chat, optionally filtered by gender"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    if gender_filter:
        cursor.execute('''
            SELECT DISTINCT u.user_id, u.username, u.first_name, u.gender
            FROM users u
            JOIN messages m ON u.user_id = m.user_id
            WHERE m.chat_id = ? AND u.gender = ?
        ''', (chat_id, gender_filter))
    else:
        cursor.execute('''
            SELECT DISTINCT u.user_id, u.username, u.first_name, u.gender
            FROM users u
            JOIN messages m ON u.user_id = m.user_id
            WHERE m.chat_id = ?
        ''', (chat_id,))
    
    results = cursor.fetchall()
    conn.close()
    return results

def set_user_gender(user_id: int, gender: str):
    """Set user gender"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET gender = ? WHERE user_id = ?', (gender, user_id))
    conn.commit()
    conn.close()

def add_punishment(user_id: int, points: int = 1):
    """Add punishment points"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO punishments (user_id, points)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET points = points + ?
    ''', (user_id, points, points))
    conn.commit()
    conn.close()

def get_punishment_leaderboard() -> List[tuple]:
    """Get punishment leaderboard"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, p.points
        FROM punishments p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.points > 0
        ORDER BY p.points DESC
        LIMIT 10
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def reset_punishment_leaderboard():
    """Reset all punishments"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM punishments')
    conn.commit()
    conn.close()

def track_joke_reaction(message_id: int, chat_id: int, user_id: int, reaction: str):
    """Track reaction on joke"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO joke_reactions 
        (message_id, chat_id, user_id, reaction)
        VALUES (?, ?, ?, ?)
    ''', (message_id, chat_id, user_id, reaction))
    conn.commit()
    conn.close()

def get_joke_reaction_counts(message_id: int, chat_id: int) -> Dict[str, int]:
    """Get reaction counts for a joke"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT reaction, COUNT(*) as count
        FROM joke_reactions
        WHERE message_id = ? AND chat_id = ?
        GROUP BY reaction
    ''', (message_id, chat_id))
    results = cursor.fetchall()
    conn.close()
    
    counts = {'👍': 0, '👎': 0}
    for reaction, count in results:
        counts[reaction] = count
    return counts

# Anonymous messages helper functions
anon_cooldowns = {}

def can_send_anon_message(user_id: int) -> tuple:
    """Check if user can send anon message (cooldown check)"""
    cooldown_seconds = int(get_setting('anon_cooldown') or 60)
    
    if user_id in anon_cooldowns:
        last_time = anon_cooldowns[user_id]
        elapsed = (datetime.now() - last_time).total_seconds()
        
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed)
            return False, remaining
    
    return True, 0

def record_anon_message(user_id: int, chat_id: int, message_text: str):
    """Record anonymous message in database"""
    today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO anon_messages (sender_id, chat_id, message_text, sent_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, chat_id, message_text, today))
    conn.commit()
    conn.close()
    
    anon_cooldowns[user_id] = datetime.now()

def get_anon_stats() -> Dict:
    """Get anonymous message statistics for admin"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM anon_messages')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT sender_id) FROM anon_messages')
    unique_senders = cursor.fetchone()[0]
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM anon_messages WHERE sent_date LIKE ?', (f'{today}%',))
    today_count = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT u.username, u.first_name, COUNT(*) as count
        FROM anon_messages a
        JOIN users u ON a.sender_id = u.user_id
        GROUP BY a.sender_id
        ORDER BY count DESC
        LIMIT 5
    ''')
    top_senders = cursor.fetchall()
    
    conn.close()
    
    return {
        'total': total,
        'unique_senders': unique_senders,
        'today': today_count,
        'top_senders': top_senders
    }

# ═══════════════════════════════════════════════════════════════════════════
# 🤖 BOT INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# FSM States
class AdminStates(StatesGroup):
    waiting_for_text_edit = State()
    waiting_for_prediction = State()
    waiting_for_joke = State()
    waiting_for_word = State()
    waiting_for_joke_submission = State()
    waiting_for_gender_set = State()
    waiting_for_prediction_delete = State()
    waiting_for_anon_prefix = State()
    waiting_for_anon_cooldown = State()
    waiting_for_anon_instruction = State()
    waiting_for_anon_group_msg = State()

# ═══════════════════════════════════════════════════════════════════════════
# 📬 COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message):
    """### START COMMAND ###"""
    
    # Track user
    if message.from_user:
        track_user(
            message.from_user.id,
            message.from_user.username or "Unknown",
            message.from_user.first_name or "Unknown"
        )
    
    # Track group if in group
    if message.chat.type in ['group', 'supergroup']:
        track_group(message.chat.id, message.chat.title or "Unknown Group")
    
    welcome_text = get_setting('welcome_text')
    await message.reply(welcome_text, parse_mode="Markdown")
    logger.info(f"✅ /start from user {message.from_user.id}")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """### HELP COMMAND ###"""
    help_text = get_setting('help_text')
    await message.reply(help_text, parse_mode="Markdown")
    logger.info(f"📚 /help from user {message.from_user.id}")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """### STATS COMMAND ###"""
    
    if message.chat.type == 'private':
        await message.reply("❌ This command only works in groups!")
        return
    
    top_users = get_daily_stats(message.chat.id)
    
    if not top_users:
        await message.reply("📊 No messages tracked today yet! Start chatting!")
        return
    
    stats_text = "📊 **Top 10 Most Active Users Today:**\n\n"
    
    for idx, (user_id, username, first_name, msg_count) in enumerate(top_users, 1):
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = f"{idx}."
        
        user_mention = f"@{username}" if username else first_name
        stats_text += f"{medal} {user_mention} - **{msg_count}** messages\n"
    
    # Add user's personal stats
    if message.from_user:
        user_stats = get_user_stats(message.from_user.id, message.chat.id)
        tracked_word = get_setting('tracked_word')
        stats_text += f"\n{'─' * 30}\n"
        stats_text += f"👤 **Your Stats Today:**\n"
        stats_text += f"💬 Messages: **{user_stats['messages']}**\n"
        stats_text += f"🔤 '{tracked_word}' count: **{user_stats['words']}**"
    
    await message.reply(stats_text, parse_mode="Markdown")
    logger.info(f"📊 /stats from user {message.from_user.id}")

@router.message(Command("crush"))
async def cmd_crush(message: Message):
    """### CRUSH COMMAND ###"""
    
    if message.chat.type == 'private':
        await message.reply("❌ This command only works in groups!")
        return
    
    if not message.from_user:
        return
    
    chat_users = get_chat_users(message.chat.id)
    
    if len(chat_users) < 2:
        await message.reply("❌ Not enough users in the chat to find a crush!")
        return
    
    # Get user's gender
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT gender FROM users WHERE user_id = ?', (message.from_user.id,))
    result = cursor.fetchone()
    user_gender = result[0] if result else 'UNKNOWN'
    conn.close()
    
    # Filter based on crush mode
    crush_mode = get_setting('crush_mode')
    potential_crushes = []
    
    for user_id, username, first_name, gender in chat_users:
        if user_id == message.from_user.id:
            continue
        
        if crush_mode == 'opposite':
            if (user_gender == 'MALE' and gender == 'FEMALE') or \
               (user_gender == 'FEMALE' and gender == 'MALE') or \
               user_gender == 'UNKNOWN' or gender == 'UNKNOWN':
                potential_crushes.append((user_id, username, first_name))
        else:  # same gender
            if user_gender == gender or user_gender == 'UNKNOWN' or gender == 'UNKNOWN':
                potential_crushes.append((user_id, username, first_name))
    
    if not potential_crushes:
        await message.reply(
            "❌ No suitable crushes found!\n"
            "💡 Admin can set user genders via /admin panel."
        )
        return
    
    # Pick random crush
    crush = random.choice(potential_crushes)
    crush_mention = f"@{crush[1]}" if crush[1] else crush[2]
    
    messages = [
        f"💘 Your crush is: {crush_mention}! Go talk to them!",
        f"💕 Cupid has spoken! Your crush is: {crush_mention}!",
        f"💖 Love is in the air! Your crush is: {crush_mention}!",
        f"💝 The stars have aligned! Your crush is: {crush_mention}!",
        f"💗 Your perfect match: {crush_mention}! Don't be shy!",
    ]
    
    await message.reply(random.choice(messages))
    logger.info(f"💘 /crush: {message.from_user.id} -> {crush[0]}")

@router.message(Command("comp"))
async def cmd_comp(message: Message):
    """### COMPATIBILITY COMMAND ###"""
    
    # Parse mentions or text after command
    args = message.text.split()[1:] if message.text else []
    
    if len(args) < 2:
        await message.reply(
            "❌ Please mention two users!\n"
            "**Example:** /comp @user1 @user2\n"
            "**or:** /comp Alice Bob"
        )
        return
    
    user1 = args[0]
    user2 = args[1]
    
    # Calculate compatibility
    compatibility = random.randint(0, 100)
    
    # Comments based on compatibility
    if compatibility >= 90:
        comment = "🔥 Perfect match! Soulmates detected!"
        emoji = "💯"
    elif compatibility >= 75:
        comment = "💕 Excellent chemistry! Great together!"
        emoji = "❤️"
    elif compatibility >= 60:
        comment = "💗 Very good compatibility!"
        emoji = "😊"
    elif compatibility >= 45:
        comment = "👍 Good potential!"
        emoji = "🙂"
    elif compatibility >= 30:
        comment = "🤔 Could work with some effort..."
        emoji = "😐"
    elif compatibility >= 15:
        comment = "😬 Not the best match..."
        emoji = "😕"
    else:
        comment = "💔 Better as friends..."
        emoji = "😢"
    
    # Create a fancy bar
    filled = int(compatibility / 10)
    bar = "█" * filled + "░" * (10 - filled)
    
    await message.reply(
        f"💝 **Compatibility Check**\n\n"
        f"{user1} 💫 {user2}\n\n"
        f"{bar} **{compatibility}%** {emoji}\n\n"
        f"{comment}",
        parse_mode="Markdown"
    )
    logger.info(f"💝 /comp: {user1} + {user2} = {compatibility}%")

@router.message(Command("prediction"))
async def cmd_prediction(message: Message):
    """### PREDICTION COMMAND ###"""
    
    if not message.from_user:
        return
    
    # Check if already got prediction today
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT last_prediction_date FROM users WHERE user_id = ?',
                   (message.from_user.id,))
    result = cursor.fetchone()
    
    if result and result[0] == today:
        await message.reply(
            "🔮 You've already received your prediction for today!\n"
            "Come back tomorrow for a new one! ✨"
        )
        conn.close()
        return
    
    # Get random prediction
    cursor.execute('SELECT text FROM predictions ORDER BY RANDOM() LIMIT 1')
    prediction = cursor.fetchone()
    
    if not prediction:
        await message.reply("❌ No predictions available! Contact admin.")
        conn.close()
        return
    
    # Update last prediction date
    cursor.execute('UPDATE users SET last_prediction_date = ? WHERE user_id = ?',
                   (today, message.from_user.id))
    conn.commit()
    conn.close()
    
    await message.reply(
        f"🔮 **Your Prediction for Today:**\n\n{prediction[0]}\n\n"
        f"✨ Come back tomorrow for a new prediction!",
        parse_mode="Markdown"
    )
    logger.info(f"🔮 /prediction from user {message.from_user.id}")

@router.message(Command("joke"))
async def cmd_joke(message: Message):
    """### JOKE COMMAND ###"""
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT text FROM jokes ORDER BY RANDOM() LIMIT 1')
    joke = cursor.fetchone()
    conn.close()
    
    if not joke:
        await message.reply("❌ No jokes available! Try again later.")
        return
    
    await message.reply(f"😄 {joke[0]}")
    logger.info(f"😄 /joke from user {message.from_user.id}")

@router.message(Command("punishment"))
async def cmd_punishment(message: Message):
    """### PUNISHMENT COMMAND ###"""
    
    if message.chat.type == 'private':
        await message.reply("❌ This command only works in groups!")
        return
    
    leaderboard = get_punishment_leaderboard()
    
    if not leaderboard:
        text = "😇 **Punishment Leaderboard**\n\nNo punishments recorded yet!\nEveryone is behaving perfectly! ✨"
    else:
        text = "⚠️ **Punishment Leaderboard**\n\nWall of Shame:\n\n"
        for idx, (user_id, username, first_name, points) in enumerate(leaderboard, 1):
            user_mention = f"@{username}" if username else first_name
            if idx == 1:
                emoji = "🥇"
            elif idx == 2:
                emoji = "🥈"
            elif idx == 3:
                emoji = "🥉"
            else:
                emoji = "💀"
            text += f"{emoji} {user_mention} - **{points}** point(s)\n"
    
    # Check if user is punisher or admin
    is_authorized = False
    if message.from_user:
        if message.from_user.id == ADMIN_ID:
            is_authorized = True
        else:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT is_punisher FROM users WHERE user_id = ?', 
                          (message.from_user.id,))
            result = cursor.fetchone()
            is_authorized = result and result[0] == 1
            conn.close()
    
    # Add buttons
    buttons = []
    if is_authorized:
        buttons.append([InlineKeyboardButton(
            text="🔄 Reset Leaderboard", 
            callback_data="punishment_reset"
        )])
    
    if message.from_user and message.from_user.id == ADMIN_ID:
        buttons.append([InlineKeyboardButton(
            text="👮 Manage Punishers", 
            callback_data="punishment_manage"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    
    await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)
    logger.info(f"⚠️ /punishment from user {message.from_user.id}")

@router.message(Command("anon"))
async def cmd_anon(message: Message):
    """### ANONYMOUS MESSAGE COMMAND ###"""
    
    # Check if feature is enabled
    if get_setting('anon_enabled') != 'true':
        await message.reply("❌ Anonymous messages are currently disabled by admin.")
        return
    
    # If used in group, redirect to DM
    if message.chat.type in ['group', 'supergroup']:
        group_msg = get_setting('anon_group_message')
        await message.reply(group_msg)
        logger.info(f"📢 /anon used in group by {message.from_user.id}")
        return
    
    # Must be in DM
    if message.chat.type != 'private':
        return
    
    # Check if user provided a message
    message_text = message.text.replace('/anon', '').strip()
    
    if not message_text:
        # Show instructions
        instruction = get_setting('anon_dm_instruction')
        await message.reply(instruction, parse_mode="Markdown")
        return
    
    # Check cooldown
    can_send, remaining = can_send_anon_message(message.from_user.id)
    
    if not can_send:
        await message.reply(
            f"⏳ **Cooldown Active**\n\n"
            f"Please wait {remaining} seconds before sending another anonymous message.",
            parse_mode="Markdown"
        )
        return
    
    # Get target chat (first group)
    groups = get_all_groups()
    if not groups:
        await message.reply(
            "❌ No groups available!\n"
            "The bot must be added to at least one group first."
        )
        return
    
    target_chat = groups[0][0]
    
    # Send anonymous message to group
    try:
        prefix = get_setting('anon_prefix') or '👤 Anonymous'
        
        anon_text = f"**{prefix}:**\n\n{message_text}"
        
        await bot.send_message(
            target_chat,
            anon_text,
            parse_mode="Markdown"
        )
        
        # Record in database
        record_anon_message(message.from_user.id, target_chat, message_text)
        
        # Confirm to sender
        await message.reply(
            "✅ **Message Sent!**\n\n"
            "Your anonymous message has been posted to the group! 🕵️",
            parse_mode="Markdown"
        )
        
        logger.info(f"📨 Anonymous message sent by {message.from_user.id} to {target_chat}")
        
    except Exception as e:
        logger.error(f"Failed to send anon message: {e}")
        await message.reply(
            "❌ Failed to send message!\n"
            "Please make sure the bot is still in the group and has proper permissions."
        )

# ═══════════════════════════════════════════════════════════════════════════
# 👨‍💼 ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """### ADMIN PANEL ###"""
    
    if message.chat.type != 'private':
        await message.reply("❌ Admin panel only works in private chat!")
        return
    
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ You don't have access to the admin panel!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Edit Texts", callback_data="admin_texts")],
        [InlineKeyboardButton(text="🔮 Manage Predictions", callback_data="admin_predictions")],
        [InlineKeyboardButton(text="😄 Manage Jokes", callback_data="admin_jokes")],
        [InlineKeyboardButton(text="🔤 Set Tracked Word", callback_data="admin_word")],
        [InlineKeyboardButton(text="👥 Manage Genders", callback_data="admin_genders")],
        [InlineKeyboardButton(text="👤 Anonymous Messages", callback_data="admin_anon")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings")],
    ])
    
    await message.reply(
        "🔧 **Admin Control Panel**\n\n"
        "Select an option to manage:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ═══════════════════════════════════════════════════════════════════════════
# 👤 ANONYMOUS MESSAGES ADMIN CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_anon")
async def admin_anon_menu(callback: CallbackQuery):
    """Anonymous messages management menu"""
    
    enabled = get_setting('anon_enabled') == 'true'
    prefix = get_setting('anon_prefix') or '👤 Anonymous'
    cooldown = get_setting('anon_cooldown') or '60'
    
    stats = get_anon_stats()
    
    status_emoji = "✅" if enabled else "❌"
    
    text = f"👤 **Anonymous Messages Management**\n\n"
    text += f"**Status:** {status_emoji} {'Enabled' if enabled else 'Disabled'}\n"
    text += f"**Prefix:** {prefix}\n"
    text += f"**Cooldown:** {cooldown} seconds\n\n"
    text += f"📊 **Statistics:**\n"
    text += f"• Total messages: {stats['total']}\n"
    text += f"• Unique senders: {stats['unique_senders']}\n"
    text += f"• Today: {stats['today']}\n\n"
    
    if stats['top_senders']:
        text += f"**Top Anonymous Senders:**\n"
        for username, first_name, count in stats['top_senders']:
            name = f"@{username}" if username else first_name
            text += f"• {name}: {count} messages\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'🔴 Disable' if enabled else '🟢 Enable'}", 
            callback_data="anon_toggle"
        )],
        [InlineKeyboardButton(text="✏️ Edit Prefix", callback_data="anon_edit_prefix")],
        [InlineKeyboardButton(text="⏳ Set Cooldown", callback_data="anon_edit_cooldown")],
        [InlineKeyboardButton(text="📝 Edit Instructions", callback_data="anon_edit_instruction")],
        [InlineKeyboardButton(text="💬 Edit Group Message", callback_data="anon_edit_group_msg")],
        [InlineKeyboardButton(text="📊 View All Messages", callback_data="anon_view_all")],
        [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="admin_back")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "anon_toggle")
async def anon_toggle(callback: CallbackQuery):
    """Toggle anonymous messages on/off"""
    current = get_setting('anon_enabled')
    new_value = 'false' if current == 'true' else 'true'
    update_setting('anon_enabled', new_value)
    
    status = "enabled" if new_value == 'true' else "disabled"
    await callback.answer(f"✅ Anonymous messages {status}!", show_alert=True)
    await admin_anon_menu(callback)
    logger.info(f"👤 Anonymous messages {status}")

@router.callback_query(F.data == "anon_edit_prefix")
async def anon_edit_prefix_start(callback: CallbackQuery, state: FSMContext):
    """Start editing anonymous message prefix"""
    await state.set_state(AdminStates.waiting_for_anon_prefix)
    
    current = get_setting('anon_prefix') or '👤 Anonymous'
    
    await callback.message.edit_text(
        f"✏️ **Edit Anonymous Prefix**\n\n"
        f"**Current prefix:** {current}\n\n"
        f"Send me the new prefix (or /cancel):\n\n"
        f"Examples:\n"
        f"• 👤 Anonymous\n"
        f"• 🕵️ Secret Messenger\n"
        f"• 👻 Ghost\n"
        f"• 🎭 Mystery Person",
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_anon_prefix)
async def anon_edit_prefix_finish(message: Message, state: FSMContext):
    """Save new anonymous prefix"""
    if message.text == "/cancel":
        await state.clear()
        await message.reply("❌ Cancelled.")
        return
    
    update_setting('anon_prefix', message.text)
    await state.clear()
    
    await message.reply(
        f"✅ Anonymous prefix updated to:\n{message.text}\n\n"
        f"Use /admin to return to admin panel."
    )
    logger.info(f"✏️ Anon prefix updated to: {message.text}")

@router.callback_query(F.data == "anon_edit_cooldown")
async def anon_edit_cooldown_start(callback: CallbackQuery, state: FSMContext):
    """Start editing cooldown"""
    await state.set_state(AdminStates.waiting_for_anon_cooldown)
    
    current = get_setting('anon_cooldown') or '60'
    
    await callback.message.edit_text(
        f"⏳ **Set Cooldown Period**\n\n"
        f"**Current cooldown:** {current} seconds\n\n"
        f"Send me the new cooldown in seconds (or /cancel):\n\n"
        f"Examples:\n"
        f"• 30 - 30 seconds\n"
        f"• 60 - 1 minute\n"
        f"• 300 - 5 minutes\n"
        f"• 0 - No cooldown",
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_anon_cooldown)
async def anon_edit_cooldown_finish(message: Message, state: FSMContext):
    """Save new cooldown"""
    if message.text == "/cancel":
        await state.clear()
        await message.reply("❌ Cancelled.")
        return
    
    try:
        cooldown = int(message.text)
        if cooldown < 0:
            await message.reply("❌ Cooldown must be 0 or positive!")
            return
        
        update_setting('anon_cooldown', str(cooldown))
        await state.clear()
        
        await message.reply(
            f"✅ Cooldown set to {cooldown} seconds!\n\n"
            f"Use /admin to return to admin panel."
        )
        logger.info(f"⏳ Anon cooldown set to: {cooldown}")
    except ValueError:
        await message.reply("❌ Please send a valid number!")

@router.callback_query(F.data == "anon_edit_instruction")
async def anon_edit_instruction_start(callback: CallbackQuery, state: FSMContext):
    """Start editing DM instructions"""
    await state.set_state(AdminStates.waiting_for_anon_instruction)
    
    current = get_setting('anon_dm_instruction')
    
    await callback.message.edit_text(
        f"📝 **Edit DM Instructions**\n\n"
        f"**Current instructions:**\n{current}\n\n"
        f"{'─' * 30}\n\n"
        f"Send me the new instructions (or /cancel):",
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_anon_instruction)
async def anon_edit_instruction_finish(message: Message, state: FSMContext):
    """Save new instructions"""
    if message.text == "/cancel":
        await state.clear()
        await message.reply("❌ Cancelled.")
        return
    
    update_setting('anon_dm_instruction', message.text)
    await state.clear()
    
    await message.reply(
        f"✅ DM instructions updated!\n\n"
        f"Use /admin to return to admin panel."
    )

@router.callback_query(F.data == "anon_edit_group_msg")
async def anon_edit_group_msg_start(callback: CallbackQuery, state: FSMContext):
    """Start editing group message"""
    await state.set_state(AdminStates.waiting_for_anon_group_msg)
    
    current = get_setting('anon_group_message')
    
    await callback.message.edit_text(
        f"💬 **Edit Group Message**\n\n"
        f"This message is shown when someone uses /anon in the group.\n\n"
        f"**Current message:**\n{current}\n\n"
        f"{'─' * 30}\n\n"
        f"Send me the new message (or /cancel):",
        parse_mode="Markdown"
    )

@router.message(AdminStates.waiting_for_anon_group_msg)
async def anon_edit_group_msg_finish(message: Message, state: FSMContext):
    """Save new group message"""
    if message.text == "/cancel":
        await state.clear()
        await message.reply("❌ Cancelled.")
        return
    
    update_setting('anon_group_message', message.text)
    await state.clear()
    
    await message.reply(
        f"✅ Group message updated!\n\n"
        f"Use /admin to return to admin panel."
    )

@router.callback_query(F.data == "anon_view_all")
async def anon_view_all(callback: CallbackQuery):
    """View recent anonymous messages (admin only)"""
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.message_text, u.username, u.first_name, a.sent_date
        FROM anon_messages a
        JOIN users u ON a.sender_id = u.user_id
        ORDER BY a.sent_date DESC
        LIMIT 10
    ''')
    messages = cursor.fetchall()
    conn.close()
    
    if not messages:
        text = "📋 **Recent Anonymous Messages**\n\nNo messages yet!"
    else:
        text = "📋 **Last 10 Anonymous Messages:**\n\n"
        for msg_text, username, first_name, date in messages:
            sender = f"@{username}" if username else first_name
            short_msg = msg_text[:50] + "..." if len(msg_text) > 50 else msg_text
            text += f"**From:** {sender}\n"
            text += f"**Date:** {date}\n"
            text += f"**Message:** {short_msg}\n"
            text += "─" * 30 + "\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_anon")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ PUNISHMENT CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "punishment_reset")
async def reset_punishments(callback: CallbackQuery):
    """Reset punishment leaderboard"""
    
    # Verify authorization
    if callback.from_user.id != ADMIN_ID:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT is_punisher FROM users WHERE user_id = ?', 
                      (callback.from_user.id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or result[0] != 1:
            await callback.answer("❌ No permission!", show_alert=True)
            return
    
    reset_punishment_leaderboard()
    await callback.answer("✅ Punishment leaderboard reset!", show_alert=True)
    logger.info(f"🔄 Punishment reset by {callback.from_user.id}")

@router.callback_query(F.data == "punishment_manage")
async def manage_punishers(callback: CallbackQuery):
    """Manage punisher roles"""
    
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name FROM users 
        WHERE is_punisher = 1
    ''')
    punishers = cursor.fetchall()
    conn.close()
    
    if punishers:
        text = "👮 **Current Punishers:**\n\n"
        for user_id, username, first_name in punishers:
            user_name = f"@{username}" if username else first_name
            text += f"• {user_name} (ID: `{user_id}`)\n"
    else:
        text = "👮 **Punisher Management**\n\nNo punishers assigned yet."
    
    text += "\n\nTo manage punishers, use these commands:\n"
    text += "`/setpunisher user_id` - Add punisher\n"
    text += "`/removepunisher user_id` - Remove punisher"
    
    await callback.message.edit_text(text, parse_mode="Markdown")

@router.message(Command("setpunisher"))
async def set_punisher(message: Message):
    """Set a user as punisher"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_id = int(message.text.split()[1])
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_punisher = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await message.reply(f"✅ User {user_id} is now a punisher!")
        logger.info(f"👮 Punisher added: {user_id}")
    except (IndexError, ValueError):
        await message.reply("❌ Usage: /setpunisher user_id")

@router.message(Command("removepunisher"))
async def remove_punisher(message: Message):
    """Remove punisher role"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_id = int(message.text.split()[1])
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_punisher = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await message.reply(f"✅ User {user_id} is no longer a punisher!")
        logger.info(f"👮 Punisher removed: {user_id}")
    except (IndexError, ValueError):
        await message.reply("❌ Usage: /removepunisher user_id")

# ═══════════════════════════════════════════════════════════════════════════
# 🎭 JOKER OF THE DAY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

async def assign_daily_joker(bot_instance: Bot):
    """Assign random user as joker of the day"""
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Check if already assigned
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM joker_daily WHERE date = ?', (today,))
    result = cursor.fetchone()
    
    if result:
        logger.info("🃏 Joker already assigned today")
        conn.close()
        return
    
    # Get active users from last 7 days
    cursor.execute('''
        SELECT DISTINCT user_id FROM messages 
        WHERE date >= date('now', '-7 days')
    ''')
    users = cursor.fetchall()
    
    if not users:
        logger.warning("⚠️ No active users for joker assignment")
        conn.close()
        return
    
    # Pick random user
    joker_id = random.choice(users)[0]
    
    # Save to database
    cursor.execute(
        'INSERT INTO joker_daily (date, user_id, joke_sent) VALUES (?, ?, 0)',
        (today, joker_id)
    )
    conn.commit()
    
    # Get user info
    cursor.execute('SELECT username, first_name FROM users WHERE user_id = ?', (joker_id,))
    user_info = cursor.fetchone()
    conn.close()
    
    if not user_info:
        return
    
    username, first_name = user_info
    user_name = f"@{username}" if username else first_name
    
    try:
        # Notify user in DM
        await bot_instance.send_message(
            joker_id,
            f"🎭 **Congratulations!**\n\n"
            f"You are the **Joker of the Day!** 🌟\n\n"
            f"📝 Your mission:\n"
            f"• Send me your best joke right here in this chat\n"
            f"• I'll post it to the group\n"
            f"• Users will react with 👍 or 👎\n\n"
            f"🎯 **Results:**\n"
            f"• {GOOD_JOKE_THRESHOLD}+ 👍 = Your joke gets saved to the database!\n"
            f"• {BAD_JOKE_THRESHOLD}+ 👎 = You get a punishment point!\n\n"
            f"Good luck! 🍀\n\n"
            f"_Just reply to this message with your joke!_",
            parse_mode="Markdown"
        )
        
        # Notify in all groups
        groups = get_all_groups()
        for chat_id, title in groups:
            try:
                await bot_instance.send_message(
                    chat_id,
                    f"🎭 **Joker of the Day Announcement!**\n\n"
                    f"{user_name} has been chosen as today's joker!\n\n"
                    f"They'll be sending their joke soon... 👀\n"
                    f"Get ready to judge with 👍 or 👎!",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify group {chat_id}: {e}")
        
        logger.info(f"🃏 Daily joker assigned: {joker_id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to notify joker: {e}")

# Joker joke submission handler
@router.message(F.chat.type == 'private', F.text)
async def handle_joker_submission(message: Message):
    """Handle joke submission from joker"""
    
    if not message.from_user or not message.text:
        return
    
    # Check if this is a command
    if message.text.startswith('/'):
        return
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT joke_sent FROM joker_daily WHERE date = ? AND user_id = ?',
        (today, message.from_user.id)
    )
    result = cursor.fetchone()
    
    if not result:
        # Not today's joker
        conn.close()
        return
    
    if result[0] == 1:
        await message.reply("❌ You've already submitted your joke for today!")
        conn.close()
        return
    
    # Save joke
    cursor.execute(
        'UPDATE joker_daily SET joke_sent = 1, joke_text = ? WHERE date = ? AND user_id = ?',
        (message.text, today, message.from_user.id)
    )
    conn.commit()
    conn.close()
    
    await message.reply(
        "✅ **Your joke has been received!**\n\n"
        "I'm posting it to all groups now... 🎭\n"
        "Good luck! 🍀"
    )
    
    # Post joke to all groups
    groups = get_all_groups()
    username = message.from_user.username
    first_name = message.from_user.first_name
    user_name = f"@{username}" if username else first_name
    
    for chat_id, title in groups:
        try:
            sent_msg = await bot.send_message(
                chat_id,
                f"🎭 **Joke of the Day**\n\n"
                f"By: {user_name}\n\n"
                f"{message.text}\n\n"
                f"{'─' * 30}\n"
                f"👍 Like it? | 👎 Not funny?\n"
                f"React to vote!",
                parse_mode="Markdown"
            )
            
            # Save message ID for reaction tracking
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE joker_daily SET message_id = ?, chat_id = ? WHERE date = ? AND user_id = ?',
                (sent_msg.message_id, chat_id, today, message.from_user.id)
            )
            conn.commit()
            conn.close()
            
            logger.info(f"🃏 Joke posted to group {chat_id}")
            
        except Exception as e:
            logger.error(f"Failed to post joke to {chat_id}: {e}")
    
    logger.info(f"🃏 Joke submitted by joker {message.from_user.id}")

# Reaction handler for jokes
@router.message_reaction()
async def handle_joke_reactions(reaction: MessageReactionUpdated):
    """Handle reactions on joker jokes"""
    
    if not reaction.new_reaction:
        return
    
    message_id = reaction.message_id
    chat_id = reaction.chat.id
    user_id = reaction.user.id
    
    # Check if this is a joker joke
    today = datetime.now().strftime('%Y-%m-%d')
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT user_id FROM joker_daily WHERE date = ? AND message_id = ? AND chat_id = ?',
        (today, message_id, chat_id)
    )
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return
    
    joker_id = result[0]
    
    # Extract reaction emoji
    reaction_emoji = None
    for r in reaction.new_reaction:
        if isinstance(r, ReactionTypeEmoji):
            reaction_emoji = r.emoji
            break
    
    if not reaction_emoji or reaction_emoji not in ['👍', '👎']:
        conn.close()
        return
    
    # Track reaction
    track_joke_reaction(message_id, chat_id, user_id, reaction_emoji)
    
    # Get current counts
    counts = get_joke_reaction_counts(message_id, chat_id)
    
    conn.close()
    
    logger.info(f"🎭 Reaction on joke: {reaction_emoji} (👍 {counts['👍']} | 👎 {counts['👎']})")
    
    # Check if thresholds reached
    if counts['👍'] >= GOOD_JOKE_THRESHOLD:
        # Save joke to database
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT joke_text FROM joker_daily WHERE date = ?', (today,))
        joke_text_result = cursor.fetchone()
        
        if joke_text_result:
            joke_text = joke_text_result[0]
            cursor.execute(
                'INSERT OR IGNORE INTO jokes (text, author_id) VALUES (?, ?)',
                (joke_text, joker_id)
            )
            conn.commit()
            
            # Notify
            try:
                await bot.send_message(
                    chat_id,
                    f"🎉 **AMAZING!**\n\n"
                    f"The joke has received {counts['👍']} 👍!\n"
                    f"It's been added to the jokes database! 🌟",
                    parse_mode="Markdown"
                )
                
                await bot.send_message(
                    joker_id,
                    f"🎉 **CONGRATULATIONS!**\n\n"
                    f"Your joke was a hit! 🌟\n"
                    f"It received {counts['👍']} 👍 and has been saved to the database!",
                    parse_mode="Markdown"
                )
            except:
                pass
            
            logger.info(f"🌟 Good joke saved from joker {joker_id}")
        
        conn.close()
    
    elif counts['👎'] >= BAD_JOKE_THRESHOLD:
        # Add punishment
        add_punishment(joker_id, 1)
        
        # Notify
        try:
            await bot.send_message(
                chat_id,
                f"😬 **OH NO!**\n\n"
                f"The joke has received {counts['👎']} 👎!\n"
                f"The joker gets a punishment point! 💀",
                parse_mode="Markdown"
            )
            
            await bot.send_message(
                joker_id,
                f"😢 **OOPS!**\n\n"
                f"Your joke received {counts['👎']} 👎...\n"
                f"You've earned a punishment point. Better luck next time!",
                parse_mode="Markdown"
            )
        except:
            pass
        
        logger.info(f"💀 Bad joke from joker {joker_id} - punishment added")

# ═══════════════════════════════════════════════════════════════════════════
# 📨 MESSAGE TRACKING
# ═══════════════════════════════════════════════════════════════════════════

@router.message(F.chat.type.in_(['group', 'supergroup']), F.text)
async def track_all_messages(message: Message):
    """Track all group messages"""
    
    if not message.from_user or not message.text:
        return
    
    # Track user activity
    track_user(
        message.from_user.id,
        message.from_user.username or "Unknown",
        message.from_user.first_name or "Unknown"
    )
    track_message(message.from_user.id, message.chat.id)
    
    # Track custom word
    tracked_word = get_setting('tracked_word')
    if tracked_word and tracked_word.lower() in message.text.lower():
        word_count = message.text.lower().count(tracked_word.lower())
        track_word(message.from_user.id, word_count)

# ═══════════════════════════════════════════════════════════════════════════
# ⏰ SCHEDULER - DAILY AUTOMATED TASKS
# ═══════════════════════════════════════════════════════════════════════════

async def schedule_daily_tasks():
    """Schedule all automated daily tasks"""
    
    scheduler = AsyncIOScheduler()
    
    # Reset stats at midnight
    scheduler.add_job(
        reset_daily_stats,
        trigger='cron',
        hour=0,
        minute=0,
        id='reset_stats'
    )
    
    # Assign joker at 12 AM
    scheduler.add_job(
        assign_daily_joker,
        trigger='cron',
        hour=12,
        minute=0,
        args=[bot],
        id='assign_joker'
    )
    
    scheduler.start()
    logger.info("⏰ Scheduler started successfully")
    logger.info("📊 Daily stats reset: Every day at 00:00")
    logger.info("🃏 Joker assignment: Every day at 09:00")

# ═══════════════════════════════════════════════════════════════════════════
# 🚀 MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Main function to start the bot"""
    
    # Include router
    dp.include_router(router)
    
    # Start scheduler
    await schedule_daily_tasks()
    
    logger.info("=" * 60)
    logger.info("🤖 BOT STARTING...")
    logger.info("=" * 60)
    logger.info(f"👤 Admin ID: {ADMIN_ID}")
    logger.info(f"💾 Database: {DATABASE_FILE}")
    logger.info(f"👍 Good joke threshold: {GOOD_JOKE_THRESHOLD}")
    logger.info(f"👎 Bad joke threshold: {BAD_JOKE_THRESHOLD}")
    logger.info("=" * 60)
    logger.info("✅ Bot is ready!")
    logger.info("📱 Add bot to your group and make it admin")
    logger.info("💬 Send /start in the group to begin")
    logger.info("🔧 Send /admin in private chat for admin panel")
    logger.info("👤 NEW: /anon command for anonymous messages!")
    logger.info("=" * 60)
    
    # Start polling
    await dp.start_polling(bot)

# ═══════════════════════════════════════════════════════════════════════════
# 🎬 ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")  # Fixed: removed {} before f-string
        raise  # Fixed: added space after 'raise'
