"""
app/services/email_service.py

ส่งอีเมลแจ้งเตือนความปลอดภัย (security notification) ผ่าน Gmail SMTP
แยกหน้าที่ชัดเจนจาก Supabase Auth OTP:
  - Supabase Auth  -> ใช้ verify ตัวตนด้วย OTP เท่านั้น (จัดการฝั่ง frontend อยู่แล้ว)
  - Gmail SMTP     -> ใช้ส่งอีเมลแจ้งเตือนหลังทำรายการสำเร็จ (ใหม่ จัดการฝั่ง backend)

หมายเหตุ: ฟังก์ชันนี้ "ไม่ raise exception" หากส่งอีเมลล้มเหลว เพื่อไม่ให้
กระทบ flow หลักของการ reset password — แค่ log error ไว้เฉยๆ
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from zoneinfo import ZoneInfo
from app.config import settings

logger = logging.getLogger(__name__)

BANGKOK_TZ = ZoneInfo("Asia/Bangkok")

THAI_MONTHS = [
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def format_thai_datetime(dt: datetime) -> str:
    """แปลง datetime เป็นรูปแบบไทย เช่น 20 มิถุนายน 2569 เวลา 14:35 น."""
    dt_local = dt.astimezone(BANGKOK_TZ)
    thai_year = dt_local.year + 543
    day = dt_local.day
    month = THAI_MONTHS[dt_local.month]
    time_str = dt_local.strftime("%H:%M")
    return f"{day} {month} {thai_year} เวลา {time_str} น."


def _build_html(greeting_name: str, formatted_time: str) -> str:
    return f"""
    <div style="font-family: 'Sarabun', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #f4fbf7; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 36px;">🔒</span>
            <h2 style="color: #0d4f2e; margin: 8px 0 0;">แจ้งเตือนเรื่องความปลอดภัย</h2>
        </div>
        <div style="background: #fff; border-radius: 12px; padding: 20px; border: 1px solid rgba(22,163,97,0.15);">
            <p style="color: #0d4f2e; font-size: 15px; line-height: 1.6;">
                เรียน {greeting_name}
            </p>
            <p style="color: #2d7055; font-size: 15px; line-height: 1.6;">
                ท่านได้ทำการ<strong>รีเซ็ตรหัสผ่านสำเร็จ</strong> สำหรับบัญชีที่ผูกกับอีเมลนี้
            </p>
            <div style="background: #e8f5f0; border-radius: 10px; padding: 14px; margin: 16px 0;">
                <p style="margin: 0; color: #4a7c62; font-size: 13px;">วันและเวลาที่ทำรายการ</p>
                <p style="margin: 4px 0 0; color: #0d4f2e; font-size: 16px; font-weight: 700;">{formatted_time}</p>
            </div>
            <p style="color: #6b9e84; font-size: 13px; line-height: 1.6;">
                หากท่านไม่ได้เป็นผู้ดำเนินการนี้ กรุณาติดต่อผู้ดูแลระบบทันที
                เพื่อความปลอดภัยของบัญชีท่าน
            </p>
        </div>
        <p style="text-align: center; color: #8aab9a; font-size: 12px; margin-top: 20px;">
            อีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ
        </p>
    </div>
    """


def send_password_reset_notification(to_email: str, full_name: str = "") -> bool:
    """
    ส่งอีเมลแจ้งเตือนความปลอดภัยหลังรีเซ็ตรหัสผ่านสำเร็จ ผ่าน Gmail SMTP
    คืนค่า True ถ้าส่งสำเร็จ, False ถ้าส่งไม่สำเร็จ
    """
    now = datetime.now(BANGKOK_TZ)
    formatted_time = format_thai_datetime(now)
    greeting_name = full_name if full_name else "ผู้ใช้งาน"
    html_content = _build_html(greeting_name, formatted_time)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "แจ้งเตือนเรื่องความปลอดภัย: รีเซ็ตรหัสผ่านสำเร็จ"
    msg["From"] = f"DietAI Security <{settings.gmail_address}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(settings.gmail_address, settings.gmail_app_password)
            server.sendmail(settings.gmail_address, [to_email], msg.as_string())
        logger.info(f"Password reset notification sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset notification to {to_email}: {e}")
        return False
    

def _build_doctor_approved_html(greeting_name: str, formatted_time: str) -> str:
    return f"""
    <div style="font-family: 'Sarabun', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #f4fbf7; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 36px;">✅</span>
            <h2 style="color: #0d4f2e; margin: 8px 0 0;">แจ้งเตือนการสมัครสมาชิก</h2>
        </div>
        <div style="background: #fff; border-radius: 12px; padding: 20px; border: 1px solid rgba(22,163,97,0.15);">
            <p style="color: #0d4f2e; font-size: 15px; line-height: 1.6;">
                เรียน {greeting_name}
            </p>
            <p style="color: #2d7055; font-size: 15px; line-height: 1.6;">
                แอดมินได้ทำการ<strong>อนุมัติบัญชีของท่านแล้ว</strong> ท่านสามารถเข้าสู่ระบบ
                ด้วยชื่อผู้ใช้และรหัสผ่านที่ลงทะเบียนไว้ได้ทันที
            </p>
            <div style="background: #e8f5f0; border-radius: 10px; padding: 14px; margin: 16px 0;">
                <p style="margin: 0; color: #4a7c62; font-size: 13px;">วันและเวลาที่อนุมัติ</p>
                <p style="margin: 4px 0 0; color: #0d4f2e; font-size: 16px; font-weight: 700;">{formatted_time}</p>
            </div>
            <p style="color: #6b9e84; font-size: 13px; line-height: 1.6;">
                ขอบคุณที่ร่วมเป็นส่วนหนึ่งของระบบ
            </p>
        </div>
        <p style="text-align: center; color: #8aab9a; font-size: 12px; margin-top: 20px;">
            อีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ
        </p>
    </div>
    """


def _build_doctor_rejected_html(greeting_name: str, formatted_time: str) -> str:
    return f"""
    <div style="font-family: 'Sarabun', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 24px; background: #f4fbf7; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 36px;">❌</span>
            <h2 style="color: #0d4f2e; margin: 8px 0 0;">แจ้งเตือนการสมัครสมาชิก</h2>
        </div>
        <div style="background: #fff; border-radius: 12px; padding: 20px; border: 1px solid rgba(22,163,97,0.15);">
            <p style="color: #0d4f2e; font-size: 15px; line-height: 1.6;">
                เรียน {greeting_name}
            </p>
            <p style="color: #2d7055; font-size: 15px; line-height: 1.6;">
                ขออภัย คำขอสมัครสมาชิกของท่าน<strong>ไม่ได้รับการอนุมัติ</strong>
                จากแอดมินในครั้งนี้
            </p>
            <div style="background: #e8f5f0; border-radius: 10px; padding: 14px; margin: 16px 0;">
                <p style="margin: 0; color: #4a7c62; font-size: 13px;">วันและเวลาที่ดำเนินการ</p>
                <p style="margin: 4px 0 0; color: #0d4f2e; font-size: 16px; font-weight: 700;">{formatted_time}</p>
            </div>
            <p style="color: #6b9e84; font-size: 13px; line-height: 1.6;">
                หากท่านมีข้อสงสัยเกี่ยวกับผลการพิจารณา กรุณาติดต่อผู้ดูแลระบบ
                เพื่อสอบถามรายละเอียดเพิ่มเติม
            </p>
        </div>
        <p style="text-align: center; color: #8aab9a; font-size: 12px; margin-top: 20px;">
            อีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ
        </p>
    </div>
    """


def send_doctor_approved_notification(to_email: str, full_name: str = "") -> bool:
    """
    ส่งอีเมลแจ้งเตือนหลังแอดมินอนุมัติบัญชีแพทย์สำเร็จ
    คืนค่า True ถ้าส่งสำเร็จ, False ถ้าส่งไม่สำเร็จ
    """
    now = datetime.now(BANGKOK_TZ)
    formatted_time = format_thai_datetime(now)
    greeting_name = full_name if full_name else "ผู้สมัคร"
    html_content = _build_doctor_approved_html(greeting_name, formatted_time)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "แจ้งเตือนการสมัครสมาชิก: บัญชีของท่านได้รับการอนุมัติแล้ว"
    msg["From"] = f"DietAI Security <{settings.gmail_address}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(settings.gmail_address, settings.gmail_app_password)
            server.sendmail(settings.gmail_address, [to_email], msg.as_string())
        logger.info(f"Doctor approved notification sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send doctor approved notification to {to_email}: {e}")
        return False


def send_doctor_rejected_notification(to_email: str, full_name: str = "") -> bool:
    """
    ส่งอีเมลแจ้งเตือนหลังแอดมินปฏิเสธบัญชีแพทย์
    คืนค่า True ถ้าส่งสำเร็จ, False ถ้าส่งไม่สำเร็จ
    """
    now = datetime.now(BANGKOK_TZ)
    formatted_time = format_thai_datetime(now)
    greeting_name = full_name if full_name else "ผู้สมัคร"
    html_content = _build_doctor_rejected_html(greeting_name, formatted_time)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "แจ้งเตือนการสมัครสมาชิก: ผลการพิจารณาบัญชีของท่าน"
    msg["From"] = f"DietAI Security <{settings.gmail_address}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(settings.gmail_address, settings.gmail_app_password)
            server.sendmail(settings.gmail_address, [to_email], msg.as_string())
        logger.info(f"Doctor rejected notification sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send doctor rejected notification to {to_email}: {e}")
        return False