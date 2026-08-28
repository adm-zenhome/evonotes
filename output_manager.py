import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from .config import DESKTOP_ZENDESK_DIR, DATABASE_FILE, DATA_DIR
from .notifier import InductionNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class OutputManager:
    """Manages document rendering, markdown exports in ~/Desktop/Zendesk, and database persistence."""

    def __init__(self):
        self.output_dir = DESKTOP_ZENDESK_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_file = DATABASE_FILE
        self.notifier = InductionNotifier()

    def _load_db(self) -> List[Dict[str, Any]]:
        if self.db_file.exists():
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading meetings DB: {e}")
        return []

    def _save_db(self, data: List[Dict[str, Any]]):
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def render_markdown(self, intelligence: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Renders structured executive intelligence into a polished Markdown document."""
        title = intelligence.get("meeting_title", "Reunião Executiva")
        date_str = metadata.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
        duration_min = round(metadata.get("duration", 0) / 60, 1)

        participants_md = "\n".join([
            f"* **{p.get('name', 'N/A')}** ({p.get('role', 'N/A')}): {p.get('key_stance', '')}"
            for p in intelligence.get("participants", [])
        ])

        commitments_md = "\n".join([
            f"- [{'x' if c.get('done') else ' '}] **[{c.get('owner', 'A Definir')}]** {c.get('action', '')} *(Contexto: {c.get('deadline_or_context', 'N/A')})* — `Prioridade: {c.get('urgency', 'MEDIA')}`"
            for c in intelligence.get("commitments_and_promises", [])
        ])

        accounts_table_rows = "\n".join([
            f"| **{acc.get('account_name', '')}** | {acc.get('current_situation', '')} | {acc.get('opportunity_or_risk', '')} | {acc.get('next_step', '')} |"
            for acc in intelligence.get("accounts_discussed", [])
        ])

        theses_md = "\n".join([f"* {t}" for t in intelligence.get("strategic_theses", [])])

        emails_md = ""
        for i, email in enumerate(intelligence.get("follow_up_emails", []), 1):
            emails_md += f"""
#### ✉️ Rascunho {i}: {email.get('subject', 'Follow-up')}
**Para:** `{email.get('to', '')}`  
**Assunto:** `{email.get('subject', '')}`  

```text
{email.get('body', '')}
```
"""

        md_content = f"""# 📑 {title}

> **📅 Data:** {date_str}  
> **⏱️ Duração:** {duration_min} min  
> **🏷️ Categoria:** {intelligence.get('category', 'Comercial')}  
> **✨ Motor:** Executive Voice OS v1.0 (Jarvis)

---

## 🎯 1. Resumo Executivo
{intelligence.get('executive_summary', 'Sem resumo disponível.')}

---

## 👥 2. Participantes & Posicionamento
{participants_md if participants_md else "*Participantes não identificados.*"}

---

## 📋 3. Matriz de Compromissos & Promessas Verbais
{commitments_md if commitments_md else "*Nenhum compromisso pendente identificado.*"}

---

## 🏢 4. Mapeamento de Contas & Pipeline
| Conta | Situação Atual | Oportunidade / Risco | Próximo Passo |
|---|---|---|---|
{accounts_table_rows if accounts_table_rows else "| Nenhuma | - | - | - |"}

---

## 💡 5. Teses Estratégicas & Insights de Vendas
{theses_md if theses_md else "*Nenhuma tese adicional registrada.*"}

---

## ✉️ 6. Rascunhos de E-mail de Follow-up (1-Click)
{emails_md if emails_md else "*Nenhum rascunho de e-mail gerado.*"}

---
*Relatório gerado automaticamente pelo Executive Voice OS.*
"""
        return md_content

    def save_meeting(self, file_id: str, intelligence: Dict[str, Any], metadata: Dict[str, Any], raw_transcript: str = "") -> Path:
        """Saves markdown report to ~/Desktop/Zendesk, updates database and triggers induction alerts."""
        safe_title = intelligence.get("meeting_title", "Reuniao").replace(" ", "_").replace("/", "-")
        date_prefix = metadata.get("created_at", datetime.now().strftime("%Y-%m-%d"))[:10]
        filename = f"CALL_{date_prefix}_{safe_title}.md"
        target_path = self.output_dir / filename

        md_content = self.render_markdown(intelligence, metadata)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Dual save to Obsidian Plaud knowledge vault
        obsidian_dir = Path("/Users/felipe/Jarvis/07 - CONHECIMENTO/03 - Notas e Arquivos/Plaud")
        obsidian_dir.mkdir(parents=True, exist_ok=True)
        obsidian_target = obsidian_dir / f"{date_prefix}_{safe_title}.md"
        with open(obsidian_target, "w", encoding="utf-8") as f:
            f.write(md_content)

        logging.info(f"Report saved to {target_path} and {obsidian_target}")

        # Update Database
        db = self._load_db()
        db = [item for item in db if item.get("file_id") != file_id]

        record = {
            "file_id": file_id,
            "title": intelligence.get("meeting_title", "Reunião"),
            "category": intelligence.get("category", "Geral"),
            "created_at": metadata.get("created_at", datetime.now().isoformat()),
            "duration": metadata.get("duration", 0),
            "doc_path": str(target_path),
            "intelligence": intelligence,
            "raw_transcript_preview": raw_transcript[:1000] if raw_transcript else "",
            "updated_at": datetime.now().isoformat()
        }
        db.insert(0, record)
        self._save_db(db)

        # Trigger Proactive Induction (Desktop Banner + Telegram)
        try:
            self.notifier.trigger_post_meeting_induction(intelligence, str(target_path))
        except Exception as e:
            logging.error(f"Error triggering induction notifier: {e}")

        return target_path

if __name__ == "__main__":
    om = OutputManager()
    print("OutputManager with InductionNotifier ready.")
