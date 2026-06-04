# Vision-Intake-Brief — mdmaker

> Director-Brief nach DIRECTOR_OS D-01. Eingang: 4. Juni 2026.

## 0. Vision (Mensch → Direktion, gespiegelt)

> Ein einziges CLI-Tool, das jedes E-Book-Format frisst und sauberes Markdown ausgibt.
> "pandoc für E-Books." Ordner rein, .md raus.
>
> `mdmaker <eingabe>/ -o <ausgabe>/ -j <n> [--recursive --dry-run --force --check]`
>
> Formate: EPUB, PDF(Text), PDF(Scan/OCR), MOBI, PRC, DOC, DOCX, DJVU, CHM, XZ, ZIP.
> Smart Routing: Format erkennen → in die Pipeline leiten, die für DIESES Format
> wirklich funktioniert. PDF-Heuristik: erste ~10 Seiten sampeln, <~30 Zeichen/Seite
> → OCR-Pipeline, sonst Text-Pipeline.

## 1. Zerlegung (Direktion D-01.i)

| Nr | Frage | Antwort (Mensch) |
|---|---|---|
| 1 | Pflicht-Formate vs. nice-to-have? | Alle 11 sind Pflicht. Keines optional. |
| 2 | Primäre Zielgruppe? | Entwickler/Wissensarbeiter für KI/RAG, Volltextsuche, Wissensmanagement |
| 3 | CLI oder GUI? | CLI only. Kein GUI. |
| 4 | Ausgabeformate außer MD? | Nur Markdown. |
| 5 | Nicht-funktional? | Python ≥3.10, 3.14 aktiv; Windows-first; lokal; externer Tool-Abhängigkeits-Check |

## 2. Routing-Entscheidungen (DIRECTOR_OS §6)

| Arbeitsstück | Führt | Berät | Begründung |
|---|---|---|---|
| Konvertierungs-Pipeline | **Backend** | Security | Daten/API/Dienst-Signal |
| Format-Detektion | **Backend** | — | Parsing-Logik |
| Security-Härtung | **Security** | Backend | "Ist das sicher?" (eigenes System) |
| CLI-Ergonomie | **Frontend** | Design | Oberfläche/Komponente |
| OCR-Qualität | **Backend** | GameDev (Rendering-Pipeline-Erfahrung) | Performance/Qualität |
| DOC-COM-Modul | **Backend** | Security | Plattform-nativ |

## 3. Pflicht-Prüfaufträge (vom Menschen, nicht delegierbar)

1. **SECURITY-GATE:** Bedrohungsmodell + Härtung: Zip-Bombs, Path-Traversal, DOCX-Makros/XXE, Ressourcen-Limits.
2. **BACKEND/ARCHITEKTUR (Ousterhout):** Word-COM als TIEFES Modul hinter DocConverter-Schnittstelle.
3. **ANTIBIAS/EHRLICHKEIT:** Qualitätsmetrik jenseits Exit-Code-0 definieren; Survivorship-Bias benennen.

## 4. Offene Fragen der Direktion (vor Baubeginn)

> Diese werden NICHT geraten. Der Mensch entscheidet.

1. **Archiv-Entpackung (ZIP/XZ):** Soll mdmaker NUR entpacken, wenn das Archiv EIN Buch enthält, oder auch Multi-File-Archive (z. B. `images/`-Ordner) unterstützen? Falls Multi-File: wie wird das "Haupt-Buch" identifiziert?
2. **CHM-Konvertierung:** hh.exe ist Windows-only. Soll auf Linux/macOS `archmage` oder `libchm` verwendet werden, oder reicht "7z zum Entpacken, HTML→Text mit eigenem Parser"?
3. **Qualitäts-Schwelle OCR:** Welche akzeptable Mindest-Zeichengenauigkeit? Oder: "best effort, Ausgabe immer — Metadaten warnen bei <X% Confidence"?
4. **Namensschema für .md-Ausgabe:** `Titel - Autor, Jahr.md` wie im Studio, oder 1:1 Eingabedateiname? Metadaten-basiert mit Fallback?
5. **Parallelität:** `-j` für `ThreadPoolExecutor` (Python, I/O-gebunden) oder `ProcessPoolExecutor` (OCR, CPU-gebunden)? Oder hybrid?

---

*Direktion D-01 abgeschlossen. Warte auf Antworten des Menschen vor Briefing-Versand.*
