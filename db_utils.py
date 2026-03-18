#!/usr/bin/env python3
"""
Utility script per gestire il database del sistema
"""

import sys
import sqlite3
from pathlib import Path

DB_PATH = Path("memory/project_memory.db")


def reset_database():
    """Resetta completamente il database"""
    if DB_PATH.exists():
        print(f"🗑️  Rimuovendo database esistente: {DB_PATH}")
        DB_PATH.unlink()
        print("✓ Database rimosso")
    else:
        print("ℹ️  Database non esiste, niente da rimuovere")


def view_stats():
    """Mostra statistiche del database"""
    if not DB_PATH.exists():
        print("❌ Database non esiste")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n📊 Statistiche Database\n")

    # Project memory
    cursor.execute("SELECT COUNT(*) FROM project_memory")
    count = cursor.fetchone()[0]
    print(f"  Actions logged: {count}")

    # Tasks
    cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    print(f"\n  Tasks:")
    for status, count in cursor.fetchall():
        print(f"    {status}: {count}")

    # Bugs
    cursor.execute("SELECT status, COUNT(*) FROM bugs GROUP BY status")
    print(f"\n  Bugs:")
    for status, count in cursor.fetchall():
        print(f"    {status}: {count}")

    # Decisions
    cursor.execute("SELECT COUNT(*) FROM architecture_decisions")
    count = cursor.fetchone()[0]
    print(f"\n  Architecture decisions: {count}")

    conn.close()


def clean_old_data(days=7):
    """Pulisce dati vecchi"""
    if not DB_PATH.exists():
        print("❌ Database non esiste")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n🧹 Pulizia dati più vecchi di {days} giorni\n")

    # Clean project_memory
    cursor.execute(
        "DELETE FROM project_memory WHERE timestamp < date('now', '-' || ? || ' days')",
        (days,),
    )
    deleted = cursor.rowcount
    print(f"  ✓ Rimosse {deleted} azioni vecchie")

    # Clean completed/failed tasks
    cursor.execute(
        "DELETE FROM tasks WHERE status IN ('completed', 'failed') AND completed_at < date('now', '-' || ? || ' days')",
        (days,),
    )
    deleted = cursor.rowcount
    print(f"  ✓ Rimossi {deleted} task completati/falliti")

    # Clean resolved bugs
    cursor.execute(
        "DELETE FROM bugs WHERE status = 'resolved' AND resolved_at < date('now', '-' || ? || ' days')",
        (days,),
    )
    deleted = cursor.rowcount
    print(f"  ✓ Rimossi {deleted} bug risolti")

    conn.commit()
    conn.close()

    print("\n✓ Pulizia completata")


def view_recent_actions(limit=20):
    """Mostra azioni recenti"""
    if not DB_PATH.exists():
        print("❌ Database non esiste")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n📝 Ultime {limit} azioni\n")

    cursor.execute(
        """
        SELECT timestamp, agent, action, description 
        FROM project_memory 
        ORDER BY timestamp DESC 
        LIMIT ?
    """,
        (limit,),
    )

    for timestamp, agent, action, description in cursor.fetchall():
        print(f"  [{timestamp}] {agent}: {action}")
        print(f"    {description[:80]}{'...' if len(description) > 80 else ''}")
        print()

    conn.close()


def main():
    """Main menu"""
    if len(sys.argv) < 2:
        print("""
🔧 Hypnonyx Database Utility

Usage: python db_utils.py <command>

Commands:
  reset          - Resetta completamente il database
  stats          - Mostra statistiche
  clean [days]   - Pulisce dati vecchi (default: 7 giorni)
  actions [N]    - Mostra ultime N azioni (default: 20)

Examples:
  python db_utils.py reset
  python db_utils.py stats
  python db_utils.py clean 30
  python db_utils.py actions 50
""")
        return

    command = sys.argv[1].lower()

    if command == "reset":
        confirm = input(
            "⚠️  Sei sicuro? Questo cancellerà tutto il database. (yes/no): "
        )
        if confirm.lower() == "yes":
            reset_database()
        else:
            print("Operazione annullata")

    elif command == "stats":
        view_stats()

    elif command == "clean":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        clean_old_data(days)

    elif command == "actions":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        view_recent_actions(limit)

    else:
        print(f"❌ Comando sconosciuto: {command}")
        print("Usa 'python db_utils.py' per vedere l'help")


if __name__ == "__main__":
    main()
