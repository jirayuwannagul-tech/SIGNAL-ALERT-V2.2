import logging

from datetime import datetime

from ..models.database import Database



logger = logging.getLogger(__name__)



class MemberManager:

    def __init__(self, telegram_notifier):

        self.db = Database()

        self.tg = telegram_notifier

        self.membership_fee = 490

        self.valid_days = 30



    def process_new_vip(self, user_id, username, full_name, payment_ref):

        """จัดการเมื่อมีการชำระเงินและสมัคร VIP เข้ามา"""

        try:

            # 1. บันทึกข้อมูลลงฐานข้อมูล

            self.db.add_or_update_member(user_id, username, full_name, days=self.valid_days)



            # 2. ส่งข้อความยินดีต้อนรับ

            msg = (

                f"🎉 *ยินดีต้อนรับสู่ครอบครัว VIP!*\n"

                f"━━━━━━━━━━━━━━━━━\n"

                f"👤 สมาชิก: `{full_name}`\n"

                f"⏱ ระยะเวลา: `{self.valid_days} วัน`\n"

                f"✅ สถานะ: `Active (Futures Signals)`\n"

                f"━━━━━━━━━━━━━━━━━\n"

                f"ขอบคุณที่ไว้วางใจบอทจ่าเฉยครับ!"

            )

            self.tg.send_message(msg, thread_id=None) # ส่งเข้าห้องสมัครสมาชิกหรือ Direct

            return True

        except Exception as e:

            logger.error(f"Error processing VIP: {e}")

            return False



    def check_and_cleanup_expiry(self, vip_chat_id):

        """ฟังก์ชันตรวจสอบสมาชิกหมดอายุและเตะออก (รันโดย Scheduler)"""

        expired_members = self.db.get_expired_members()



        for user_id, username in expired_members:

            try:

                # 1. ส่งคำสั่งเตะผ่าน Telegram API

                # หมายเหตุ: บอทต้องเป็น Admin ในกลุ่มถึงจะเตะได้

                success = self.tg.kick_chat_member(vip_chat_id, user_id)



                if success:

                    # 2. ปรับสถานะใน DB

                    self.db.set_member_status(user_id, 'NORMAL')



                    # 3. แจ้งเตือนในห้องสมัครสมาชิก (Optional)

                    expiry_msg = f"🔔 สมาชิก `{username or user_id}` หมดอายุ VIP และถูกเชิญออกจากกลุ่มเรียบร้อยแล้ว"

                    self.tg.send_message(expiry_msg)

                    logger.info(f"🚫 Kicked expired member: {user_id}")



            except Exception as e:

                logger.error(f"Failed to kick member {user_id}: {e}")



    def get_member_info(self, user_id):

        """ดึงข้อมูลเพื่อแสดงให้สมาชิกดูเวลาพิมพ์ /me หรือ /check"""

        member = self.db.get_member(user_id)

        if not member:

            return "❌ ไม่พบข้อมูลสมาชิกของคุณในระบบ"



        status = member[3]

        expiry = member[5]

        return f"👤 สถานะ: `{status}`\n📅 หมดอายุ: `{expiry}`"