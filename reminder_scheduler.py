import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz
from typing import Callable
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ReminderScheduler:
    def __init__(self, reminder_callback: Callable):
        """
        Initialize the reminder scheduler
        
        Args:
            reminder_callback: Function to call when reminder triggers
                             Should accept (user_id, reminder_content, reminder_id)
        """
        # Use Indian timezone (IST - UTC+5:30)
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.scheduler = BackgroundScheduler(timezone=self.timezone)
        self.reminder_callback = reminder_callback
        self.scheduler.start()
        logger.info("ReminderScheduler initialized and started")
    
    def parse_time(self, time_str: str) -> datetime:
        """
        Parse natural language time to datetime
        
        Examples:
        - "in 5 minutes" or "after 5 minutes"
        - "in 30 seconds" or "after 30 seconds" (for testing)
        - "in 2 hours" or "after 2 hours"
        - "tomorrow at 3pm"
        - "at 3:29"
        - "2024-01-15 14:30"
        """
        now = datetime.now(self.timezone)  # Use Indian timezone
        time_str = time_str.lower().strip()
        
        logger.info(f"Parsing time string: '{time_str}' (current time: {now})")
        
        # Handle "in X" OR "after X" seconds/minutes/hours/days
        if time_str.startswith("in ") or time_str.startswith("after "):
            # Remove the prefix
            if time_str.startswith("in "):
                parts = time_str[3:].split()
            else:  # starts with "after "
                parts = time_str[6:].split()
            
            if len(parts) >= 2:
                try:
                    amount = int(parts[0])
                    unit = parts[1]
                    
                    if "second" in unit or "sec" in unit:
                        result = now + timedelta(seconds=amount)
                        logger.info(f"Parsed as {amount} seconds -> {result}")
                        return result
                    elif "minute" in unit or "min" in unit:
                        result = now + timedelta(minutes=amount)
                        logger.info(f"Parsed as {amount} minutes -> {result}")
                        return result
                    elif "hour" in unit or "hr" in unit:
                        result = now + timedelta(hours=amount)
                        logger.info(f"Parsed as {amount} hours -> {result}")
                        return result
                    elif "day" in unit:
                        result = now + timedelta(days=amount)
                        logger.info(f"Parsed as {amount} days -> {result}")
                        return result
                    elif "week" in unit:
                        result = now + timedelta(weeks=amount)
                        logger.info(f"Parsed as {amount} weeks -> {result}")
                        return result
                except ValueError as e:
                    logger.warning(f"Could not parse amount from '{time_str}': {e}")
                    pass
        
        # Handle "tomorrow"
        if "tomorrow" in time_str:
            tomorrow = now + timedelta(days=1)
            
            # Try to extract time
            if "at" in time_str:
                time_part = time_str.split("at")[1].strip()
                try:
                    # Try parsing time formats
                    for fmt in ["%I%p", "%I:%M%p", "%H:%M", "%H"]:
                        try:
                            parsed_time = datetime.strptime(time_part.replace(" ", ""), fmt).time()
                            result = self.timezone.localize(datetime.combine(tomorrow.date(), parsed_time))
                            logger.info(f"Parsed as tomorrow at {time_part} -> {result}")
                            return result
                        except ValueError:
                            continue
                except Exception as e:
                    logger.warning(f"Error parsing time from 'tomorrow': {e}")
                    pass
            
            # Default to tomorrow at current time
            logger.info(f"Parsed as tomorrow (same time) -> {tomorrow}")
            return tomorrow
        
        # Handle "today" or just "at X"
        if "today" in time_str or "at" in time_str:
            if "at" in time_str:
                time_part = time_str.split("at")[1].strip()
                try:
                    # Try parsing different time formats
                    for fmt in ["%I%p", "%I:%M%p", "%H:%M", "%H", "%I:%M"]:
                        try:
                            parsed_time = datetime.strptime(time_part.replace(" ", ""), fmt).time()
                            result = self.timezone.localize(datetime.combine(now.date(), parsed_time))
                            
                            # If the time has already passed today, schedule for tomorrow
                            if result < now:
                                result += timedelta(days=1)
                                logger.info(f"Time already passed today, scheduling for tomorrow")
                            
                            logger.info(f"Parsed as 'at {time_part}' -> {result}")
                            return result
                        except ValueError:
                            continue
                except Exception as e:
                    logger.warning(f"Error parsing time from 'at': {e}")
                    pass
        
        # Try standard datetime formats
        for fmt in [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M",
        ]:
            try:
                parsed = datetime.strptime(time_str, fmt)
                result = self.timezone.localize(parsed)
                logger.info(f"Parsed as datetime format '{fmt}' -> {result}")
                return result
            except ValueError:
                continue
        
        # Default: 1 hour from now
        result = now + timedelta(hours=1)
        logger.warning(f"Could not parse '{time_str}', defaulting to 1 hour from now -> {result}")
        return result
    
    def schedule_reminder(self, reminder_id: int, user_id: int, content: str, time_str: str) -> dict:
        """
        Schedule a reminder
        
        Args:
            reminder_id: Database ID of the reminder
            user_id: Telegram user ID
            content: Reminder content
            time_str: When to remind (natural language)
        
        Returns:
            Dictionary with scheduling result
        """
        try:
            reminder_time = self.parse_time(time_str)
            
            # Don't schedule past reminders
            now = datetime.now(self.timezone)
            if reminder_time < now:
                error_msg = f"Cannot schedule reminder in the past (reminder: {reminder_time}, now: {now})"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "parsed_time": None
                }
            
            # Schedule the job
            job_id = f"reminder_{reminder_id}"
            
            logger.info(f"Scheduling job {job_id} for user {user_id} at {reminder_time}")
            logger.info(f"Job will trigger in {(reminder_time - now).total_seconds():.1f} seconds")
            
            self.scheduler.add_job(
                self.reminder_callback,
                trigger=DateTrigger(run_date=reminder_time),
                args=[user_id, content, reminder_id],
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"Job {job_id} scheduled successfully")
            
            # Verify the job was added
            job = self.scheduler.get_job(job_id)
            if job:
                logger.info(f"Job {job_id} verified in scheduler, next run: {job.next_run_time}")
            else:
                logger.error(f"Job {job_id} not found after scheduling!")
            
            return {
                "success": True,
                "parsed_time": reminder_time,
                "job_id": job_id
            }
        
        except Exception as e:
            logger.error(f"Error scheduling reminder: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "parsed_time": None
            }
    
    def cancel_reminder(self, reminder_id: int) -> bool:
        """Cancel a scheduled reminder"""
        try:
            job_id = f"reminder_{reminder_id}"
            self.scheduler.remove_job(job_id)
            logger.info(f"Cancelled reminder {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Could not cancel reminder {reminder_id}: {e}")
            return False
    
    def get_scheduled_reminders(self) -> list:
        """Get all scheduled reminder jobs"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                "job_id": job.id,
                "next_run": job.next_run_time,
                "args": job.args
            }
            for job in jobs
        ]
    
    def shutdown(self):
        """Shutdown the scheduler"""
        logger.info("Shutting down scheduler")
        self.scheduler.shutdown()