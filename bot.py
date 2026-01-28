import os
import logging
import asyncio
import re
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from dotenv import load_dotenv

from database import init_db, get_db, User, Conversation, Reminder, List, ListItem, Image, VoiceNote
from vector_store import VectorStoreManager
from llm_manager import LLMManager
from image_analyzer import ImageAnalyzer
from audio_preprocessor import AudioProcessor
from reminder_scheduler import ReminderScheduler

# Load environment variables
load_dotenv()
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["TRANSFORMERS_NO_FLAX"] = "1"
os.environ["TRANSFORMERS_NO_JAX"] = "1"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize components
vector_store = VectorStoreManager()
llm_manager = LLMManager()
image_analyzer = ImageAnalyzer()
audio_processor = AudioProcessor()

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        
        # Initialize reminder scheduler with SYNC wrapper callback
        self.reminder_scheduler = ReminderScheduler(self.send_reminder_sync)
        
        # Setup handlers
        self.setup_handlers()
        
        # Initialize database
        init_db()
        
        logger.info("TelegramBot initialized successfully")
    
    def send_reminder_sync(self, user_id: int, content: str, reminder_id: int):
        """
        Synchronous wrapper for sending reminders - called by scheduler.
        """
        logger.info(f"send_reminder_sync called for reminder {reminder_id}, user {user_id}")
        
        try:
            # Try to get existing event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                # No event loop exists, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                logger.info("Created new event loop for reminder callback")
            
            # Run the async function in the event loop
            loop.run_until_complete(self.send_reminder_async(user_id, content, reminder_id))
            
        except Exception as e:
            logger.error(f"Error in send_reminder_sync: {e}", exc_info=True)
    
    async def send_reminder_async(self, user_id: int, content: str, reminder_id: int):
        """
        Async method to actually send the reminder via Telegram.
        """
        print('''-------------------content------------------''')
        print(content)
        logger.info(f"Attempting to send reminder {reminder_id} to user {user_id}")
        
        try:
            # Send the reminder message
            await self.app.bot.send_message(
                chat_id=user_id,
                text=f"🔔 Reminder: {content}"
            )
            
            logger.info(f"Successfully sent reminder {reminder_id} to user {user_id}")
            
            # Mark reminder as sent in database
            db = get_db()
            try:
                reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
                if reminder:
                    reminder.sent = True
                    reminder.completed = True
                    db.commit()
                    logger.info(f"Marked reminder {reminder_id} as sent in database")
                else:
                    logger.warning(f"Reminder {reminder_id} not found in database")
            except Exception as db_error:
                logger.error(f"Database error while marking reminder as sent: {db_error}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error sending reminder {reminder_id}: {e}", exc_info=True)
    
    def detect_reminder_intent(self, text: str) -> bool:
        """
        Detect if the message is asking to set a reminder.
        Returns True if reminder intent is detected.
        """
        text_lower = text.lower()
        
        # Reminder trigger phrases
        reminder_patterns = [
            r'\bremind me\b',
            r'\bset (a )?reminder\b',
            r'\breminder (to|for)\b',
            r'\bdon\'?t forget\b',
            r'\bafter \d+\b',
            r'\bin \d+\b',
            r'\btomorrow at\b',
            r'\btoday at\b',
            r'\bnext (week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        ]
        
        for pattern in reminder_patterns:
            if re.search(pattern, text_lower):
                logger.info(f"Reminder intent detected with pattern: {pattern}")
                return True
        
        return False
    
    def extract_reminder_from_text(self, text: str) -> dict:
        """
        Extract reminder content and time from natural language text.
        FIXED VERSION - Handles your specific format better
        """
        text_lower = text.lower().strip()
        original_text = text.strip()
        
        logger.info(f"[REMINDER EXTRACT] Input: '{text}'")
        
        # Pattern 1: "remind me after X to Y" or "remind me to Y after X"
        patterns = [
            # "remind me after 2 min to stop scrolling"
            r'remind me (after|in)\s+([^to]+?)\s+to\s+(.+)',
            # "remind me to stop scrolling after 2 min"  
            r'remind me to\s+(.+?)\s+(after|in|at|tomorrow|today|next)\s+(.+)',
            # "after 2 min remind me to stop scrolling"
            r'(after|in)\s+([^to]+?)\s+remind me to\s+(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                logger.info(f"[REMINDER EXTRACT] Pattern matched: {groups}")
                
                # Determine which group is content and which is time
                if len(groups) == 3:
                    if groups[0] in ['after', 'in', 'at', 'tomorrow', 'today', 'next']:
                        # Format: "(time_keyword) (time_value) ... (content)"
                        time_str = f"{groups[0]} {groups[1]}".strip()
                        content = groups[2].strip()
                    elif groups[1] in ['after', 'in', 'at', 'tomorrow', 'today', 'next']:
                        # Format: "(content) (time_keyword) (time_value)"
                        content = groups[0].strip()
                        time_str = f"{groups[1]} {groups[2]}".strip()
                    else:
                        continue
                    
                    logger.info(f"[REMINDER EXTRACT] Extracted - Content: '{content}', Time: '{time_str}'")
                    return {'content': content, 'time_str': time_str}
        
        # Fallback: Simple keyword split
        for keyword in [' after ', ' in ', ' at ', ' tomorrow ', ' today ']:
            if keyword in text_lower:
                # Check if keyword appears in a good position
                idx = text_lower.find(keyword)
                
                # Try both directions
                # 1. Content first: "do something in 2 hours"
                before = text_lower[:idx].strip()
                after = text_lower[idx:].strip()
                
                # Remove "remind me to" prefix from before
                before = re.sub(r'^(remind me to|remind me|set a reminder to|reminder to)\s*', '', before).strip()
                
                if before and len(before) > 3:
                    content = before
                    time_str = after
                    logger.info(f"[REMINDER EXTRACT] Fallback - Content: '{content}', Time: '{time_str}'")
                    return {'content': content, 'time_str': time_str}
        
        # Last resort: Use whole text as content
        logger.warning(f"[REMINDER EXTRACT] Could not parse, using full text")
        content = re.sub(r'^(remind me to|remind me)\s*', '', text_lower).strip()
        
        return {'content': content if content else original_text, 'time_str': 'in 1 hour'}
    
    async def create_reminder_from_message(self, update: Update, user: User, text: str):
        """
        Create a reminder from a natural language message.
        """
        # Extract reminder info
        reminder_info = self.extract_reminder_from_text(text)
        content = reminder_info['content']
        time_str = reminder_info['time_str']
        
        logger.info(f"Creating reminder - User: {user.telegram_id}, Content: '{content}', Time: '{time_str}'")
        
        # Save to database
        db = get_db()
        try:
            reminder = Reminder(
                user_id=user.id,
                content=content,
                reminder_time=datetime.now(timezone.utc),  # Placeholder
                sent=False,
                completed=False
            )
            db.add(reminder)
            db.commit()
            db.refresh(reminder)
            
            logger.info(f"Created reminder ID {reminder.id} for user {user.telegram_id}")
            
            # Schedule the reminder
            schedule_result = self.reminder_scheduler.schedule_reminder(
                reminder.id,
                user.telegram_id,
                content,
                time_str
            )
            
            if schedule_result["success"]:
                # Update with actual scheduled time
                reminder.reminder_time = schedule_result["parsed_time"]
                db.commit()
                
                logger.info(f"Scheduled reminder ID {reminder.id} for {schedule_result['parsed_time']}")
                
                # Add to vector store
                vector_store.add_reminder(
                    user.telegram_id,
                    content,
                    schedule_result["parsed_time"].isoformat()
                )
                
                await update.message.reply_text(
                    f"✅ Got it! I'll remind you:\n\n"
                    f"📋 {content}\n"
                    f"⏰ {schedule_result['parsed_time'].strftime('%I:%M %p on %B %d')}"
                )
            else:
                db.delete(reminder)
                db.commit()
                await update.message.reply_text(
                    f"I understood you want a reminder, but I couldn't parse the time. Can you say it differently?\n"
                    f"Examples: 'in 30 minutes', 'tomorrow at 3pm', 'in 2 hours'"
                )
                
        except Exception as e:
            logger.error(f"Error creating reminder: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't create that reminder.")
        finally:
            db.close()
    
    def setup_handlers(self):
        """Setup all message and command handlers"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("list", self.list_command))
        self.app.add_handler(CommandHandler("mylists", self.view_lists_command))
        self.app.add_handler(CommandHandler("myreminders", self.view_reminders_command))
        self.app.add_handler(CommandHandler("myimages", self.view_images_command))
        self.app.add_handler(CommandHandler("search", self.search_command))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        logger.info("All handlers registered")
    
    def get_or_create_user(self, telegram_user) -> User:
        """Get or create user in database"""
        db = get_db()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_user.id).first()
            
            if not user:
                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Created new user: {telegram_user.id} ({telegram_user.first_name})")
            
            return user
        finally:
            db.close()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = self.get_or_create_user(update.effective_user)
        
        welcome_message = f"""👋 Welcome {user.first_name}!

I'm your AI assistant with advanced memory and capabilities:

✨ **Features:**
- 💬 Natural conversation with memory
- 🖼️ Image analysis and storage
- 🎤 Voice message transcription
- ⏰ Smart reminders (just tell me naturally!)
- 📝 List management
- 🔍 Semantic search across your data

**Examples:**
- "Remind me to call mom in 2 hours"
- "Don't forget to buy milk tomorrow at 5pm"
- "Reminder to take medicine after 30 minutes"

Use /help to see all available commands!"""
        
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """📚 **Available Commands:**

**Basic:**
- Just chat with me naturally!

**Reminders (Natural Language):**
- "Remind me to call John in 2 hours"
- "Don't forget meeting tomorrow at 3pm"
- "Reminder to take pills after 30 minutes"
- `/myreminders` - View all reminders

**Lists:**
- `/list <name> <items>` - Create a list
  Example: `/list Shopping milk, eggs, bread`
- `/mylists` - View all lists

**Images:**
- Send me an image and I'll analyze it
- `/myimages` - View all your images

**Voice:**
- Send voice messages - I'll transcribe them

**Search:**
- `/search <query>` - Search your memory

**General:**
- `/help` - Show this help message
- `/start` - Restart the bot"""
        
        await update.message.reply_text(help_text)
    
    def detect_list_intent(self, text: str) -> dict:
        """
        Use LLM to detect if message is about list management.
        Delegates to llm_manager for actual detection.
        
        Returns dict with 'intent', 'list_name', 'item', 'action' or None
        """
        return llm_manager.detect_list_intent(text)


    async def handle_list_intent(self, update: Update, user: User, intent_data: dict):
        """
        Handle list-related intents detected from natural language.
        """
        db = get_db()
        try:
            # ADD TO LIST
            if intent_data['intent'] == 'add_to_list':
                list_name = intent_data['list_name']
                item_content = intent_data['item']
                
                # Find or create list
                list_obj = db.query(List).filter(
                    List.user_id == user.id,
                    List.name.ilike(f"%{list_name}%")
                ).first()
                
                if not list_obj:
                    # Create new list
                    list_obj = List(user_id=user.id, name=list_name)
                    db.add(list_obj)
                    db.commit()
                    db.refresh(list_obj)
                    logger.info(f"Created new list '{list_name}' for user {user.telegram_id}")
                
                # Check if item already exists
                existing = db.query(ListItem).filter(
                    ListItem.list_id == list_obj.id,
                    ListItem.content.ilike(f"%{item_content}%")
                ).first()
                
                if existing:
                    await update.message.reply_text(
                        f"{item_content.title()} is already in your {list_name} list, you've added it previously."
                    )
                else:
                    # Add new item
                    new_item = ListItem(
                        list_id=list_obj.id,
                        content=item_content,
                        completed=False
                    )
                    db.add(new_item)
                    db.commit()
                    
                    logger.info(f"Added '{item_content}' to list '{list_name}'")
                    
                    # Update vector store
                    all_items = db.query(ListItem).filter(ListItem.list_id == list_obj.id).all()
                    vector_store.add_list(
                        user.telegram_id,
                        list_name,
                        [item.content for item in all_items]
                    )
                    
                    await update.message.reply_text(
                        f"✅ Added {item_content} to {list_name} list"
                    )
            
            # SHOW SPECIFIC LIST
            elif intent_data['intent'] == 'show_list':
                list_name = intent_data['list_name']
                
                # Find list
                list_obj = db.query(List).filter(
                    List.user_id == user.id,
                    List.name.ilike(f"%{list_name}%")
                ).first()
                
                if not list_obj:
                    await update.message.reply_text(
                        f"You don't have a {list_name} list yet."
                    )
                    return
                
                # Get items
                items = db.query(ListItem).filter(
                    ListItem.list_id == list_obj.id
                ).order_by(ListItem.created_at).all()
                
                if not items:
                    await update.message.reply_text(
                        f"Your {list_name} list is empty, I couldn't find any items in it."
                    )
                else:
                    message = f"🛒 **{list_name.title()} List:**\n\n"
                    for i, item in enumerate(items, 1):
                        status = "✅" if item.completed else "⭕"
                        message += f"{i}. {status} {item.content}\n"
                    
                    await update.message.reply_text(message)
            
            # SHOW ALL LISTS
            elif intent_data['intent'] == 'show_all_lists':
                lists = db.query(List).filter(List.user_id == user.id).all()
                
                if not lists:
                    await update.message.reply_text("You don't have any lists yet.")
                    return
                
                message = "📋 **Your Lists:**\n\n"
                
                for list_obj in lists:
                    items = db.query(ListItem).filter(
                        ListItem.list_id == list_obj.id
                    ).all()
                    
                    message += f"**{list_obj.name.title()}** ({len(items)} items)"
                    
                    if items:
                        message += ":\n"
                        for item in items[:3]:  # Show first 3
                            status = "✅" if item.completed else "⭕"
                            message += f"  {status} {item.content}\n"
                        if len(items) > 3:
                            message += f"  ... and {len(items) - 3} more\n"
                    else:
                        message += " - but none of them have any items added to them except "
                        # This matches your bot's response
                    
                    message += "\n"
                
                await update.message.reply_text(message)
            
            # DELETE ITEM FROM LIST
            elif intent_data['intent'] == 'delete_item':
                list_name = intent_data['list_name']
                item_content = intent_data['item']
                
                # Find list
                list_obj = db.query(List).filter(
                    List.user_id == user.id,
                    List.name.ilike(f"%{list_name}%")
                ).first()
                
                if not list_obj:
                    await update.message.reply_text(
                        f"You don't have a {list_name} list yet."
                    )
                    return
                
                # Find item to delete
                item_to_delete = db.query(ListItem).filter(
                    ListItem.list_id == list_obj.id,
                    ListItem.content.ilike(f"%{item_content}%")
                ).first()
                
                if item_to_delete:
                    db.delete(item_to_delete)
                    db.commit()
                    
                    logger.info(f"Deleted '{item_content}' from list '{list_name}'")
                    
                    # Get remaining items and show updated list
                    remaining_items = db.query(ListItem).filter(
                        ListItem.list_id == list_obj.id
                    ).all()
                    
                    if remaining_items:
                        items_text = ", ".join([item.content for item in remaining_items])
                        await update.message.reply_text(
                            f"I've removed {item_content} from your {list_name} list, it now has only {items_text}."
                        )
                    else:
                        await update.message.reply_text(
                            f"I've removed {item_content} from your {list_name} list. The list is now empty."
                        )
                    
                    # Update vector store
                    if remaining_items:
                        vector_store.add_list(
                            user.telegram_id,
                            list_name,
                            [item.content for item in remaining_items]
                        )
                else:
                    await update.message.reply_text(
                        f"I couldn't find '{item_content}' in your {list_name} list."
                    )
            
            # COMPLETE ITEM ON LIST
            elif intent_data['intent'] == 'complete_item':
                list_name = intent_data['list_name']
                item_content = intent_data['item']
                
                # Find list
                list_obj = db.query(List).filter(
                    List.user_id == user.id,
                    List.name.ilike(f"%{list_name}%")
                ).first()
                
                if not list_obj:
                    await update.message.reply_text(
                        f"You don't have a {list_name} list yet."
                    )
                    return
                
                # Find item to complete
                item_to_complete = db.query(ListItem).filter(
                    ListItem.list_id == list_obj.id,
                    ListItem.content.ilike(f"%{item_content}%")
                ).first()
                
                if item_to_complete:
                    if item_to_complete.completed:
                        await update.message.reply_text(
                            f"'{item_content}' is already marked as completed on your {list_name} list."
                        )
                    else:
                        item_to_complete.completed = True
                        db.commit()
                        
                        logger.info(f"Marked '{item_content}' as completed in list '{list_name}'")
                        
                        await update.message.reply_text(
                            f"✅ Marked '{item_content}' as done on your {list_name} list!"
                        )
                        
                        # Update vector store
                        all_items = db.query(ListItem).filter(
                            ListItem.list_id == list_obj.id
                        ).all()
                        vector_store.add_list(
                            user.telegram_id,
                            list_name,
                            [item.content for item in all_items]
                        )
                else:
                    await update.message.reply_text(
                        f"I couldn't find '{item_content}' in your {list_name} list."
                    )
        
        finally:
            db.close()
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages - with reminder detection"""
        user = self.get_or_create_user(update.effective_user)
        message_text = update.message.text
        
        logger.info(f"Message from user {user.telegram_id}: {message_text[:50]}...")
        
        # Check if this is a reminder request
        if self.detect_reminder_intent(message_text):
            logger.info("Reminder intent detected, creating reminder...")
            await self.create_reminder_from_message(update, user, message_text)
            return
        list_intent = self.detect_list_intent(message_text)
        if list_intent:
            logger.info(f"List intent detected: {list_intent}")
            await self.handle_list_intent(update, user, list_intent)
            return
        
        # Normal conversation handling
        db = get_db()
        try:
            user_conv = Conversation(user_id=user.id, role='user', content=message_text)
            db.add(user_conv)
            db.commit()
            
            # Add to vector store
            vector_store.add_conversation(user.telegram_id, message_text, 'user')
            
            # Get conversation history
            recent_convs = db.query(Conversation).filter(
                Conversation.user_id == user.id
            ).order_by(Conversation.timestamp.desc()).limit(10).all()
            
            conversation_history = [
                {"role": conv.role, "content": conv.content}
                for conv in reversed(recent_convs)
            ]
            
            # Search for relevant context
            relevant_docs = vector_store.search_memory(user.telegram_id, message_text, k=3)
            context_list = [doc.page_content for doc in relevant_docs]
            
            # Generate response
            response = llm_manager.generate_response(
                message_text,
                context=context_list,
                conversation_history=conversation_history
            )
            
            # Save assistant response
            assistant_conv = Conversation(user_id=user.id, role='assistant', content=response)
            db.add(assistant_conv)
            db.commit()
            
            # Add to vector store
            vector_store.add_conversation(user.telegram_id, response, 'assistant')
            
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I encountered an error processing your message.")
        finally:
            db.close()
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle image messages"""
        user = self.get_or_create_user(update.effective_user)
        
        logger.info(f"Photo received from user {user.telegram_id}")
        await update.message.reply_text("📸 Analyzing your image...")
        
        try:
            # Get the photo
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # Download to local
            os.makedirs('data/images', exist_ok=True)
            file_path = f'data/images/{photo.file_id}.jpg'
            await file.download_to_drive(file_path)
            
            # Get caption if provided
            caption = update.message.caption or ""
            
            # Analyze image
            analysis = image_analyzer.analyze_image(file_path, caption)
            
            # Save to database
            db = get_db()
            try:
                image_record = Image(
                    user_id=user.id,
                    file_id=photo.file_id,
                    file_path=file_path,
                    caption=caption,
                    analysis=analysis,
                    timestamp=datetime.now(timezone.utc)
                )
                db.add(image_record)
                db.commit()
                db.refresh(image_record)
                
                # Add to vector store
                vector_store.add_image_analysis(user.telegram_id, analysis, caption, image_record.id)
                
                await update.message.reply_text(f"🖼️ **Image Analysis:**\n\n{analysis}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error handling photo: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't analyze that image.")
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages"""
        user = self.get_or_create_user(update.effective_user)
        
        logger.info(f"Voice message received from user {user.telegram_id}")
        await update.message.reply_text("🎤 Transcribing your voice message...")
        
        try:
            # Get voice file
            if update.message.voice:
                voice = update.message.voice
            else:
                voice = update.message.audio
            
            file = await context.bot.get_file(voice.file_id)
            
            # Download to local
            os.makedirs('data/voice', exist_ok=True)
            file_path = f'data/voice/{voice.file_id}.ogg'
            await file.download_to_drive(file_path)
            
            # Transcribe
            result = audio_processor.process_voice_note(file_path)
            
            if result["success"]:
                transcription = result["transcription"]
                
                # Save to database
                db = get_db()
                try:
                    voice_record = VoiceNote(
                        user_id=user.id,
                        file_id=voice.file_id,
                        file_path=file_path,
                        transcription=transcription,
                        timestamp=datetime.now(timezone.utc)
                    )
                    db.add(voice_record)
                    db.commit()
                    db.refresh(voice_record)
                    
                    # Add to vector store
                    vector_store.add_voice_transcription(user.telegram_id, transcription, voice_record.id)
                    
                    await update.message.reply_text(f"📝 **Transcription:**\n\n{transcription}")
                    
                    # Check if the transcription contains a reminder request
                    if self.detect_reminder_intent(transcription):
                        logger.info("Reminder detected in voice transcription")
                        # Create a fake update with the transcription as text
                        await self.create_reminder_from_message(update, user, transcription)
                    
                finally:
                    db.close()
            else:
                await update.message.reply_text(f"❌ Error transcribing: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error handling voice: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't transcribe that voice message.")
    
    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command"""
        user = self.get_or_create_user(update.effective_user)
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /list <name> <items>\n"
                "Example: /list Shopping milk, eggs, bread, cheese"
            )
            return
        
        # Parse list name and items
        text = " ".join(context.args)
        parts = text.split(" ", 1)
        
        if len(parts) < 2:
            await update.message.reply_text("Please provide both list name and items!")
            return
        
        list_name = parts[0]
        items_text = parts[1]
        items = [item.strip() for item in items_text.split(",")]
        
        logger.info(f"Creating list '{list_name}' with {len(items)} items for user {user.telegram_id}")
        
        # Save to database
        db = get_db()
        try:
            new_list = List(user_id=user.id, name=list_name)
            db.add(new_list)
            db.commit()
            db.refresh(new_list)
            
            for item_content in items:
                item = ListItem(list_id=new_list.id, content=item_content)
                db.add(item)
            
            db.commit()
            
            # Add to vector store
            vector_store.add_list(user.telegram_id, list_name, items)
            
            items_display = "\n".join([f"• {item}" for item in items])
            await update.message.reply_text(
                f"✅ List created!\n\n"
                f"📝 **{list_name}**\n{items_display}"
            )
            
        except Exception as e:
            logger.error(f"Error creating list: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't create that list.")
        finally:
            db.close()
    
    async def view_lists_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all user lists"""
        user = self.get_or_create_user(update.effective_user)
        
        db = get_db()
        try:
            lists = db.query(List).filter(List.user_id == user.id).all()
            
            if not lists:
                await update.message.reply_text("You don't have any lists yet!")
                return
            
            response = "📝 **Your Lists:**\n\n"
            for lst in lists:
                items = db.query(ListItem).filter(ListItem.list_id == lst.id).all()
                items_display = "\n".join([f"  {'✅' if item.completed else '☐'} {item.content}" for item in items])
                response += f"**{lst.name}**\n{items_display}\n\n"
            
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"Error viewing lists: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't retrieve your lists.")
        finally:
            db.close()
    
    async def view_reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all user reminders"""
        user = self.get_or_create_user(update.effective_user)
        
        db = get_db()
        try:
            reminders = db.query(Reminder).filter(
                Reminder.user_id == user.id,
                Reminder.sent == False
            ).order_by(Reminder.reminder_time).all()
            
            if not reminders:
                await update.message.reply_text("You don't have any active reminders!")
                return
            
            response = "⏰ **Your Reminders:**\n\n"
            for reminder in reminders:
                status = "✅ Sent" if reminder.sent else "⏳ Pending"
                response += f"{status}\n📋 {reminder.content}\n🕐 {reminder.reminder_time.strftime('%I:%M %p on %B %d, %Y')}\n\n"
            
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"Error viewing reminders: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't retrieve your reminders.")
        finally:
            db.close()
    
    async def view_images_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View all user images"""
        user = self.get_or_create_user(update.effective_user)
        
        db = get_db()
        try:
            images = db.query(Image).filter(Image.user_id == user.id).order_by(Image.timestamp.desc()).limit(10).all()
            
            if not images:
                await update.message.reply_text("You haven't shared any images yet!")
                return
            
            await update.message.reply_text(f"📸 Found {len(images)} recent images. Sending them now...")
            
            for img in images:
                caption = f"📅 {img.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
                if img.caption:
                    caption += f"💬 {img.caption}\n"
                caption += f"🔍 {img.analysis[:200]}..."
                
                try:
                    await update.message.reply_photo(
                        photo=img.file_id,
                        caption=caption
                    )
                except Exception as e:
                    logger.error(f"Error sending image: {e}")
                    
        except Exception as e:
            logger.error(f"Error viewing images: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't retrieve your images.")
        finally:
            db.close()
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search through user's memory"""
        user = self.get_or_create_user(update.effective_user)
        
        if not context.args:
            await update.message.reply_text("Usage: /search <query>\nExample: /search images of my dog")
            return
        
        query = " ".join(context.args)
        
        logger.info(f"Search query from user {user.telegram_id}: {query}")
        
        try:
            # Search in vector store
            results = vector_store.search_memory(user.telegram_id, query, k=5)
            
            if not results:
                await update.message.reply_text("No results found!")
                return
            
            response = f"🔍 **Search Results for:** {query}\n\n"
            for i, doc in enumerate(results, 1):
                doc_type = doc.metadata.get('type', 'unknown')
                content_preview = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                response += f"{i}. **Type:** {doc_type}\n{content_preview}\n\n"
            
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"Error in search: {e}", exc_info=True)
            await update.message.reply_text("Sorry, I couldn't perform that search.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(text=f"Selected option: {query.data}")
    
    def run(self):
        """Run the bot"""
        logger.info("Starting bot...")
        logger.info("Press Ctrl+C to stop")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    logger.info("Initializing Telegram bot with natural language reminders...")
    bot = TelegramBot(token)
    bot.run()

if __name__ == '__main__':
    main()