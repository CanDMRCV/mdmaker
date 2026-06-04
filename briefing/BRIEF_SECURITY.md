# Brief — Security (beratend, Gate-Träger)

> Inbound D-03. Führend bei Sicherheitsentscheidungen. **Gate: Autorisierung & Schaden.**

## 1. Auftrag

Baue das **Bedrohungsmodell** für mdmaker und implementiere die Härtung für alle Entpackungs-/Parsing-Pfade. Das Tool verarbeitet nicht vertrauenswürdige Dateien — Pflicht vor Durchstich.

## 2. Bedrohungsmodell (STRIDE-Lite)

| Bedrohung | Vektor | Schadenspotenzial | Maßnahme |
|---|---|---|---|
| **Zip-Bomb** | Entpackte ZIP/XZ mit 10 KB → 100 GB | DoS, Platte voll | Dekompressions-Ratio-Limit: max 100:1; max 500 MB entpackt |
| **Path-Traversal** | ZIP-Eintrag `../../../etc/passwd` | Überschreibt Systemdateien | Jeder Pfad im Archiv wird normalisiert; `..`-Einträge → Abbruch |
| **XXE (DOCX)** | XML External Entity in docx.xml | Liest lokale Dateien | `defusedxml` oder XML-Parser mit `resolve_entities=False` |
| **DOC-Makros** | .doc mit VBA-Makro | Code-Ausführung | Word COM: `AutomationSecurity=ForceDisable`, kein Makro-Run |
| **OOM EPUB** | EPUB mit 1 GB HTML-Eintrag | RAM erschöpft | Max 100 MB pro Einzeldatei im EPUB; Timeout 300s je Converter |
| **Tesseract-CMD-Injection** | Dateiname `img;rm -rf /.png` | Shell-Injection | `subprocess.run([...], shell=False)`, Dateinamen nie in Shell |
| **Calibre-Pfad** | Sonderzeichen im Pfad | `ebook-convert` crasht oder injiziert | Pfade normalisieren; keine Shell-Expansion |

## 3. Quellenbindung

- **Anderson Security Engineering (R2):** System-Sicherheit ist eine Emergenz-Eigenschaft; "security is a system property, not a feature." [Karte: `security-engineering`]
- **OWASP Top 10 (R1n):** A01:2021 Broken Access Control → Path-Traversal; A03:2021 Injection → Shell/CMD. [OWASP Top 10]
- **Nygard Release It! (R3):** Bulkhead/Timeout für externe Prozesse (Calibre, Tesseract). [Karte: `release-it`]

## 4. Härtungs-API (Backend muss implementieren)

```python
# security.py — von Security spezifiziert, von Backend implementiert
def safe_extract(archive_path: Path, dest: Path, max_ratio: int = 100) -> Path:
    """Entpackt ZIP/XZ sicher. Raises SecurityError bei Bombe/Traversal."""

def safe_parse_xml(xml_path: Path) -> ElementTree:
    """Parst DOCX/EPUB-XML ohne XXE."""

def limit_resources(timeout_s: int = 300, max_ram_mb: int = 500):
    """Context-Manager: Timeout + RAM-Limit für Converter."""
```

## 5. Prüf-Kriterien (Security)

- [ ] `safe_extract` fängt Zip-Bomb ab (10-KB→10-GB-Archiv wird abgelehnt)
- [ ] `safe_extract` fängt `../` Path-Traversal ab
- [ ] DOCX-Parser nutzt XXE-sicheren XML-Parser
- [ ] DOC-Converter öffnet Word ohne Makros
- [ ] Alle `subprocess.run` nutzen `shell=False`
- [ ] Kein Dateiname landet unescaped in Shell/CMD

---
*Brief Security v1.0 · erstellt von Direktion · 4. Juni 2026*
