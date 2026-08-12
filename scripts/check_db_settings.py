#!/usr/bin/env python3
"""
Script pentru a verifica setările din baza de date
"""

import sys
import os

# Adaugă proiectul la path pentru a putea importa modulele
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db import SessionLocal
from app.models.db_models import AppSetting

def check_settings():
    """Verifică setările din baza de date"""
    
    with SessionLocal() as db:
        # Căutăm setări legate de email/SMTP
        email_settings = db.query(AppSetting).filter(
            AppSetting.key.like('%email%') | 
            AppSetting.key.like('%smtp%') | 
            AppSetting.key.like('%password%')
        ).all()
        
        print("🔍 Setări legate de email/SMTP din baza de date:")
        for setting in email_settings:
            if 'password' in setting.key.lower():
                print(f"   - {setting.key}: [PAROLĂ ASCUNSĂ]")
            else:
                print(f"   - {setting.key}: {setting.value}")
        
        # Verificăm și setările de plugin-uri noi
        plugin_settings = db.query(AppSetting).filter(
            AppSetting.key.like('plugin_%')
        ).all()
        
        if plugin_settings:
            print("\n🔍 Setări de plugin-uri noi:")
            for setting in plugin_settings:
                if 'password' in setting.key.lower() or 'token' in setting.key.lower():
                    print(f"   - {setting.key}: [SENSIBIL ASCUNS]")
                else:
                    print(f"   - {setting.key}: {setting.value}")
        
        if not email_settings and not plugin_settings:
            print("✅ Nu s-au găsit setări legate de email/SMTP în baza de date")

if __name__ == "__main__":
    check_settings()
