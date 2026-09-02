import re
import sqlite3
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

from config import DATA_DIR, DATABASE_FILE

DB_PATH = DATA_DIR / "executive_voice.db"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ExecutiveDatabase:
    def reset_all_data(self):
        """Wipes all meetings, commitments, sources, categories, audio cache, profiles, and resets to 100% virgin state."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [r[0] for r in cursor.fetchall()]
            for tbl in tables:
                cursor.execute(f"DELETE FROM {tbl}")
            conn.commit()
            logging.info(f"🔥 DATABASE COMPLETELY WIPED: Cleared tables {tables}!")

        # Wipe profiles to clean virgin state
        profiles_dir = DATA_DIR / "profiles"
        if profiles_dir.exists():
            for p_file in profiles_dir.glob("*.json"):
                try:
                    p_file.unlink()
                    logging.info(f"Purged profile file: {p_file}")
                except Exception as e:
                    logging.warning(f"Error purging profile {p_file}: {e}")

        # Wipe audio briefings and audio cache
        cache_dir = DATA_DIR.parent / "cache"
        if cache_dir.exists():
            for item in cache_dir.glob("*"):
                if item.is_file():
                    try:
                        item.unlink()
                    except Exception:
                        pass
                elif item.is_dir() and item.name == "audio_briefings":
                    for sub in item.glob("*"):
                        try:
                            sub.unlink()
                        except Exception:
                            pass

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()
        # self.migrate_from_json_if_needed() disabled for 100% clean control

    
    def get_user_integration(self, service_name: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, service_name, is_active, config_json, updated_at FROM user_integrations WHERE service_name = ? OR id = ?", (service_name, service_name))
            row = cursor.fetchone()
            if row:
                import json
                return {
                    "id": row["id"],
                    "service_name": row["service_name"],
                    "is_connected": bool(row["is_active"]),
                    "config": json.loads(row["config_json"] or "{}"),
                    "updated_at": row["updated_at"]
                }
            return None

    def save_user_integration(self, service_name: str, is_connected: bool = True, config: dict = None):
        import json
        cfg_str = json.dumps(config or {})
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_integrations (id, user_id, service_name, is_active, config_json, updated_at)
                VALUES (?, 'felipe_donato', ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    is_active = excluded.is_active,
                    config_json = excluded.config_json,
                    updated_at = CURRENT_TIMESTAMP
            """, (service_name, service_name, 1 if is_connected else 0, cfg_str))
            conn.commit()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def init_db(self):
        """Creates normalized executive tables for meetings, intelligence, and profiles."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Persistent Custom Categories Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    icon TEXT DEFAULT 'ph-tag',
                    is_deleted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Meetings Table
            
            # WhatsApp Audio Inbox Queue (Real Ingestion Queue)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whatsapp_inbox_queue (
                    message_id TEXT PRIMARY KEY,
                    phone TEXT NOT NULL,
                    sender_name TEXT,
                    chat_name TEXT,
                    is_group INTEGER DEFAULT 0,
                    audio_url TEXT NOT NULL,
                    duration_seconds INTEGER DEFAULT 0,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'PENDING'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    file_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT DEFAULT 'Geral',
                    duration_seconds INTEGER DEFAULT 0,
                    start_time TEXT,
                    audio_path TEXT,
                    audio_url TEXT,
                    doc_path TEXT,
                    executive_summary TEXT,
                    intelligence_json TEXT,
                    transcript_full TEXT,
                    custom_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            try:
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN notification_prefs_json TEXT DEFAULT '{}'")
            except Exception:
                pass


            # Action Items & Commitments Table
            
            # Stakeholder Profiles Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stakeholder_profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    company TEXT,
                    role TEXT,
                    communication_style TEXT,
                    treatment_guidelines TEXT,
                    key_topics_json TEXT DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            
            # Custom Ingestion Channels Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_channels (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT 'ph-microphone',
                    is_deleted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Ensure channel column exists in meetings
            try:
                cursor.execute("ALTER TABLE meetings ADD COLUMN channel TEXT DEFAULT 'Plaud Note Pro'")



            except Exception:
                pass

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commitments (
                    completed_at TIMESTAMP,
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT NOT NULL,
                    owner TEXT,
                    action TEXT NOT NULL,
                    deadline_or_context TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (meeting_id) REFERENCES meetings (file_id) ON DELETE CASCADE
                )
            """)
            # Ensure optional commitment columns exist
            for col in ['completed_at TIMESTAMP', 'rationale_why TEXT', 'rationale_how TEXT']:
                try:
                    cursor.execute(f"ALTER TABLE commitments ADD COLUMN {col}")
                except Exception:
                    pass
            # Ensure columns value_amount and quote_citation exist in accounts_deals
            try:
                cursor.execute("ALTER TABLE accounts_deals ADD COLUMN value_amount INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE accounts_deals ADD COLUMN quote_citation TEXT DEFAULT ''")
            except Exception:
                pass


            # Inferred Feedback & Exclusions Learning Engine (Zero Hallucination Guardrail)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inferred_exclusions_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_name TEXT NOT NULL,
                    reason TEXT DEFAULT 'REMOVED_BY_USER',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Deals & Accounts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts_deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    opportunity_or_risk TEXT,
                    next_step TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (meeting_id) REFERENCES meetings (file_id) ON DELETE CASCADE
                )
            """)
            # Ensure columns value_amount and quote_citation exist in accounts_deals
            try:
                cursor.execute("ALTER TABLE accounts_deals ADD COLUMN value_amount INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE accounts_deals ADD COLUMN quote_citation TEXT DEFAULT ''")
            except Exception:
                pass


            # User Profiles & Calibrated Context
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    company TEXT,
                    preferred_voice_tone TEXT,
                    elevenlabs_voice_id TEXT,
                    calibration_meetings_processed INTEGER DEFAULT 0,
                    calibration_target INTEGER DEFAULT 10,
                    calibration_status TEXT DEFAULT 'LEARNING',
                    vocabulary_json TEXT,
                    stakeholders_json TEXT,
                    style_preferences_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            try:
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN notification_prefs_json TEXT DEFAULT '{}'")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN saved_minutes_per_meeting INTEGER DEFAULT 20")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN time_multiplier REAL DEFAULT 1.5")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN profession_area TEXT DEFAULT 'general'")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN whatsapp_phone TEXT DEFAULT '+55 11 97430-7292'")
            except Exception:
                pass


            # Integrations Log & Config
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_integrations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    config_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS keyword_feedback (
                    user_id TEXT NOT NULL,
                    term TEXT NOT NULL,
                    vote INTEGER NOT NULL,
                    last_voted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, term)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whatsapp_verification_codes (
                    phone TEXT PRIMARY KEY,
                    otp_code TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    verified INTEGER DEFAULT 0,
                    user_id TEXT DEFAULT 'felipe_donato',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meeting_source_links (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(file_id) ON DELETE CASCADE
                )
            """)

            conn.commit()
            logging.info(f"SQLite database initialized at {self.db_path}")

    def migrate_from_json_if_needed(self):
        """Migrates legacy meetings_db.json into SQLite if DB is empty."""
        if not DATABASE_FILE.exists():
            return
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM meetings")
            count = cursor.fetchone()["count"]
            if count > 0:
                return  # Already has data

            try:
                with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)

                for m in legacy_data:
                    intel = m.get("intelligence", {})
                    cursor.execute("""
                        INSERT OR REPLACE INTO meetings (
                            file_id, title, category, duration_seconds, start_time,
                            audio_path, audio_url, doc_path, executive_summary,
                            intelligence_json, custom_notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        m.get("file_id"),
                        intel.get("meeting_title", m.get("title", "Sem Título")),
                        intel.get("category", "Comercial"),
                        m.get("duration", 0),
                        m.get("date", ""),
                        m.get("audio_path", ""),
                        m.get("audio_url", ""),
                        m.get("doc_path", ""),
                        intel.get("executive_summary", ""),
                        json.dumps(intel, ensure_ascii=False),
                        m.get("custom_notes", "")
                    ))

                    # Insert commitments
                    for c in intel.get("commitments_and_promises", []):
                        cursor.execute("""
                            INSERT INTO commitments (meeting_id, owner, action, deadline_or_context)
                            VALUES (?, ?, ?, ?)
                        """, (m.get("file_id"), c.get("owner", "Felipe"), c.get("action", ""), c.get("deadline_or_context", "")))

                    # Insert accounts
                    for acc in intel.get("accounts_discussed", []):
                        cursor.execute("""
                            INSERT INTO accounts_deals (meeting_id, account_name, opportunity_or_risk, next_step)
                            VALUES (?, ?, ?, ?)
                        """, (m.get("file_id"), acc.get("account_name", ""), acc.get("opportunity_or_risk", ""), acc.get("next_step", "")))

                conn.commit()
                logging.info(f"Successfully migrated {len(legacy_data)} meetings to SQLite DB.")
            except Exception as e:
                logging.error(f"Error during legacy migration: {e}")

    def get_all_meetings(self, channel: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM meetings WHERE 1=1"
            params = []
            if user_id:
                query += " AND (user_id = ? OR user_id IS NULL OR user_id = 'default_user')"
                params.append(user_id)
            if channel:
                query += " AND (channel LIKE ? OR custom_notes LIKE ? OR title LIKE ?)"
                params.extend([f"%{channel}%", f"%{channel}%", f"%{channel}%"])
            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            meetings = []
            for r in rows:
                m_dict = dict(r)
                if m_dict.get("intelligence_json"):
                    try:
                        m_dict["intelligence"] = json.loads(m_dict["intelligence_json"])
                    except Exception:
                        m_dict["intelligence"] = {}
                else:
                    m_dict["intelligence"] = {}
                m_dict["transcription"] = m_dict.get("transcript_full") or ""
                m_dict["transcript"] = m_dict.get("transcript_full") or ""
                # Ensure channel is explicitly set
                c_val = m_dict.get("channel")
                if not c_val:
                    if "WhatsApp" in (m_dict.get("custom_notes") or "") or "WhatsApp" in (m_dict.get("title") or ""):
                        c_val = "WhatsApp Cloud API"
                    else:
                        c_val = "Plaud Note Pro"
                m_dict["channel"] = c_val
                meetings.append(m_dict)
            return meetings

    def get_meeting(self, file_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meetings WHERE file_id = ?", (file_id,))
            row = cursor.fetchone()
            if not row:
                return None
            m_dict = dict(row)
            if m_dict.get("intelligence_json"):
                try:
                    m_dict["intelligence"] = json.loads(m_dict["intelligence_json"])
                except Exception:
                    m_dict["intelligence"] = {}
            return m_dict

    def save_meeting(self, meeting_data: Dict[str, Any]):
        intel = meeting_data.get("intelligence", {})
        file_id = meeting_data.get("file_id")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            t_full = meeting_data.get("transcript_full") or meeting_data.get("transcription") or meeting_data.get("transcript") or ""
            cursor.execute("""
                INSERT OR REPLACE INTO meetings (
                    file_id, title, category, duration_seconds, start_time,
                    audio_path, audio_url, doc_path, executive_summary,
                    intelligence_json, transcript_full, custom_notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                file_id,
                intel.get("meeting_title", meeting_data.get("title", "Sem Título")),
                intel.get("category", meeting_data.get("category", "Geral")),
                meeting_data.get("duration_seconds", meeting_data.get("duration", 0)),
                meeting_data.get("start_time", meeting_data.get("date", datetime.now().isoformat())),
                meeting_data.get("audio_path", ""),
                meeting_data.get("audio_url", ""),
                meeting_data.get("doc_path", ""),
                intel.get("executive_summary", meeting_data.get("executive_summary", "")),
                json.dumps(intel, ensure_ascii=False),
                t_full,
                meeting_data.get("custom_notes", "")
            ))

            # Refresh commitments
            cursor.execute("DELETE FROM commitments WHERE meeting_id = ?", (file_id,))
            for c in intel.get("commitments_and_promises", []):
                cursor.execute("""
                    INSERT INTO commitments (meeting_id, owner, action, deadline_or_context)
                    VALUES (?, ?, ?, ?)
                """, (file_id, c.get("owner", ""), c.get("action", ""), c.get("deadline_or_context", "")))

            # Refresh accounts
            cursor.execute("DELETE FROM accounts_deals WHERE meeting_id = ?", (file_id,))
            for acc in intel.get("accounts_discussed", []):
                cursor.execute("""
                    INSERT INTO accounts_deals (meeting_id, account_name, opportunity_or_risk, next_step, value_amount, quote_citation)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    file_id, 
                    acc.get("account_name", ""), 
                    acc.get("opportunity_or_risk", ""), 
                    acc.get("next_step", ""),
                    acc.get("value_amount", 0),
                    acc.get("quote_citation", "")
                ))

            conn.commit()

    def update_meeting_notes(self, file_id: str, custom_notes: Optional[str] = None, executive_summary: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if custom_notes is not None:
                cursor.execute("UPDATE meetings SET custom_notes = ?, updated_at = CURRENT_TIMESTAMP WHERE file_id = ?", (custom_notes, file_id))
            if executive_summary is not None:
                cursor.execute("SELECT intelligence_json FROM meetings WHERE file_id = ?", (file_id,))
                row = cursor.fetchone()
                if row and row["intelligence_json"]:
                    try:
                        intel = json.loads(row["intelligence_json"])
                        intel["executive_summary"] = executive_summary
                        cursor.execute("""
                            UPDATE meetings 
                            SET executive_summary = ?, intelligence_json = ?, updated_at = CURRENT_TIMESTAMP 
                            WHERE file_id = ?
                        """, (executive_summary, json.dumps(intel, ensure_ascii=False), file_id))
                    except Exception as e:
                        logging.error(f"Error updating summary json: {e}")
            conn.commit()

    def update_meeting_full(self, file_id: str, title: Optional[str] = None, executive_summary: Optional[str] = None, custom_notes: Optional[str] = None) -> bool:
        """Updates meeting title, executive summary and custom notes in SQLite."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meetings WHERE file_id = ?", (file_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            intel = {}
            if row["intelligence_json"]:
                try:
                    intel = json.loads(row["intelligence_json"])
                except Exception:
                    intel = {}
            
            new_title = title if title is not None else row["title"]
            new_summary = executive_summary if executive_summary is not None else row["executive_summary"]
            new_notes = custom_notes if custom_notes is not None else row["custom_notes"]
            
            intel["meeting_title"] = new_title
            intel["executive_summary"] = new_summary
            
            cursor.execute("""
                UPDATE meetings
                SET title = ?, executive_summary = ?, custom_notes = ?, intelligence_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE file_id = ?
            """, (new_title, new_summary, new_notes, json.dumps(intel, ensure_ascii=False), file_id))
            conn.commit()
            return True


        # Also update meetings_db.json
        try:
            if DATABASE_FILE.exists():
                with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for m in data:
                    if m.get("file_id") == file_id:
                        m["title"] = new_title
                        if "intelligence" in m and isinstance(m["intelligence"], dict):
                            m["intelligence"]["meeting_title"] = new_title
                with open(DATABASE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Error updating title in JSON: {e}")

    def delete_meeting(self, file_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM commitments WHERE meeting_id = ?", (file_id,))
            cursor.execute("DELETE FROM accounts_deals WHERE meeting_id = ?", (file_id,))
            cursor.execute("DELETE FROM meeting_source_links WHERE meeting_id = ?", (file_id,))
            cursor.execute("DELETE FROM meetings WHERE file_id = ?", (file_id,))
            conn.commit()
        try:
            if DATABASE_FILE.exists():
                with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data = [m for m in data if m.get("file_id") != file_id]
                with open(DATABASE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Clean audio briefings
            briefing_file = DATA_DIR.parent / "cache" / "audio_briefings" / f"{file_id}_briefing.mp3"
            if briefing_file.exists():
                briefing_file.unlink()
        except Exception as e:
            logging.error(f"Error deleting meeting files/JSON: {e}")



    def get_all_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all commitments/tasks across all meetings with meeting metadata.
        Completed tasks naturally sink to the bottom. Tasks completed >24h are flagged as ARCHIVED.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Auto-archive tasks completed over 24 hours ago
            cursor.execute("""
                UPDATE commitments 
                SET status = 'ARCHIVED' 
                WHERE status = 'DONE' 
                  AND completed_at IS NOT NULL 
                  AND datetime(completed_at) <= datetime('now', '-24 hours')
            """)
            conn.commit()

            query = """
                SELECT c.id, c.meeting_id, c.owner, c.action, c.deadline_or_context, c.status, c.created_at, c.completed_at,
                       m.title as meeting_title, m.category as meeting_category, m.start_time
                FROM commitments c
                LEFT JOIN meetings m ON c.meeting_id = m.file_id
            """
            params = []
            if status and status != "ALL":
                query += " WHERE c.status = ?"
                params.append(status)
            
            # Ordering: Active tasks first (PENDING/DELEGATED), then DONE at bottom, then ARCHIVED
            query += """
                ORDER BY 
                    CASE 
                        WHEN c.status = 'PENDING' THEN 0 
                        WHEN c.status = 'DELEGATED' THEN 1 
                        WHEN c.status = 'DONE' THEN 2 
                        ELSE 3 
                    END ASC,
                    c.id DESC
            """
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_task_status(self, task_id: int, status: str) -> bool:
        """Updates task status (PENDING, DONE, DELEGATED, CANCELLED, ARCHIVED) and updates completed_at timestamp."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status == 'DONE':
                cursor.execute("""
                    UPDATE commitments 
                    SET status = 'DONE', completed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (task_id,))
            else:
                cursor.execute("""
                    UPDATE commitments 
                    SET status = ?, completed_at = NULL 
                    WHERE id = ?
                """, (status, task_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_task_details(self, task_id: int, action: Optional[str] = None, owner: Optional[str] = None, deadline: Optional[str] = None, rationale_why: Optional[str] = None, rationale_how: Optional[str] = None) -> bool:
        """Updates task action, owner, deadline, and strategic rationale line-by-line."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if action is not None:
                updates.append("action = ?")
                params.append(action)
            if owner is not None:
                updates.append("owner = ?")
                params.append(owner)
            if deadline is not None:
                updates.append("deadline_or_context = ?")
                params.append(deadline)
            if rationale_why is not None:
                updates.append("rationale_why = ?")
                params.append(rationale_why)
            if rationale_how is not None:
                updates.append("rationale_how = ?")
                params.append(rationale_how)
            
            if not updates:
                return False
            
            params.append(task_id)
            cursor.execute(f"UPDATE commitments SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            return cursor.rowcount > 0

    def create_task(self, meeting_id: str, action: str, owner: str = "Felipe Donato", deadline: str = "Hoje", user_id: str = "felipe_donato") -> int:
        """Creates a new task/commitment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO commitments (meeting_id, owner, action, deadline_or_context, status, user_id)
                VALUES (?, ?, ?, ?, 'PENDING', ?)
            """, (meeting_id, owner, action, deadline, user_id))
            conn.commit()
            return cursor.lastrowid


# --- Analytics & Feedback Extension ---

def init_analytics_tables():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_feedback (
                user_id TEXT NOT NULL,
                term TEXT NOT NULL,
                term_type TEXT DEFAULT 'KEYWORD', -- 'KEYWORD', 'STAKEHOLDER', 'TOPIC'
                vote TEXT DEFAULT 'NEUTRAL',     -- 'UP', 'DOWN', 'NEUTRAL'
                frequency INTEGER DEFAULT 1,
                last_voted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, term)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_source_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                source_type TEXT DEFAULT 'PLAUD', -- 'PLAUD', 'MEETING_REF', 'URL', 'DOC'
                source_title TEXT NOT NULL,
                source_ref TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings (file_id) ON DELETE CASCADE
            )
        """)
        conn.commit()

# init_analytics_tables called inside ExecutiveDatabase.init_db


def get_keyword_analytics(user_id: str = "felipe_donato") -> Dict[str, Any]:
    """Aggregates spoken terms, pipeline and metrics STRICTLY from SQLite database dynamically."""
    meetings = db.get_all_meetings()
    
    # 1. Dynamically extract candidate terms from existing meetings in SQLite
    term_counts = {}
    term_categories = {}

    for m in meetings:
        intel = m.get("intelligence", {})
        
        # Extract tags
        for tag in intel.get("tags", []):
            if tag and len(tag) > 2:
                t_clean = tag.strip()
                term_counts[t_clean] = term_counts.get(t_clean, 0) + 1
                term_categories[t_clean] = "Tag da Reunião"
        
        # Extract accounts
        for acc in intel.get("accounts_discussed", []):
            name = acc.get("account_name")
            if name:
                n_clean = name.strip()
                term_counts[n_clean] = term_counts.get(n_clean, 0) + 2
                term_categories[n_clean] = "Conta / Empresa"
                
        # Extract participants
        for part in intel.get("participants", []):
            p_name = part.get("name")
            if p_name and p_name.lower() not in ["felipe", "felipe donato", "você"]:
                p_clean = p_name.strip()
                term_counts[p_clean] = term_counts.get(p_clean, 0) + 1
                term_categories[p_clean] = part.get("role") or "Interlocutor"

    # Fetch user votes
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT term, vote FROM keyword_feedback WHERE user_id = ?", (user_id,))
        votes = {row["term"]: row["vote"] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) as c, COALESCE(SUM(value_amount), 0) as total_val FROM accounts_deals")
        r_deals = cursor.fetchone()
        real_deals_count = r_deals["c"] if r_deals else 0
        real_total_val = r_deals["total_val"] if r_deals else 0

    pending_unvoted = []
    voted_up = []
    voted_down = []

    # Sort terms by frequency
    sorted_terms = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)

    for term, count in sorted_terms:
        v = votes.get(term, "NEUTRAL")
        item = {
            "term": term,
            "category": term_categories.get(term, "Vocabulário"),
            "count": count,
            "vote": v
        }
        if v == "NEUTRAL":
            pending_unvoted.append(item)
        elif v == "UP":
            voted_up.append(item)
        elif v == "DOWN":
            voted_down.append(item)

    active_terms = pending_unvoted[:6]

    # Dynamic metrics based on actual meetings
    total_meetings = len(meetings)
    hours_saved = round((total_meetings * 45) / 60, 1) if total_meetings > 0 else 0.0
    deals_count = real_deals_count if total_meetings > 0 else 0
    pipeline_value = f"R$ {int(real_total_val/1000)}k" if (total_meetings > 0 and real_total_val > 0) else "R$ 0"

    # Unified dynamic stakeholders list
    stakeholders_list = get_unified_stakeholders_list() if total_meetings > 0 else []

    return {
        "user_id": user_id,
        "hours_saved": hours_saved,
        "meetings_count": total_meetings,
        "pipeline_total": pipeline_value,
        "deals_count": deals_count,
        "bifocal": {
            "hours_saved": hours_saved,
            "meetings_processed": total_meetings,
            "automation_rate": "100%" if total_meetings > 0 else "0%",
            "deals_mapped": deals_count,
            "pipeline_value": pipeline_value,
            "focus_quote": "Lente 1: Custo Marginal Zero • Lente 2: Geração de Receita B2B"
        },
        "terms": active_terms,
        "all_pending_terms": pending_unvoted,
        "total_calibrated": len(voted_up),
        "total_discarded": len(voted_down),
        "stakeholders": stakeholders_list
    }


def record_keyword_vote(user_id: str, term: str, vote: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO keyword_feedback (user_id, term, vote, last_voted)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, term) DO UPDATE SET
                vote = excluded.vote,
                last_voted = CURRENT_TIMESTAMP
        """, (user_id, term, vote))
        conn.commit()

def link_meeting_source(meeting_id: str, source_type: str, source_title: str, source_ref: str = ""):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meeting_source_links (meeting_id, source_type, source_title, source_ref)
            VALUES (?, ?, ?, ?)
        """, (meeting_id, source_type, source_title, source_ref))
        conn.commit()

def get_meeting_sources(meeting_id: str) -> List[Dict[str, Any]]:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM meeting_source_links WHERE meeting_id = ? ORDER BY created_at ASC", (meeting_id,))
        return [dict(r) for r in cursor.fetchall()]

record_keyword_feedback = record_keyword_vote


STAKEHOLDER_PROFILES = {}

def get_stakeholder_profile_data(name: str) -> dict:
    clean_name = name.lower().strip()
    # 1. Check SQLite persisted profiles
    persisted = get_persisted_stakeholder_profile(name)
    if persisted:
        return persisted

    # 2. Check defaults
    for key, prof in STAKEHOLDER_PROFILES.items():
        if key in clean_name or clean_name in key:
            return prof

    # 3. Dynamic default
    return {
        "name": name,
        "company": "Parceiro / Cliente",
        "role": "Stakeholder Executivo",
        "communication_style": "C-Level Profissional (Foco em Resultados e Clareza)",
        "treatment_guidelines": f"Tratar {name} com tom executivo, elegante e focado em ações claras e alinhamentos imediatos.",
        "key_topics": []
    }



def get_all_deals_breakdown() -> list:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.id, d.meeting_id, d.account_name, d.opportunity_or_risk, d.next_step, 
                   COALESCE(d.value_amount, 0) as value_amount, 
                   COALESCE(d.quote_citation, '') as quote_citation,
                   COALESCE(m.title, 'Reunião Mapeada') as meeting_title,
                   COALESCE(m.start_time, '') as meeting_date
            FROM accounts_deals d
            LEFT JOIN meetings m ON d.meeting_id = m.file_id
            ORDER BY d.id DESC
        """)
        rows = cursor.fetchall()
        deals = [dict(r) for r in rows]
        
        # Link tasks for each deal
        for d in deals:
            acc = d.get('account_name', '')
            m_id = d.get('meeting_id', '')
            cursor.execute("""
                SELECT id, meeting_id, owner, action, deadline_or_context, status 
                FROM commitments 
                WHERE meeting_id = ? OR action LIKE ?
            """, (m_id, f"%{acc}%"))
            d['tasks'] = [dict(t) for t in cursor.fetchall()]
        return deals

def delete_deal_by_id(deal_id: int):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Find deal name first
        cursor.execute("SELECT account_name FROM accounts_deals WHERE id = ?", (deal_id,))
        row = cursor.fetchone()
        acc_name = row["account_name"] if row else "Unknown"

        # Record negative feedback rule
        cursor.execute("""
            INSERT INTO inferred_exclusions_feedback (entity_type, entity_name, reason)
            VALUES ('deal', ?, 'DISCARDED_BY_USER_AS_NON_DEAL')
        """, (acc_name,))

        cursor.execute("DELETE FROM accounts_deals WHERE id = ?", (deal_id,))
        conn.commit()
        logging.info(f"Auto-correction learned: '{acc_name}' excluded from deals pipeline.")


def get_all_persistent_categories() -> list:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, icon FROM custom_categories WHERE is_deleted = 0 ORDER BY created_at ASC")
        rows = cursor.fetchall()
        cats = [dict(r) for r in rows]
        
        # Also include any categories present in meetings that are not deleted
        cursor.execute("SELECT DISTINCT category FROM meetings WHERE category IS NOT NULL AND category != 'Geral' AND category != ''")
        m_cats = [r["category"] for r in cursor.fetchall()]
        
        existing_names = {c["name"].lower() for c in cats}
        for mc in m_cats:
            if mc.lower() not in existing_names:
                cats.append({"id": f"cat-{mc.lower().replace(' ', '-')}", "name": mc, "icon": "ph-tag"})
                existing_names.add(mc.lower())
        return cats

def create_persistent_category(name: str, icon: str = "ph-tag") -> dict:
    cat_id = f"cat-{int(datetime.now().timestamp())}"
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO custom_categories (id, name, icon, is_deleted)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(name) DO UPDATE SET is_deleted = 0, icon = excluded.icon
        """, (cat_id, name, icon))
        conn.commit()
    return {"id": cat_id, "name": name, "icon": icon}

def rename_category(old_name: str, new_name: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM custom_categories WHERE id = ? OR name = ?", (old_name, old_name))
        row = cursor.fetchone()
        current_name = row["name"] if row else old_name
        cursor.execute("UPDATE custom_categories SET name = ? WHERE id = ? OR name = ?", (new_name, old_name, current_name))
        cursor.execute("UPDATE meetings SET category = ? WHERE category = ?", (new_name, current_name))
        conn.commit()

def delete_category(cat_name: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM custom_categories WHERE id = ? OR name = ?", (cat_name, cat_name))
        row = cursor.fetchone()
        actual_name = row["name"] if row else cat_name
        cursor.execute("DELETE FROM custom_categories WHERE id = ? OR name = ?", (cat_name, actual_name))
        cursor.execute("UPDATE meetings SET category = 'Geral' WHERE category = ?", (actual_name,))
        # Record exclusion feedback
        cursor.execute("""
            INSERT INTO inferred_exclusions_feedback (entity_type, entity_name, reason)
            VALUES ('category', ?, 'DELETED_BY_USER')
        """, (actual_name,))
        conn.commit()
        logging.info(f"Category '{actual_name}' permanently deleted and recorded in exclusion feedback.")


def get_user_notification_preferences(user_id: str = "felipe_donato") -> dict:
    default_prefs = {
        "wa_ingest": True,
        "wa_morning": True,
        "wa_call_ready": True,
        "email_closing": True,
        "email_weekly": True
    }
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT notification_prefs_json FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["notification_prefs_json"]:
            try:
                loaded = json.loads(row["notification_prefs_json"])
                default_prefs.update(loaded)
            except Exception:
                pass
    return default_prefs

def save_user_notification_preferences(user_id: str = "felipe_donato", prefs: dict = None):
    if not prefs:
        return
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profiles (user_id, user_name, notification_prefs_json)
            VALUES (?, 'Usuário', ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                notification_prefs_json = excluded.notification_prefs_json,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, json.dumps(prefs)))
        conn.commit()


def get_user_efficiency_settings(user_id: str = "default_user") -> dict:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT saved_minutes_per_meeting, time_multiplier FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["saved_minutes_per_meeting"] is not None:
            return {
                "saved_minutes_per_meeting": row["saved_minutes_per_meeting"],
                "time_multiplier": row["time_multiplier"] or 1.5
            }
    return {
        "saved_minutes_per_meeting": 20,
        "time_multiplier": 1.5
    }


def save_user_efficiency_settings(user_id: str = "default_user", saved_minutes: int = 20, multiplier: float = 1.5):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profiles (user_id, user_name, saved_minutes_per_meeting, time_multiplier)
            VALUES (?, 'Usuário', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                saved_minutes_per_meeting = excluded.saved_minutes_per_meeting,
                time_multiplier = excluded.time_multiplier,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, saved_minutes, multiplier))
        conn.commit()


def update_deal_value(deal_id: int, new_value: int):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts_deals SET value_amount = ? WHERE id = ?", (new_value, deal_id))
        conn.commit()
        logging.info(f"Updated deal {deal_id} value to R$ {new_value}")


def save_stakeholder_profile(prof: dict):
    clean_id = prof.get("name", "").lower().strip()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO stakeholder_profiles (id, name, company, role, communication_style, treatment_guidelines, key_topics_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                company = excluded.company,
                role = excluded.role,
                communication_style = excluded.communication_style,
                treatment_guidelines = excluded.treatment_guidelines,
                key_topics_json = excluded.key_topics_json,
                updated_at = CURRENT_TIMESTAMP
        """, (
            clean_id,
            prof.get("name", ""),
            prof.get("company", ""),
            prof.get("role", ""),
            prof.get("communication_style", "C-Level Profissional"),
            prof.get("treatment_guidelines", ""),
            json.dumps(prof.get("key_topics", []))
        ))
        conn.commit()
        logging.info(f"Saved stakeholder profile for '{prof.get('name')}'")

def get_persisted_stakeholder_profile(name: str) -> dict:
    clean_id = name.lower().strip()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stakeholder_profiles WHERE id = ? OR id LIKE ?", (clean_id, f"%{clean_id}%"))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            try:
                d["key_topics"] = json.loads(d.get("key_topics_json", "[]"))
            except Exception:
                d["key_topics"] = []
            return d
    return None


def get_unified_stakeholders_list() -> list:
    """Scans all meetings and SQLite profiles to produce a single SSOT stakeholder directory dynamically."""
    meetings = db.get_all_meetings()
    all_tasks = db.get_all_tasks()
    
    stk_map = {}

    # 2. Scan all meetings
    for m in meetings:
        intel = m.get("intelligence", {})
        participants = intel.get("participants", [])
        m_title = m.get("title", "")
        m_id = m.get("file_id", "")
        m_date = m.get("start_time", "")
        
        for p in participants:
            p_name = p.get("name", "").strip()
            if not p_name or p_name.lower() in ["felipe", "felipe donato", "você"]:
                continue
            k = p_name.lower().strip()
            if k not in stk_map:
                stk_map[k] = {
                    "name": p_name,
                    "role": p.get("role", "Stakeholder Executivo"),
                    "company": "",
                    "participated": 0,
                    "mentioned": 0,
                    "treatment_guidelines": f"Tratar {p_name} com tom executivo e foco em alinhamentos claros.",
                    "meetings": []
                }
            stk_map[k]["participated"] += 1
            stk_map[k]["meetings"].append({"title": m_title, "file_id": m_id, "start_time": m_date})

    # 3. Check SQLite overrides
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stakeholder_profiles")
        for row in cursor.fetchall():
            k = row["id"].lower().strip()
            if k in stk_map:
                if row["name"]: stk_map[k]["name"] = row["name"]
                if row["role"]: stk_map[k]["role"] = row["role"]
                if row["company"]: stk_map[k]["company"] = row["company"]
                if row["treatment_guidelines"]: stk_map[k]["treatment_guidelines"] = row["treatment_guidelines"]

    results = []
    for k, s in stk_map.items():
        p_count = s["participated"]
        m_count = s["mentioned"]
        
        rel_tasks = [
            {"id": t.get("id"), "action": t.get("action"), "deadline": t.get("deadline_or_context"), "status": t.get("status")}
            for t in all_tasks if s["name"].split()[0].lower() in (t.get("owner") or "").lower()
        ]
        
        act_label = f"👥 Participou de {p_count} call • 🗣️ Citado(a) {m_count}x nas falas"

        results.append({
            "name": s["name"],
            "role": s["role"],
            "company": s["company"],
            "communication_style": s.get("communication_style", "C-Level Profissional"),
            "treatment_guidelines": s.get("treatment_guidelines", ""),
            "count": p_count,
            "participated_count": p_count,
            "mentioned_count": m_count,
            "activity_label": act_label,
            "meetings": s["meetings"],
            "tasks": rel_tasks
        })
        
    return sorted(results, key=lambda x: x["count"], reverse=True)


def get_all_persistent_channels() -> list:
    default_channels = [
        {"id": "whatsapp", "name": "WhatsApp", "icon": "ph-whatsapp-logo"},
        {"id": "call", "name": "Ligação Telefônica", "icon": "ph-phone-call"},
        {"id": "video", "name": "Videoconferência (Meet/Zoom)", "icon": "ph-video-camera"},
        {"id": "presential", "name": "Reunião Presencial", "icon": "ph-users"},
        {"id": "podcast", "name": "Podcast / Entrevista", "icon": "ph-broadcast"}
    ]
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, icon FROM custom_channels WHERE is_deleted = 0 ORDER BY created_at ASC")
        rows = cursor.fetchall()
        db_channels = [dict(r) for r in rows]
        
        existing_names = {c["name"].lower() for c in db_channels}
        # Insert defaults if table is empty
        if not db_channels:
            for d in default_channels:
                cursor.execute("INSERT OR IGNORE INTO custom_channels (id, name, icon) VALUES (?, ?, ?)", (d["id"], d["name"], d["icon"]))
            conn.commit()
            return default_channels
            
        return db_channels

def create_custom_channel(name: str, icon: str = "ph-microphone") -> dict:
    chan_id = f"chan_{re.sub(r'[^a-zA-Z0-9]', '_', name.lower())}"
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO custom_channels (id, name, icon, is_deleted)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET is_deleted = 0, name = excluded.name, icon = excluded.icon
        """, (chan_id, name, icon))
        conn.commit()
    return {"id": chan_id, "name": name, "icon": icon}

def delete_custom_channel(channel_name: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_channels WHERE name = ?", (channel_name,))
        conn.commit()

def update_meeting_channel(file_id: str, channel_name: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE meetings SET channel = ? WHERE file_id = ?", (channel_name, file_id))
        conn.commit()


def save_whatsapp_inbox_item(item: Dict[str, Any]):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO whatsapp_inbox_queue 
            (message_id, phone, sender_name, chat_name, is_group, audio_url, duration_seconds, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["message_id"],
            item["phone"],
            item.get("sender_name", item["phone"]),
            item.get("chat_name", item["phone"]),
            1 if item.get("is_group") else 0,
            item["audio_url"],
            item.get("duration_seconds", 0),
            item.get("status", "PENDING")
        ))
        conn.commit()

def get_pending_whatsapp_inbox(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM whatsapp_inbox_queue WHERE status = 'PENDING' ORDER BY received_at DESC"
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

def mark_whatsapp_inbox_status(message_id: str, status: str = "PROCESSED"):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE whatsapp_inbox_queue SET status = ? WHERE message_id = ?", (status, message_id))
        conn.commit()

def get_user_whatsapp_phone(user_id: str = "felipe_donato") -> str:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT whatsapp_phone FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["whatsapp_phone"]:
            return row["whatsapp_phone"]
        return "+55 11 97430-7292"

def set_user_whatsapp_phone(user_id: str = "felipe_donato", phone: str = "") -> str:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profiles (user_id, user_name, whatsapp_phone) 
            VALUES (?, 'Felipe Donato', ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                whatsapp_phone = excluded.whatsapp_phone,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, phone))
        conn.commit()
    return phone

def update_meeting_title(file_id: str, new_title: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE meetings SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE file_id = ?", (new_title, file_id))
        conn.commit()

def save_whatsapp_otp(phone: str, code: str, expires_seconds: int = 300, user_id: str = "felipe_donato") -> None:
    clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    expires_at = datetime.fromtimestamp(time.time() + expires_seconds).strftime("%Y-%m-%d %H:%M:%S")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO whatsapp_verification_codes (phone, otp_code, expires_at, attempts, verified, user_id, created_at)
            VALUES (?, ?, ?, 0, 0, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(phone) DO UPDATE SET 
                otp_code = excluded.otp_code,
                expires_at = excluded.expires_at,
                attempts = 0,
                verified = 0,
                created_at = CURRENT_TIMESTAMP
        """, (clean_phone, code, expires_at, user_id))
        conn.commit()

def verify_whatsapp_otp(phone: str, code: str, user_id: str = "felipe_donato") -> tuple:
    clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM whatsapp_verification_codes WHERE phone = ?", (clean_phone,))
        row = cursor.fetchone()
        if not row:
            return False, "Nenhum código 2FA foi solicitado para este número. Clique em 'Enviar Código'."
        
        row_dict = dict(row)
        if row_dict["attempts"] >= 5:
            return False, "Número máximo de tentativas excedido. Solicite um novo código 2FA."
            
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if str(row_dict["expires_at"]) < now_str:
            return False, "Código 2FA expirado. Por favor, solicite um novo código."
            
        if str(row_dict["otp_code"]).strip() != str(code).strip():
            cursor.execute("UPDATE whatsapp_verification_codes SET attempts = attempts + 1 WHERE phone = ?", (clean_phone,))
            conn.commit()
            return False, f"Código 2FA incorreto. Tentativa {row_dict['attempts'] + 1} de 5."
            
        # Code matches! Mark verified and update profile
        cursor.execute("UPDATE whatsapp_verification_codes SET verified = 1, attempts = 0 WHERE phone = ?", (clean_phone,))
        cursor.execute("""
            INSERT INTO user_profiles (user_id, user_name, whatsapp_phone) 
            VALUES (?, 'Felipe Donato', ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                whatsapp_phone = excluded.whatsapp_phone,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, phone))
        conn.commit()
        return True, "Telefone verificado com sucesso!"

# Bind methods to ExecutiveDatabase class as well
ExecutiveDatabase.save_whatsapp_inbox_item = lambda self, item: save_whatsapp_inbox_item(item)
ExecutiveDatabase.get_pending_whatsapp_inbox = lambda self, limit=None: get_pending_whatsapp_inbox(limit)
ExecutiveDatabase.mark_whatsapp_inbox_status = lambda self, mid, s='PROCESSED': mark_whatsapp_inbox_status(mid, s)
ExecutiveDatabase.get_user_whatsapp_phone = lambda self, uid="felipe_donato": get_user_whatsapp_phone(uid)
ExecutiveDatabase.set_user_whatsapp_phone = lambda self, uid="felipe_donato", p="": set_user_whatsapp_phone(uid, p)
ExecutiveDatabase.save_whatsapp_otp = lambda self, p, c, exp=300, uid="felipe_donato": save_whatsapp_otp(p, c, exp, uid)
ExecutiveDatabase.verify_whatsapp_otp = lambda self, p, c, uid="felipe_donato": verify_whatsapp_otp(p, c, uid)
ExecutiveDatabase.update_meeting_title = lambda self, fid, t: update_meeting_title(fid, t)

# Singleton Database Instance
db = ExecutiveDatabase()


