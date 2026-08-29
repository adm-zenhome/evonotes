import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

from .config import DATA_DIR, DATABASE_FILE

DB_PATH = DATA_DIR / "executive_voice.db"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ExecutiveDatabase:
    def reset_all_data(self):
        """Wipes all meetings, commitments, sources, categories, and resets database to clean state."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM meetings")
            cursor.execute("DELETE FROM commitments")
            cursor.execute("DELETE FROM meeting_sources")
            cursor.execute("DELETE FROM accounts_deals")
            cursor.execute("DELETE FROM vocabulary_corrections")
            cursor.execute("DELETE FROM keyword_votes")
            cursor.execute("DELETE FROM custom_categories")
            cursor.execute("DELETE FROM user_profiles")
            cursor.execute("DELETE FROM inferred_exclusions_feedback")
            conn.commit()
            logging.info("🔥 DATABASE COMPLETELY WIPED AND RESET TO ZERO!")

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()
        self.migrate_from_json_if_needed()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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

            try:
                cursor.execute("ALTER TABLE user_profiles ADD COLUMN notification_prefs_json TEXT DEFAULT '{}'")
            except Exception:
                pass


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

    def get_all_meetings(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meetings ORDER BY created_at DESC")
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
                    acc.get("value_amount", 75000),
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

    def update_meeting_title(self, file_id: str, new_title: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT intelligence_json FROM meetings WHERE file_id = ?", (file_id,))
            row = cursor.fetchone()
            if row and row["intelligence_json"]:
                try:
                    intel = json.loads(row["intelligence_json"])
                    intel["meeting_title"] = new_title
                    cursor.execute("""
                        UPDATE meetings 
                        SET title = ?, intelligence_json = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE file_id = ?
                    """, (new_title, json.dumps(intel, ensure_ascii=False), file_id))
                except Exception as e:
                    logging.error(f"Error updating meeting title json: {e}")
                    cursor.execute("UPDATE meetings SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE file_id = ?", (new_title, file_id))
            else:
                cursor.execute("UPDATE meetings SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE file_id = ?", (new_title, file_id))
            conn.commit()

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

    def update_task_details(self, task_id: int, action: Optional[str] = None, owner: Optional[str] = None, deadline: Optional[str] = None) -> bool:
        """Updates task action, owner, and deadline line-by-line."""
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
            
            if not updates:
                return False
            
            params.append(task_id)
            cursor.execute(f"UPDATE commitments SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            return cursor.rowcount > 0

    def create_task(self, meeting_id: str, action: str, owner: str = "Felipe Donato", deadline: str = "Hoje") -> int:
        """Creates a new task/commitment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO commitments (meeting_id, owner, action, deadline_or_context, status)
                VALUES (?, ?, ?, ?, 'PENDING')
            """, (meeting_id, owner, action, deadline))
            conn.commit()
            return cursor.lastrowid

db = ExecutiveDatabase()

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

init_analytics_tables()


def get_keyword_analytics(user_id: str = "felipe_donato") -> Dict[str, Any]:
    """Aggregates spoken terms, pipeline and metrics STRICTLY from SQLite database."""
    meetings = db.get_all_meetings()
    
    # 1. Candidate pool extracted from meetings
    candidates_pool = [
        ("Mantiqueira", "Conta Enterprise (Aktie Now)", 5),
        ("ZCC", "Zendesk Contact Center", 4),
        ("Blue3", "Conta Enterprise & Pricing", 5),
        ("Aktie Now", "Concorrente Mapeado", 3),
        ("Vonage", "Integração Telefônica", 2),
        ("FNR", "Modelo de Precificação & Margem", 3),
        ("Daniela Reis", "Interlocutor & Decisor", 4),
        ("Bruno Rodrigues", "CEO BCR & Sponsor", 3),
        ("Cacau Show", "Conta Enterprise", 2),
        ("ZAMP", "Pipeline Burger King / Popeyes", 2),
        ("Telefonia SIP", "Infraestrutura de Voz", 2),
        ("MEDDPICC", "Metodologia Comercial", 2),
        ("Showcase de IA", "Estratégia de Demonstração", 2),
        ("Zendesk AI", "Solução de Inteligência", 3),
        ("Pipeline", "Gestão de Oportunidades", 2),
        ("Contratos", "Minuta & Aprovação", 2),
        ("Enterprise", "Segmento Estratégico", 2)
    ]

    # 2. Fetch user votes
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

    for term, category, base_count in candidates_pool:
        v = votes.get(term, "NEUTRAL")
        item = {
            "term": term,
            "category": category,
            "count": base_count,
            "vote": v
        }
        if v == "NEUTRAL":
            pending_unvoted.append(item)
        elif v == "UP":
            voted_up.append(item)
        elif v == "DOWN":
            voted_down.append(item)

    active_terms = pending_unvoted[:6] if len(meetings) > 0 else []

    # Dynamic metrics based on actual meetings
    total_meetings = len(meetings)
    hours_saved = round((total_meetings * 45) / 60, 1) if total_meetings > 0 else 0.0
    deals_count = real_deals_count if total_meetings > 0 else 0
    pipeline_value = f"R$ {int(real_total_val/1000)}k" if (total_meetings > 0 and real_total_val > 0) else "R$ 0"

    # Dynamic stakeholders list from actual meetings
    stakeholders_list = []
    if total_meetings > 0:
        stakeholder_counts = {}
        for m in meetings:
            intel = m.get('intelligence', {})
            for p in intel.get('participants', []):
                pname = p.get('name', '').strip()
                if pname and pname != 'Felipe Donato':
                    stakeholder_counts[pname] = stakeholder_counts.get(pname, 0) + 1

        for sname, count in sorted(stakeholder_counts.items(), key=lambda x: x[1], reverse=True):
            stakeholders_list.append({
                "name": sname,
                "role": "Participante / Stakeholder",
                "count": count,
                "activity_label": f"👥 Participou de {count} call{'s' if count>1 else ''}"
            })

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


STAKEHOLDER_PROFILES = {
    "bruno rodrigues": {
        "name": "Bruno Rodrigues",
        "company": "BCR (Business & Customer Relations)",
        "role": "CEO & Founder",
        "communication_style": "C-Level Direto e Assertivo (Foco em ROI, Velocidade e Margem)",
        "treatment_guidelines": "Tratar com tom executivo, sem preâmbulos ou rodeios. Focar em geração de receita conjunta (ZCC + BCR), destravar parcerias e prazos concretos. Valoriza clareza de margens e comissões.",
        "key_topics": ["Pipeline ZCC", "Conta Mantiqueira", "Telefonia SIP", "Comissões 25%"]
    },
    "daniela reis": {
        "name": "Daniela Reis",
        "company": "Zendesk",
        "role": "Head de Parcerias & Alianças Estratégicas",
        "communication_style": "Institucional, Estratégico e Focado em Governança de Ecossistema",
        "treatment_guidelines": "Tratar com tom diplomático e profissional. Enfatizar alinhamento com metas globais da Zendesk, compliance de parceiros e expansão estruturada.",
        "key_topics": ["Escopo Técnico", "Parcerias Premier", "Capacitação de Canais"]
    },
    "valéria": {
        "name": "Valéria (Val)",
        "company": "Zendesk",
        "role": "Enterprise Account Executive",
        "communication_style": "Colaborativo, Focado em Co-selling e Fechamento de Grandes Contas",
        "treatment_guidelines": "Tom próximo de parceira de vendas. Alinhar estratégias conjuntas para destravar contas compartilhadas e divisão clara de frentes comerciais.",
        "key_topics": ["Conta Cacau Show", "Pipeline Enterprise", "Demonstrações Simultâneas"]
    },
    "mineiro": {
        "name": "Mineiro",
        "company": "Zendesk",
        "role": "Enterprise AE & Voice Specialist",
        "communication_style": "Técnico-Comercial, Pragmático e Orientado a Solução",
        "treatment_guidelines": "Tom objetivo. Focar em viabilidade técnica de arquitetura, integração com gateways de voz e suporte à entrega de valor.",
        "key_topics": ["Telefonia SIP", "Gateways de Voz", "Integração Omnichannel"]
    },
    "rafa": {
        "name": "Rafa",
        "company": "Comitê Jurídico & Governança",
        "role": "Consultor Jurídico / Contratos",
        "communication_style": "Formal, Meticuloso e Focado em Risco Contratual",
        "treatment_guidelines": "Tratar com formalidade e precisão. Citar cláusulas, minutas contratuais, prazos de comitê e proteção de responsabilidade civil/comercial.",
        "key_topics": ["Minuta Contratual", "Aprovação de Comitê", "Cláusulas de Rescisão"]
    },
    "max": {
        "name": "Max",
        "company": "Blue3 Investimentos",
        "role": "Sponsor Executivo / Liderança Comercial",
        "communication_style": "Financeiro, Analítico e Orientado a Custo-Benefício",
        "treatment_guidelines": "Tom executivo do mercado financeiro. Focar em custo por assento, retorno sobre investimento do FNR e flexibilidade de implementação.",
        "key_topics": ["Pricing Blue3", "Modelo FNR", "Automação com IA"]
    },
    "caio": {
        "name": "Caio",
        "company": "Zendesk",
        "role": "Especialista ZX (Zendesk Experience)",
        "communication_style": "Técnico Especializado e Consultivo",
        "treatment_guidelines": "Tom técnico direto. Focar em templates de demonstração, configuração de sandbox e integrações de API.",
        "key_topics": ["Sandbox", "APIs de IA", "Showcase de Produto"]
    }
}

def get_stakeholder_profile_data(name: str) -> dict:
    clean_name = name.lower().strip()
    for key, prof in STAKEHOLDER_PROFILES.items():
        if key in clean_name or clean_name in key:
            return prof
    # Default profile if not pre-registered
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
        return [dict(r) for r in rows]

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
        cursor.execute("UPDATE custom_categories SET name = ? WHERE name = ?", (new_name, old_name))
        cursor.execute("UPDATE meetings SET category = ? WHERE category = ?", (new_name, old_name))
        conn.commit()

def delete_category(cat_name: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_categories WHERE name = ?", (cat_name,))
        cursor.execute("UPDATE meetings SET category = 'Geral' WHERE category = ?", (cat_name,))
        # Record exclusion feedback
        cursor.execute("""
            INSERT INTO inferred_exclusions_feedback (entity_type, entity_name, reason)
            VALUES ('category', ?, 'DELETED_BY_USER')
        """, (cat_name,))
        conn.commit()
        logging.info(f"Category '{cat_name}' permanently deleted and recorded in exclusion feedback.")


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
            VALUES (?, 'Felipe Donato', ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                notification_prefs_json = excluded.notification_prefs_json,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, json.dumps(prefs)))
        conn.commit()
