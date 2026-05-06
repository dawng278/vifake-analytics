"""
ViFake Analytics - File Cleanup Management

Handles automatic cleanup of temporary files and sessions
to ensure privacy and prevent disk space issues.
"""

import asyncio
import shutil
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def cleanup_session(session_dir: str) -> None:
    """
    Xóa toàn bộ thư mục session sau khi phân tích xong.
    Luôn được gọi trong finally block — không bao giờ bị bỏ qua.
    """
    try:
        if os.path.exists(session_dir):
            # shutil.rmtree xóa cả thư mục và tất cả file bên trong
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, session_dir)
            logger.info(f"🗑️ Cleaned up session: {session_dir}")
        else:
            logger.debug(f"📁 Session directory already cleaned: {session_dir}")
    except Exception as e:
        # Log lỗi nhưng không raise — không để cleanup lỗi crash pipeline
        logger.error(f"⚠️ Cleanup WARNING: Failed to delete {session_dir}: {e}")


async def cleanup_old_sessions(max_age_minutes: int = 30) -> None:
    """
    Dọn dẹp định kỳ: xóa các session cũ hơn N phút.
    Chạy như background task khi server khởi động.
    Phòng trường hợp server crash giữa chừng, cleanup() không được gọi.
    """
    temp_dir = "/tmp/vifake_cache"
    
    if not os.path.exists(temp_dir):
        logger.debug(f"📁 Cache directory does not exist: {temp_dir}")
        return
    
    now = time.time()
    cutoff = max_age_minutes * 60
    cleaned_count = 0
    
    try:
        for session_id in os.listdir(temp_dir):
            session_path = os.path.join(temp_dir, session_id)
            if not os.path.isdir(session_path):
                continue
                
            age = now - os.path.getctime(session_path)
            if age > cutoff:
                await cleanup_session(session_path)
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} old sessions (older than {max_age_minutes} minutes)")
        else:
            logger.debug(f"🧹 No old sessions to clean (threshold: {max_age_minutes} minutes)")
            
    except Exception as e:
        logger.error(f"❌ Cleanup old sessions failed: {e}")


async def get_cache_info() -> dict:
    """Get information about cache directory for monitoring"""
    temp_dir = "/tmp/vifake_cache"
    
    if not os.path.exists(temp_dir):
        return {
            "cache_dir": temp_dir,
            "exists": False,
            "session_count": 0,
            "total_size_mb": 0
        }
    
    try:
        session_count = 0
        total_size = 0
        
        for session_id in os.listdir(temp_dir):
            session_path = os.path.join(temp_dir, session_id)
            if os.path.isdir(session_path):
                session_count += 1
                # Calculate directory size
                for root, dirs, files in os.walk(session_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
        
        return {
            "cache_dir": temp_dir,
            "exists": True,
            "session_count": session_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get cache info: {e}")
        return {
            "cache_dir": temp_dir,
            "exists": True,
            "session_count": 0,
            "total_size_mb": 0,
            "error": str(e)
        }


async def enforce_cache_limits(max_sessions: int = 50, max_size_mb: int = 500) -> None:
    """
    Enforce cache limits to prevent disk space issues.
    Removes oldest sessions if limits are exceeded.
    """
    temp_dir = "/tmp/vifake_cache"
    
    if not os.path.exists(temp_dir):
        return
    
    try:
        sessions = []
        
        for session_id in os.listdir(temp_dir):
            session_path = os.path.join(temp_dir, session_id)
            if os.path.isdir(session_path):
                # Get session info
                session_size = 0
                for root, dirs, files in os.walk(session_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            session_size += os.path.getsize(file_path)
                
                sessions.append({
                    "id": session_id,
                    "path": session_path,
                    "size": session_size,
                    "created": os.path.getctime(session_path)
                })
        
        # Sort by creation time (oldest first)
        sessions.sort(key=lambda x: x["created"])
        
        # Check session count limit
        if len(sessions) > max_sessions:
            sessions_to_remove = sessions[:len(sessions) - max_sessions]
            for session in sessions_to_remove:
                await cleanup_session(session["path"])
                logger.info(f"🗑️ Removed old session due to count limit: {session['id']}")
        
        # Check total size limit
        total_size = sum(s["size"] for s in sessions)
        total_size_mb = total_size / (1024 * 1024)
        
        if total_size_mb > max_size_mb:
            # Remove oldest sessions until under limit
            sessions.sort(key=lambda x: x["created"])
            size_to_remove = total_size - (max_size_mb * 1024 * 1024)
            removed_size = 0
            
            for session in sessions:
                if removed_size >= size_to_remove:
                    break
                await cleanup_session(session["path"])
                removed_size += session["size"]
                logger.info(f"🗑️ Removed session due to size limit: {session['id']} "
                           f"({session['size']/1024/1024:.1f}MB)")
        
    except Exception as e:
        logger.error(f"❌ Failed to enforce cache limits: {e}")


# Background task for periodic cleanup
async def start_cleanup_scheduler():
    """Start background task for periodic cleanup"""
    async def periodic_cleanup():
        while True:
            try:
                # Clean old sessions
                await cleanup_old_sessions(max_age_minutes=30)
                
                # Enforce limits
                await enforce_cache_limits(max_sessions=50, max_size_mb=500)
                
                # Wait 15 minutes before next cleanup
                await asyncio.sleep(15 * 60)
                
            except Exception as e:
                logger.error(f"❌ Periodic cleanup failed: {e}")
                # Wait 5 minutes before retrying
                await asyncio.sleep(5 * 60)
    
    # Start the background task
    asyncio.create_task(periodic_cleanup())
    logger.info("🕐 Started cleanup scheduler (runs every 15 minutes)")
