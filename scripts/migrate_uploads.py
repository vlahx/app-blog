from __future__ import annotations

import os
import shutil

def run_migration():
    from app.models.db_models import User, MediaFile
    from app.utils.db import SessionLocal
    from app.core.config import PROJECT_ROOT
    from sqlalchemy import select
    from datetime import datetime, timezone

    print("Starting Media Uploads Hierarchy Migration...")
    
    with SessionLocal() as db:
        admin_user = db.execute(select(User).where(User.role == "admin")).scalars().first()
        if not admin_user:
            admin_user = db.execute(select(User)).scalars().first()
            
        admin_id = admin_user.id if admin_user else 1
        now = datetime.now(timezone.utc)
        
        # 1. Migrate post images from /static/images/post_images/
        post_img_dir = PROJECT_ROOT / "static" / "images" / "post_images"
        if post_img_dir.is_dir():
            target_dir = PROJECT_ROOT / "static" / "uploads" / "users" / str(admin_id) / "blog"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            for item in post_img_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    dest = target_dir / item.name
                    if not dest.exists():
                        shutil.copy2(item, dest)
                        
                    rel_url = f"/static/uploads/users/{admin_id}/blog/{item.name}"
                    rel_path = f"static/uploads/users/{admin_id}/blog/{item.name}"
                    
                    # Check if already in DB
                    exists = db.execute(select(MediaFile).where(MediaFile.file_url == rel_url)).scalar_one_or_none()
                    if not exists:
                        mf = MediaFile(
                            user_id=admin_id,
                            filename=item.name,
                            file_path=rel_path,
                            file_url=rel_url,
                            file_size=dest.stat().st_size,
                            mime_type="image/jpeg" if item.suffix in (".jpg", ".jpeg") else "image/png",
                            alt_text=item.stem.replace("_", " "),
                            category="blog",
                            created_at=now
                        )
                        db.add(mf)
            db.commit()
            print("Migrated blog post images to /static/uploads/users/{id}/blog/")

        # 2. Migrate shop images from /static/uploads/shop/
        shop_img_dir = PROJECT_ROOT / "static" / "uploads" / "shop"
        if shop_img_dir.is_dir():
            target_shop_dir = PROJECT_ROOT / "static" / "uploads" / "users" / str(admin_id) / "shop"
            target_shop_dir.mkdir(parents=True, exist_ok=True)
            
            for root, dirs, files in os.walk(shop_img_dir):
                for f in files:
                    if f.startswith("."): continue
                    src_p = Path(root) / f
                    dest_p = target_shop_dir / f
                    if not dest_p.exists():
                        shutil.copy2(src_p, dest_p)
                        
                    rel_url = f"/static/uploads/users/{admin_id}/shop/{f}"
                    rel_path = f"static/uploads/users/{admin_id}/shop/{f}"
                    
                    exists = db.execute(select(MediaFile).where(MediaFile.file_url == rel_url)).scalar_one_or_none()
                    if not exists:
                        mf = MediaFile(
                            user_id=admin_id,
                            filename=f,
                            file_path=rel_path,
                            file_url=rel_url,
                            file_size=dest_p.stat().st_size,
                            mime_type="image/jpeg" if dest_p.suffix in (".jpg", ".jpeg") else "image/png",
                            alt_text=dest_p.stem.replace("_", " "),
                            category="shop",
                            created_at=now
                        )
                        db.add(mf)
            db.commit()
            print("Migrated shop images to /static/uploads/users/{id}/shop/")

    print("Media Migration Completed Successfully!")

if __name__ == "__main__":
    run_migration()
