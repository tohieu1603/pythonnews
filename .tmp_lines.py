from pathlib import Path
lines = Path('apps/seapay/services/symbol_purchase_service.py').read_text(encoding='utf-8').splitlines()
for idx in range(1,60):
    print(f"{idx+1}: {lines[idx]}")
