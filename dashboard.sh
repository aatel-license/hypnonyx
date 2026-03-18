#!/bin/bash
# Shortcut per avviare la dashboard di Hypnonyx

# Naviga nella directory dello script (se lanciato da fuori)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Verifica se il venv esiste, altrimenti usa il python di sistema
if [ -d "venv" ]; then
    echo "Usando virtual environment..."
    ./venv/bin/python3 start_dashboard.py
else
    python3 start_dashboard.py
fi
