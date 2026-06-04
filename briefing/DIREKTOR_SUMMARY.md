# Direktor-Summary · mdmaker Alpha

> DIRECTOR_OS D-05 · Konsolidierung aller Briefs · 4. Juni 2026

## Beleg-Block (motor.md §5 — Prüfer-PASS)

```
Quellen:
  - Ousterhout R4 (tiefe Module, DocConverter)
  - DDIA R2 (Pipeline-Reliability/Fehlertoleranz)
  - Release It! R3 (Timeout/CircuitBreaker für externe Tools)
  - GoF R3 (Registry/Strategy-Pattern für Converter)
  - Khorikov R3 (Testbare Converter-Module)
  - Anderson R2 (System-Security, Bedrohungsmodell)
  - OWASP R1n (Injection/Path-Traversal)
  - Norman R2 (CLI-Feedback)

Rang-Auflösung:
  - Konkordanz (R0): Keine formalen Konflikte zwischen den Quellen
  - Architektur: Ousterhout (R4) + GoF (R3) kompatibel → Registry/Strategy
    sind TIEFE Module im Ousterhout-Sinn
  - Security: Anderson (R2) Systemdenken + OWASP (R1n) normative Vorgaben
    → Scheinkonflikt (Regel 0): Systemdenken beschreibt WAS, OWASP WIE

Antibias (Stufe 4, ADVERSARIAL):
  - Sykophantie: Direktion sagt "Ousterhout + GoF sind perfekt".
    ABER: Registry/Strategy addiert Abstraktions-Overhead.
    Falsifikation: Trifft das auf 11 Converter zu? Ja — ohne Registry
    wird if/elif unwartbar. Overhead gerechtfertigt.
  - "96% Erfolgsquote" aus altem Code → Survivorship-Bias:
    Was ist mit den 4%, die FAILED? Waren es Spezialformate (.chm)?
    Gescannte PDFs ohne Text-Layer? Die Metrik muss Fehler-KATEGORIEN
    erfassen, nicht nur zählen. → ADR-005 (Qualitätsmetrik).

Gates:
  - Security-Gate: NICHT blockierend (eigenes System).
    ABER: Härtung IST Teil von "Done" (Mensch-Vorgabe).
    → Bedrohungsmodell im BRIEF_SECURITY implementiert.

Prüfer-PASS: C1(Quellen)✓ C2(Rang)✓ C3(Antibias)✓ C4(Gates)✓ C5(Beleg)✓ C6(Ethik≠Rang)✓
```

## Entscheidungen (alle mit ADR)

| ADR | Thema | Entscheidung |
|---|---|---|
| 001 | Converter-Architektur | Registry + Strategy-Pattern |
| 002 | DOC-Plattform | DocConverter als tiefes Modul; WordCOM + LibreOffice-Stub |
| 003 | Archiv-Verhalten | Single-Book: 1 PDF/EPUB extrahieren → delegieren |
| 004 | CHM Linux/macOS | 7z cross-platform → eigener HTML→Text-Parser |
| 005 | OCR-Qualität | Best-effort + Confidence-Metadaten im Footer. Fehler-Kategorien loggen. |
| 006 | Parallelität | ThreadPoolExecutor (`-j`). OCR lagert an Tesseract-eigene Prozesse aus. |
| 007 | Namensschema | `Titel - Autor, Jahr.md` via Metadaten, Fallback: Dateiname |

## Abteilungs-Status

| Abteilung | Rolle | Brief | Status |
|---|---|---|---|
| **Backend** | Führt | BRIEF_BACKEND.md | ✅ Bereit zum Bau |
| **Security** | Berät (Gate) | BRIEF_SECURITY.md | ✅ Härtung spezifiziert |
| **Frontend** | Berät (CLI) | BRIEF_FRONTEND.md | ✅ UX spezifiziert |
| Design | — | nicht involviert | — |
| GameDev | — | nicht involviert | — |

## Naht-Beobachtung (für Lernschleife)

- **Backend↔Security:** `safe_extract()` API ist die Naht. Security spezifiziert, Backend implementiert. Bei Konflikt (z. B. "Ratio 100:1 blockiert legitime 95:1-Archive") → Direktion entscheidet.
- **Plattform-Kollision:** Word-COM vs. LibreOffice. Beide gültig in ihrer Plattform — kein Rang-Konflikt. Aber: `--check` muss plattform-abhängig prüfen.

## Nächster Schritt

**Mensch gibt Startsignal → Backend beginnt mit Durchstich (EPUB + PDF + ZIP).**
