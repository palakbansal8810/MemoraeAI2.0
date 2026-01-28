from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from contextlib import contextmanager
import logging

load_dotenv()

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    """User model for storing Telegram user information"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    lists = relationship("List", back_populates="user", cascade="all, delete-orphan")
    images = relationship("Image", back_populates="user", cascade="all, delete-orphan")
    voice_notes = relationship("VoiceNote", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, name={self.first_name})>"

class Conversation(Base):
    """Conversation history model"""
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    user = relationship("User", back_populates="conversations")
    
    def __repr__(self):
        return f"<Conversation(user_id={self.user_id}, role={self.role})>"

class Reminder(Base):
    """Reminder model"""
    __tablename__ = 'reminders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    content = Column(Text, nullable=False)
    reminder_time = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed = Column(Boolean, default=False, index=True)
    sent = Column(Boolean, default=False, index=True)
    
    # Relationship
    user = relationship("User", back_populates="reminders")
    
    def __repr__(self):
        return f"<Reminder(id={self.id}, user_id={self.user_id}, time={self.reminder_time}, sent={self.sent}, content={self.content})>"

class List(Base):
    """List model for todo lists, shopping lists, etc."""
    __tablename__ = 'lists'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="lists")
    items = relationship("ListItem", back_populates="list", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<List(id={self.id}, name={self.name}, user_id={self.user_id})>"

class ListItem(Base):
    """Individual items in a list"""
    __tablename__ = 'list_items'
    
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey('lists.id'), nullable=False, index=True)
    content = Column(Text, nullable=False)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    list = relationship("List", back_populates="items")
    
    def __repr__(self):
        return f"<ListItem(id={self.id}, list_id={self.list_id}, completed={self.completed})>"

class Image(Base):
    """Image storage and analysis model"""
    __tablename__ = 'images'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    file_id = Column(String(200), nullable=False)
    file_path = Column(String(500))
    caption = Column(Text)
    analysis = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    user = relationship("User", back_populates="images")
    
    def __repr__(self):
        return f"<Image(id={self.id}, user_id={self.user_id}, file_id={self.file_id})>"

class VoiceNote(Base):
    """Voice note storage and transcription model"""
    __tablename__ = 'voice_notes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    file_id = Column(String(200), nullable=False)
    file_path = Column(String(500))
    transcription = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationship
    user = relationship("User", back_populates="voice_notes")
    
    def __repr__(self):
        return f"<VoiceNote(id={self.id}, user_id={self.user_id}, file_id={self.file_id})>"

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/bot_database.db')

# Create engine with better error handling
try:
    engine = create_engine(
        DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,  # Verify connections before using them
        pool_recycle=3600,  # Recycle connections after 1 hour
    )
    logger.info(f"Database engine created: {DATABASE_URL}")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def init_db():
    """
    Initialize the database by creating all tables.
    This should be called once when the application starts.
    """
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        logger.info("Data directory ensured")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified successfully")
        
        # Log table names
        table_names = Base.metadata.tables.keys()
        logger.info(f"Tables: {', '.join(table_names)}")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_db():
    """
    Get a database session.
    
    IMPORTANT: The caller MUST close the session when done.
    Usage:
        db = get_db()
        try:
            # ... database operations ...
        finally:
            db.close()
    
    Returns:
        SQLAlchemy Session object
    """
    return SessionLocal()

@contextmanager
def get_db_context():
    """
    Context manager for database sessions - automatically closes session.
    
    This is the preferred way to use database sessions as it ensures
    proper cleanup even if an exception occurs.
    
    Usage:
        with get_db_context() as db:
            # ... database operations ...
            # Session automatically closed when exiting with block
    
    Yields:
        SQLAlchemy Session object
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Auto-commit on successful completion
    except Exception as e:
        db.rollback()  # Rollback on error
        logger.error(f"Database error, rolled back: {e}")
        raise
    finally:
        db.close()

def cleanup_old_data(days_old: int = 90):
    """
    Clean up old data from the database.
    
    Args:
        days_old: Remove data older than this many days
    """
    try:
        with get_db_context() as db:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            # Clean old conversations
            old_convs = db.query(Conversation).filter(
                Conversation.timestamp < cutoff_date
            ).delete()
            
            logger.info(f"Cleaned {old_convs} old conversations")
            
            # Clean completed reminders
            old_reminders = db.query(Reminder).filter(
                Reminder.completed == True,
                Reminder.created_at < cutoff_date
            ).delete()
            
            logger.info(f"Cleaned {old_reminders} old completed reminders")
            
    except Exception as e:
        logger.error(f"Error cleaning old data: {e}")

def get_user_stats(telegram_id: int) -> dict:
    """
    Get statistics for a user.
    
    Args:
        telegram_id: Telegram user ID
        
    Returns:
        Dictionary with user statistics
    """
    try:
        with get_db_context() as db:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                return {"error": "User not found"}
            
            stats = {
                "conversations": db.query(Conversation).filter(Conversation.user_id == user.id).count(),
                "reminders": db.query(Reminder).filter(Reminder.user_id == user.id).count(),
                "active_reminders": db.query(Reminder).filter(
                    Reminder.user_id == user.id,
                    Reminder.sent == False
                ).count(),
                "lists": db.query(List).filter(List.user_id == user.id).count(),
                "images": db.query(Image).filter(Image.user_id == user.id).count(),
                "voice_notes": db.query(VoiceNote).filter(VoiceNote.user_id == user.id).count(),
            }
            
            return stats
            
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {"error": str(e)}

# Test database connection on import
try:
    with engine.connect() as connection:
        logger.info("Database connection test successful")
except Exception as e:
    logger.error(f"Database connection test failed: {e}")