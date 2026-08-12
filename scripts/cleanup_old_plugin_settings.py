#!/usr/bin/env python3
"""
Script pentru curățarea setărilor vechi de plugin-uri din app_settings.
Rulează acest script după migrarea la noul sistem de plugin-uri.
"""

import sys
import os

# Adaugă proiectul la path pentru a putea importa modulele
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db import SessionLocal
from app.models.db_models import AppSetting

def cleanup_old_plugin_settings():
    """Șterge setările vechi de plugin-uri din tabelul app_settings"""
    
    # Setările vechi care erau hardcodate în admin
    old_settings = {
        "telegram_bot_token",
        "telegram_notify_chat_id", 
        "telegram_bot_username",
        "newsletter_from_email",
        "newsletter_notify_email",
        "smtp_host",
        "smtp_port",
        "smtp_user",
        "smtp_password",
        "smtp_use_tls",
    }
    
    with SessionLocal() as db:
        # Numărăm câte setări vom șterge
        to_delete = db.query(AppSetting).filter(AppSetting.key.in_(old_settings)).all()
        count = len(to_delete)
        
        if count == 0:
            print("✅ Nu există setări vechi de curățat.")
            return
        
        print(f"🗑️  Se șterg {count} setări vechi:")
        for setting in to_delete:
            print(f"   - {setting.key}")
        
        # Ștergem setările
        db.query(AppSetting).filter(AppSetting.key.in_(old_settings)).delete(synchronize_session=False)
        db.commit()
        
        print(f"✅ {count} setări vechi au fost șterse din app_settings.")

if __name__ == "__main__":
    print("🧹 Curățare setări vechi de plugin-uri...")
    cleanup_old_plugin_settings()
    print("🎉 Gata! Setările vechi au fost eliminate.")
