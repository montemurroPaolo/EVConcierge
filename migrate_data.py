#!/usr/bin/env python
"""
Migrate data from db_efisio.sqlite3 (airbnb_* tables) into db.sqlite3 (property_manager_* tables).

Usage:
    cd /home/rcr/Desktop/EVConcierge
    python migrate_data.py

This script:
  1. Reads all relevant data from the external (source) database.
  2. Inserts users (preserving their original IDs where possible, remapping if conflicts occur).
  3. Inserts all dependent tables in the correct FK order.
  4. Maps source column names to destination column names where they differ.
  5. Skips the existing admin user in the target (id=1) and remaps references.
"""

import sqlite3
import sys
import os
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DB = os.path.join(BASE_DIR, "db_efisio.sqlite3")
TARGET_DB = os.path.join(BASE_DIR, "db.sqlite3")


def dict_factory(cursor, row):
    """Convert sqlite3 rows to dicts."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_connection(db_path, readonly=False):
    """Open a connection with dict row factory."""
    if readonly:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def read_all(conn, table):
    """Read all rows from a table."""
    try:
        rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
        return rows
    except Exception as e:
        print(f"  ⚠ Could not read {table}: {e}")
        return []


def insert_row(conn, table, row_dict):
    """Insert a single row dict into a table."""
    cols = list(row_dict.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join([f'"{c}"' for c in cols])
    values = [row_dict[c] for c in cols]
    sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'
    conn.execute(sql, values)


def insert_rows(conn, table, rows, label=None):
    """Insert multiple rows, printing progress."""
    label = label or table
    count = 0
    for row in rows:
        try:
            insert_row(conn, table, row)
            count += 1
        except Exception as e:
            print(f"  ⚠ Error inserting into {table}: {e}")
            print(f"    Row: {row}")
    print(f"  ✓ {label}: {count}/{len(rows)} rows inserted")
    return count


def main():
    print("=" * 70)
    print("  EVConcierge Data Migration")
    print(f"  Source: {SOURCE_DB}")
    print(f"  Target: {TARGET_DB}")
    print("=" * 70)
    print()

    if not os.path.exists(SOURCE_DB):
        print(f"ERROR: Source database not found: {SOURCE_DB}")
        sys.exit(1)
    if not os.path.exists(TARGET_DB):
        print(f"ERROR: Target database not found: {TARGET_DB}")
        sys.exit(1)

    src = get_connection(SOURCE_DB, readonly=True)
    tgt = get_connection(TARGET_DB)

    # ------------------------------------------------------------------
    # 1. Read existing target data
    # ------------------------------------------------------------------
    print("[1/12] Reading existing target data...")
    existing_users = read_all(tgt, "auth_user")
    existing_user_ids = {u["id"] for u in existing_users}
    existing_user_emails = {u["email"].lower(): u["id"] for u in existing_users if u["email"]}
    existing_user_usernames = {u["username"]: u["id"] for u in existing_users}
    
    existing_properties = read_all(tgt, "property_manager_property")
    existing_property_ids = {p["id"] for p in existing_properties}
    print(f"  Existing target users: {len(existing_users)}")
    print(f"  Existing target properties: {len(existing_properties)}")
    print()

    # ------------------------------------------------------------------
    # 2. Migrate auth_user
    # ------------------------------------------------------------------
    print("[2/12] Migrating auth_user...")
    src_users = read_all(src, "auth_user")
    user_id_map = {}  # old_id -> new_id

    for user in src_users:
        old_id = user["id"]
        
        # Check for existing match by email or username
        matched_id = None
        if user["email"] and user["email"].lower() in existing_user_emails:
            matched_id = existing_user_emails[user["email"].lower()]
        elif user["username"] in existing_user_usernames:
            matched_id = existing_user_usernames[user["username"]]
        
        if matched_id:
            user_id_map[old_id] = matched_id
            print(f"  → User '{user['username']}' (id={old_id}) mapped to existing id={matched_id}")
            continue

        # Find a safe id to insert
        new_id = old_id
        while new_id in existing_user_ids:
            new_id += 1000  # offset to avoid conflicts

        user["id"] = new_id
        user_id_map[old_id] = new_id
        existing_user_ids.add(new_id)
        if user["email"]:
            existing_user_emails[user["email"].lower()] = new_id
        existing_user_usernames[user["username"]] = new_id

        try:
            insert_row(tgt, "auth_user", user)
            print(f"  ✓ User '{user['username']}' inserted (old_id={old_id} → new_id={new_id})")
        except Exception as e:
            print(f"  ⚠ Error inserting user '{user['username']}': {e}")

    tgt.commit()
    print(f"  User ID mapping: {user_id_map}")
    print()

    # ------------------------------------------------------------------
    # 3. Migrate UserProfile
    # ------------------------------------------------------------------
    print("[3/12] Migrating UserProfile...")
    src_profiles = read_all(src, "airbnb_userprofile")
    profile_rows = []
    for p in src_profiles:
        new_user_id = user_id_map.get(p["user_id"])
        if not new_user_id:
            print(f"  ⚠ Skipping profile for unmapped user_id={p['user_id']}")
            continue
        # Check if profile already exists
        existing = tgt.execute(
            'SELECT id FROM property_manager_userprofile WHERE user_id = ?', (new_user_id,)
        ).fetchone()
        if existing:
            # Update existing profile with source data
            tgt.execute('''
                UPDATE property_manager_userprofile SET
                    bio = ?, photo = ?, location = ?, instagram = ?,
                    subscription_plan = ?, is_banned = ?,
                    stripe_customer_id = ?, stripe_subscription_id = ?,
                    subscription_status = ?, subscription_end_date = ?,
                    is_gifted = ?, gift_plan = ?, gift_expiry_date = ?,
                    used_trial = ?, pending_fb_purchase_event = ?,
                    preferred_language = ?
                WHERE user_id = ?
            ''', (
                p.get("bio", ""), p.get("photo"), p.get("location", ""),
                p.get("instagram", ""), p.get("subscription_plan", "free"),
                p.get("is_banned", False),
                p.get("stripe_customer_id"), p.get("stripe_subscription_id"),
                p.get("subscription_status"), p.get("subscription_end_date"),
                p.get("is_gifted", False), p.get("gift_plan"),
                p.get("gift_expiry_date"), p.get("used_trial", False),
                p.get("pending_fb_purchase_event"),
                p.get("preferred_language", "original"),
                new_user_id,
            ))
            print(f"  → Updated existing profile for user_id={new_user_id}")
            continue

        row = {
            "id": p["id"],
            "user_id": new_user_id,
            "bio": p.get("bio", ""),
            "photo": p.get("photo"),
            "location": p.get("location", ""),
            "instagram": p.get("instagram", ""),
            "subscription_plan": p.get("subscription_plan", "free"),
            "is_banned": p.get("is_banned", False),
            "stripe_customer_id": p.get("stripe_customer_id"),
            "stripe_subscription_id": p.get("stripe_subscription_id"),
            "subscription_status": p.get("subscription_status"),
            "subscription_end_date": p.get("subscription_end_date"),
            "is_gifted": p.get("is_gifted", False),
            "gift_plan": p.get("gift_plan"),
            "gift_expiry_date": p.get("gift_expiry_date"),
            "used_trial": p.get("used_trial", False),
            "pending_fb_purchase_event": p.get("pending_fb_purchase_event"),
            "preferred_language": p.get("preferred_language", "original"),
        }
        profile_rows.append(row)

    insert_rows(tgt, "property_manager_userprofile", profile_rows, "UserProfile")
    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 4. Migrate Property
    # ------------------------------------------------------------------
    print("[4/12] Migrating Property...")
    src_properties = read_all(src, "airbnb_property")
    property_id_map = {}  # old_id -> new_id
    property_rows = []

    for p in src_properties:
        old_id = p["id"]
        new_owner_id = user_id_map.get(p["owner_id"])
        if not new_owner_id:
            print(f"  ⚠ Skipping property '{p['title']}' — unmapped owner_id={p['owner_id']}")
            continue

        # Check if nickname already exists (skip dups)
        if p.get("nickname"):
            dup = tgt.execute(
                'SELECT id FROM property_manager_property WHERE nickname = ?', (p["nickname"],)
            ).fetchone()
            if dup:
                property_id_map[old_id] = dup["id"]
                print(f"  → Property '{p['title']}' nickname '{p['nickname']}' already exists (id={dup['id']})")
                continue

        new_id = old_id
        while new_id in existing_property_ids:
            new_id += 1000

        property_id_map[old_id] = new_id
        existing_property_ids.add(new_id)

        row = {
            "id": new_id,
            "owner_id": new_owner_id,
            "name": p["title"],  # title → name
            "nickname": p.get("nickname", ""),
            "email": p.get("email", ""),
            "phone": p.get("phone", ""),
            "property_manager_name": p.get("property_manager_name", ""),
            "property_manager_phone": p.get("property_manager_phone", ""),
            "description": p.get("description", ""),
            "ai_summary": p.get("ai_summary", ""),
            "house_rules": "",  # not in source
            "wifi_network": "",  # not in source
            "wifi_password": "",  # not in source
            "emergency_contacts": "",  # not in source
            "is_active": p.get("is_active", True),
            "is_featured": p.get("is_featured", False),
            "property_type": p.get("property_type", "apartment"),
            "room_type": p.get("room_type", "entire_place"),
            "capacity": p.get("capacity", 2),
            "bedrooms": p.get("bedrooms"),
            "beds": p.get("beds", 1),
            "bathrooms": p.get("bathrooms"),
            "size": p.get("size"),
            "address": p.get("address", ""),
            "city": p.get("city", ""),
            "neighborhood": p.get("neighborhood", ""),
            "latitude": p.get("latitude"),
            "longitude": p.get("longitude"),
            "manual_geolocalization": p.get("manual_geolocalization", False),
            "has_wifi": p.get("has_wifi", False),
            "has_air_conditioning": p.get("has_air_conditioning", False),
            "has_heating": p.get("has_heating", False),
            "has_kitchen": p.get("has_kitchen", False),
            "has_washer": p.get("has_washer", False),
            "has_netflix": p.get("has_netflix", False),
            "has_barbecue": p.get("has_barbecue", False),
            "parking": p.get("parking", "none"),
            "parking_price": p.get("parking_price"),
            "pool": p.get("pool", "none"),
            "has_garden": p.get("has_garden", False),
            "has_balcony": p.get("has_balcony", False),
            "check_in_time": p.get("check_in_time"),
            "check_out_time": p.get("check_out_time"),
            "minimum_stay": p.get("minimum_stay", 1),
            "cancellation_policy": p.get("cancellation_policy", "moderate"),
            "pets_allowed": p.get("pets_allowed", False),
            "smoking_allowed": p.get("smoking_allowed", False),
            "parties_allowed": p.get("parties_allowed", False),
            "luggage_storage": p.get("luggage_storage", "none"),
            "luggage_storage_price": p.get("luggage_storage_price"),
            "price_range": p.get("price_range", ""),
            "ical_url": p.get("ical_url", ""),
            "instruction_password": p.get("instruction_password", ""),
            "welcome_message": p.get("welcome_message", ""),
            "view_count": p.get("view_count", 0),
            "created_at": p.get("created_at", datetime.now().isoformat()),
            "updated_at": p.get("updated_at", datetime.now().isoformat()),
        }
        property_rows.append(row)

    insert_rows(tgt, "property_manager_property", property_rows, "Property")
    tgt.commit()
    print(f"  Property ID mapping ({len(property_id_map)} entries)")
    print()

    # ------------------------------------------------------------------
    # 5. Migrate PropertyImage, PropertyBed, PropertyBathroom
    # ------------------------------------------------------------------
    print("[5/12] Migrating Property sub-tables...")

    # PropertyImage
    src_images = read_all(src, "airbnb_propertyimage")
    img_rows = []
    for i in src_images:
        new_prop_id = property_id_map.get(i["property_id"])
        if not new_prop_id:
            continue
        img_rows.append({
            "id": i["id"],
            "property_id": new_prop_id,
            "image": i.get("image", ""),
            "caption": i.get("caption", ""),
            "order": i.get("order", 0),
            "created_at": i.get("created_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_propertyimage", img_rows, "PropertyImage")

    # PropertyBed
    src_beds = read_all(src, "airbnb_propertybed")
    bed_rows = []
    for b in src_beds:
        new_prop_id = property_id_map.get(b["property_id"])
        if not new_prop_id:
            continue
        bed_rows.append({
            "id": b["id"],
            "property_id": new_prop_id,
            "bed_type": b.get("bed_type", "single"),
            "room_name": b.get("room_name", ""),
            "quantity": b.get("quantity", 1),
            "created_at": b.get("created_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_propertybed", bed_rows, "PropertyBed")

    # PropertyBathroom
    src_baths = read_all(src, "airbnb_propertybathroom")
    bath_rows = []
    for b in src_baths:
        new_prop_id = property_id_map.get(b["property_id"])
        if not new_prop_id:
            continue
        bath_rows.append({
            "id": b["id"],
            "property_id": new_prop_id,
            "bathroom_type": b.get("bathroom_type", "full"),
            "location": b.get("location", ""),
            "has_bidet": b.get("has_bidet", False),
            "has_bathtub": b.get("has_bathtub", False),
            "has_shower": b.get("has_shower", True),
            "has_hairdryer": b.get("has_hairdryer", False),
            "created_at": b.get("created_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_propertybathroom", bath_rows, "PropertyBathroom")
    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 6. Migrate Experience
    # ------------------------------------------------------------------
    print("[6/12] Migrating Experience...")
    src_experiences = read_all(src, "airbnb_experience")
    experience_id_map = {}
    exp_rows = []

    for e in src_experiences:
        old_id = e["id"]
        new_owner_id = user_id_map.get(e["owner_id"])
        if not new_owner_id:
            print(f"  ⚠ Skipping experience '{e['title']}' — unmapped owner_id={e['owner_id']}")
            continue
        experience_id_map[old_id] = old_id  # keep same id
        exp_rows.append({
            "id": old_id,
            "owner_id": new_owner_id,
            "title": e.get("title", ""),
            "description": e.get("description", ""),
            "ai_summary": e.get("ai_summary", ""),
            "duration": e.get("duration"),
            "is_active": e.get("is_active", True),
            "is_featured": e.get("is_featured", False),
            "address": e.get("address"),
            "latitude": e.get("latitude"),
            "longitude": e.get("longitude"),
            "manual_geolocalization": e.get("manual_geolocalization", False),
            "category": e.get("category", "experiences"),
            "price": e.get("price", 0),
            "group_size": e.get("group_size", "any_size"),
            "ical_url": e.get("ical_url", ""),
            "booking_method": e.get("booking_method", ""),
            "booking_phone": e.get("booking_phone", ""),
            "booking_link": e.get("booking_link", ""),
            "referral_code": e.get("referral_code", ""),
            "view_count": e.get("view_count", 0),
            "created_at": e.get("created_at", datetime.now().isoformat()),
            "updated_at": e.get("updated_at", datetime.now().isoformat()),
        })

    insert_rows(tgt, "property_manager_experience", exp_rows, "Experience")
    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 7. Migrate ExperienceImage
    # ------------------------------------------------------------------
    print("[7/12] Migrating ExperienceImage...")
    src_exp_imgs = read_all(src, "airbnb_experienceimage")
    exp_img_rows = []
    for i in src_exp_imgs:
        new_exp_id = experience_id_map.get(i["experience_id"])
        if not new_exp_id:
            continue
        exp_img_rows.append({
            "id": i["id"],
            "experience_id": new_exp_id,
            "image": i.get("image", ""),
            "caption": i.get("caption", ""),
            "order": i.get("order", 0),
            "created_at": i.get("created_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_experienceimage", exp_img_rows, "ExperienceImage")
    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 8. Migrate Instruction + InstructionImage
    # ------------------------------------------------------------------
    print("[8/12] Migrating Instruction & InstructionImage...")
    src_instructions = read_all(src, "airbnb_instruction")
    instruction_id_map = {}
    inst_rows = []

    for ins in src_instructions:
        old_id = ins["id"]
        new_prop_id = property_id_map.get(ins["property_id"])
        if not new_prop_id:
            continue
        instruction_id_map[old_id] = old_id
        inst_rows.append({
            "id": old_id,
            "property_id": new_prop_id,
            "title": ins.get("title", ""),
            "content": ins.get("content", ""),
            "instruction_type": ins.get("instruction_type", "other"),
            "video": ins.get("video"),
            "order": ins.get("order", 0),
            "created_at": ins.get("created_at", datetime.now().isoformat()),
            "updated_at": ins.get("updated_at", datetime.now().isoformat()),
        })

    insert_rows(tgt, "property_manager_instruction", inst_rows, "Instruction")

    # InstructionImage
    src_inst_imgs = read_all(src, "airbnb_instructionimage")
    inst_img_rows = []
    for i in src_inst_imgs:
        new_inst_id = instruction_id_map.get(i["instruction_id"])
        if not new_inst_id:
            continue
        inst_img_rows.append({
            "id": i["id"],
            "instruction_id": new_inst_id,
            "image": i.get("image", ""),
            "caption": i.get("caption", ""),
            "is_main": i.get("is_main", False),
            "order": i.get("order", 0),
            "created_at": i.get("created_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_instructionimage", inst_img_rows, "InstructionImage")
    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 9. Migrate PropertyExperience, PropertyCoHost, CoHostRequest
    # ------------------------------------------------------------------
    print("[9/12] Migrating linking tables...")

    # PropertyExperience
    src_pe = read_all(src, "airbnb_propertyexperience")
    pe_rows = []
    for pe in src_pe:
        new_prop = property_id_map.get(pe["property_id"])
        new_exp = experience_id_map.get(pe["experience_id"])
        if not new_prop or not new_exp:
            continue
        pe_rows.append({
            "id": pe["id"],
            "property_id": new_prop,
            "experience_id": new_exp,
            "distance": pe.get("distance", 0),
            "count": pe.get("count", 1),
        })
    insert_rows(tgt, "property_manager_propertyexperience", pe_rows, "PropertyExperience")

    # PropertyCoHost
    src_pch = read_all(src, "airbnb_propertycohost")
    pch_rows = []
    for pch in src_pch:
        new_prop = property_id_map.get(pch["property_id"])
        new_cohost = user_id_map.get(pch["co_host_id"])
        if not new_prop or not new_cohost:
            continue
        pch_rows.append({
            "id": pch["id"],
            "property_id": new_prop,
            "co_host_id": new_cohost,
            "created_at": pch.get("created_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_propertycohost", pch_rows, "PropertyCoHost")

    # CoHostRequest
    src_chr = read_all(src, "airbnb_cohostrequest")
    chr_rows = []
    for cr in src_chr:
        new_prop = property_id_map.get(cr["property_id"])
        new_host = user_id_map.get(cr["host_id"])
        new_cohost = user_id_map.get(cr["co_host_id"])
        if not new_prop or not new_host or not new_cohost:
            continue
        chr_rows.append({
            "id": cr["id"],
            "property_id": new_prop,
            "host_id": new_host,
            "co_host_id": new_cohost,
            "status": cr.get("status", "pending"),
            "message": cr.get("message", ""),
            "created_at": cr.get("created_at", datetime.now().isoformat()),
            "responded_at": cr.get("responded_at"),
        })
    insert_rows(tgt, "property_manager_cohostrequest", chr_rows, "CoHostRequest")
    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 10. Migrate Translations
    # ------------------------------------------------------------------
    print("[10/12] Migrating Translations...")

    # PropertyTranslation
    src_pt = read_all(src, "airbnb_propertytranslation")
    pt_rows = []
    for t in src_pt:
        new_prop = property_id_map.get(t["property_id"])
        if not new_prop:
            continue
        pt_rows.append({
            "id": t["id"],
            "property_id": new_prop,
            "language": t.get("language", "eng"),
            "title": t.get("title", ""),
            "description": t.get("description", ""),
            "ai_summary": t.get("ai_summary", ""),
            "created_at": t.get("created_at", datetime.now().isoformat()),
            "updated_at": t.get("updated_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_propertytranslation", pt_rows, "PropertyTranslation")

    # InstructionTranslation
    src_it = read_all(src, "airbnb_instructiontranslation")
    it_rows = []
    for t in src_it:
        new_inst = instruction_id_map.get(t["instruction_id"])
        if not new_inst:
            continue
        it_rows.append({
            "id": t["id"],
            "instruction_id": new_inst,
            "language": t.get("language", "eng"),
            "title": t.get("title", ""),
            "content": t.get("content", ""),
            "created_at": t.get("created_at", datetime.now().isoformat()),
            "updated_at": t.get("updated_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_instructiontranslation", it_rows, "InstructionTranslation")

    # ExperienceTranslation
    src_et = read_all(src, "airbnb_experiencetranslation")
    et_rows = []
    for t in src_et:
        new_exp = experience_id_map.get(t["experience_id"])
        if not new_exp:
            continue
        et_rows.append({
            "id": t["id"],
            "experience_id": new_exp,
            "language": t.get("language", "eng"),
            "title": t.get("title", ""),
            "description": t.get("description", ""),
            "ai_summary": t.get("ai_summary", ""),
            "created_at": t.get("created_at", datetime.now().isoformat()),
            "updated_at": t.get("updated_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_experiencetranslation", et_rows, "ExperienceTranslation")
    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 11. Migrate ChatLog, Feedback, PromoCode, PromoCodeUsage, DailyView, ExternalLink
    # ------------------------------------------------------------------
    print("[11/12] Migrating ChatLog, Feedback, PromoCode, DailyView, ExternalLink...")

    # ChatLog
    src_cl = read_all(src, "airbnb_chatlog")
    cl_rows = []
    for c in src_cl:
        new_prop = property_id_map.get(c["property_id"])
        if not new_prop:
            continue
        new_user = user_id_map.get(c["user_id"]) if c.get("user_id") else None
        cl_rows.append({
            "id": c["id"],
            "property_id": new_prop,
            "user_question": c.get("user_question", ""),
            "ai_response": c.get("ai_response", ""),
            "session_key": c.get("session_key"),
            "ip_address": c.get("ip_address"),
            "user_agent": c.get("user_agent", ""),
            "is_authenticated": c.get("is_authenticated", False),
            "has_password_access": c.get("has_password_access", False),
            "user_id": new_user,
            "created_at": c.get("created_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_chatlog", cl_rows, "ChatLog")

    # Feedback
    src_fb = read_all(src, "airbnb_feedback")
    fb_rows = []
    for f in src_fb:
        new_user = user_id_map.get(f["user_id"]) if f.get("user_id") else None
        fb_rows.append({
            "id": f["id"],
            "user_id": new_user,
            "name": f.get("name", ""),
            "email": f.get("email", ""),
            "feedback_type": f.get("feedback_type", "general"),
            "subject": f.get("subject", ""),
            "message": f.get("message", ""),
            "rating": f.get("rating"),
            "user_agent": f.get("user_agent", ""),
            "ip_address": f.get("ip_address"),
            "is_read": f.get("is_read", False),
            "admin_notes": f.get("admin_notes", ""),
            "created_at": f.get("created_at", datetime.now().isoformat()),
            "updated_at": f.get("updated_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_feedback", fb_rows, "Feedback")

    # PromoCode
    src_pc = read_all(src, "airbnb_promocode")
    pc_rows = []
    for pc in src_pc:
        new_created_by = user_id_map.get(pc["created_by_id"]) if pc.get("created_by_id") else None
        pc_rows.append({
            "id": pc["id"],
            "code": pc.get("code", ""),
            "description": pc.get("description", ""),
            "gift_plan": pc.get("gift_plan", "free"),
            "duration_months": pc.get("duration_months", 1),
            "max_uses": pc.get("max_uses", 1),
            "current_uses": pc.get("current_uses", 0),
            "valid_from": pc.get("valid_from"),
            "valid_until": pc.get("valid_until"),
            "is_active": pc.get("is_active", True),
            "created_at": pc.get("created_at", datetime.now().isoformat()),
            "updated_at": pc.get("updated_at", datetime.now().isoformat()),
            "created_by_id": new_created_by,
        })
    insert_rows(tgt, "property_manager_promocode", pc_rows, "PromoCode")

    # PromoCodeUsage
    src_pcu = read_all(src, "airbnb_promocodeusage")
    pcu_rows = []
    for u in src_pcu:
        new_user = user_id_map.get(u["user_id"])
        if not new_user:
            continue
        pcu_rows.append({
            "id": u["id"],
            "promo_code_id": u["promo_code_id"],
            "user_id": new_user,
            "used_at": u.get("used_at", datetime.now().isoformat()),
            "ip_address": u.get("ip_address"),
        })
    insert_rows(tgt, "property_manager_promocodeusage", pcu_rows, "PromoCodeUsage")

    # DailyView
    src_dv = read_all(src, "airbnb_dailyview")
    dv_rows = []
    for d in src_dv:
        dv_rows.append({
            "id": d["id"],
            "content_type": d.get("content_type", "property"),
            "object_id": d.get("object_id", 0),
            "date": d.get("date"),
            "view_count": d.get("view_count", 0),
            "created_at": d.get("created_at", datetime.now().isoformat()),
            "updated_at": d.get("updated_at", datetime.now().isoformat()),
        })
    insert_rows(tgt, "property_manager_dailyview", dv_rows, "DailyView")

    # ExternalLink
    src_el = read_all(src, "airbnb_externallink")
    el_rows = []
    for l in src_el:
        new_prop = property_id_map.get(l["property_id"])
        if not new_prop:
            continue
        el_rows.append({
            "id": l["id"],
            "property_id": new_prop,
            "title": l.get("title", ""),
            "url": l.get("url", ""),
            "description": l.get("description", ""),
            "link_type": l.get("link_type", "other"),
        })
    insert_rows(tgt, "property_manager_externallink", el_rows, "ExternalLink")

    tgt.commit()
    print()

    # ------------------------------------------------------------------
    # 12. Final verification
    # ------------------------------------------------------------------
    print("[12/12] Final verification...")
    tables_to_check = [
        "auth_user",
        "property_manager_userprofile",
        "property_manager_property",
        "property_manager_propertyimage",
        "property_manager_propertybed",
        "property_manager_propertybathroom",
        "property_manager_experience",
        "property_manager_experienceimage",
        "property_manager_instruction",
        "property_manager_instructionimage",
        "property_manager_propertyexperience",
        "property_manager_propertycohost",
        "property_manager_cohostrequest",
        "property_manager_propertytranslation",
        "property_manager_instructiontranslation",
        "property_manager_experiencetranslation",
        "property_manager_chatlog",
        "property_manager_feedback",
        "property_manager_promocode",
        "property_manager_promocodeusage",
        "property_manager_dailyview",
        "property_manager_externallink",
    ]

    print(f"  {'Table':<52} {'Count':>8}")
    print(f"  {'-'*52} {'-'*8}")
    for t in tables_to_check:
        try:
            count = tgt.execute(f'SELECT COUNT(*) as c FROM "{t}"').fetchone()["c"]
            print(f"  {t:<52} {count:>8}")
        except Exception as e:
            print(f"  {t:<52} ERROR: {e}")

    print()
    print("=" * 70)
    print("  Migration complete!")
    print("=" * 70)

    src.close()
    tgt.close()


if __name__ == "__main__":
    main()
