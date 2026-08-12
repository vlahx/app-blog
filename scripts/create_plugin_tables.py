#!/usr/bin/env python3
"""
Script pentru crearea tabelelor noi pentru sistemul de plugin-uri.
Rulează acest script pentru a adăuga tabelele 'plugins' și 'plugin_settings' în baza de date existentă.
"""

import sys
import os

# Adaugă proiectul la path pentru a putea importa modulele
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.db import SessionLocal
from app.models.db_models import Base, Plugin, PluginSetting

def create_plugin_tables():
    """Creează tabelele noi pentru plugin-uri dacă nu există"""
    
    with SessionLocal() as db:
        # Creăm doar tabelele noi, fără a afecta tabelele existente
        try:
            # Creăm tabela plugins
            Plugin.__table__.create(db.bind, checkfirst=True)
            print("✅ Tabela 'plugins' a fost creată (sau exista deja)")
            
            # Creăm tabela plugin_settings  
            PluginSetting.__table__.create(db.bind, checkfirst=True)
            print("✅ Tabela 'plugin_settings' a fost creată (sau exista deja)")
            
            print("🎉 Tabelele pentru sistemul de plugin-uri sunt gata!")
            
        except Exception as e:
            print(f"❌ Eroare la crearea tabelelor: {e}")
            raise

if __name__ == "__main__":
    print("🔨 Creare tabele pentru sistemul de plugin-uri...")
    create_plugin_tables()
