import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path="data/trading_bot.db"):
        self.db_path = db_path
        self._create_table()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        """สร้างตารางสมาชิกถ้ายังไม่มี"""
        query = """
        CREATE TABLE IF NOT EXISTS members (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'NORMAL',
            joined_date DATETIME,
            expiry_date DATETIME,
            last_payment_ref TEXT
        )
        """
        with self._get_connection() as conn:
            conn.execute(query)
            conn.commit()
        logger.info("📂 Database table initialized")

    def add_or_update_member(self, user_id, username, full_name, days=30):
        """เพิ่มสมาชิกใหม่หรือต่ออายุ"""
        joined_date = datetime.now()
        expiry_date = joined_date + timedelta(days=days)

        query = """
        INSERT INTO members (user_id, username, full_name, status, joined_date, expiry_date)
        VALUES (?, ?, ?, 'VIP', ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            status = 'VIP',
            expiry_date = DATETIME(MAX(expiry_date, CURRENT_TIMESTAMP), '+' || ? || ' days')
        """
        with self._get_connection() as conn:
            conn.execute(query, (user_id, username, full_name, joined_date, expiry_date, days))
            conn.commit()
        logger.info(f"✅ Member {user_id} updated to VIP for {days} days")

    def get_expired_members(self):
        """ดึงรายชื่อสมาชิกที่หมดอายุ"""
        query = "SELECT user_id, username FROM members WHERE status = 'VIP' AND expiry_date < ?"
        with self._get_connection() as conn:
            cursor = conn.execute(query, (datetime.now(),))
            return cursor.fetchall()

    def set_member_status(self, user_id, status='NORMAL'):
        """เปลี่ยนสถานะสมาชิก (เช่น เมื่อหมดอายุ)"""
        query = "UPDATE members SET status = ? WHERE user_id = ?"
        with self._get_connection() as conn:
            conn.execute(query, (status, user_id))
            conn.commit()

    def get_member(self, user_id):
        """เช็คข้อมูลสมาชิกรายคน"""
        query = "SELECT * FROM members WHERE user_id = ?"
        with self._get_connection() as conn:
            cursor = conn.execute(query, (user_id,))
            return cursor.fetchone()