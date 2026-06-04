# ADR-002 · Word-COM als tiefes Modul (Ousterhout-Prüfauftrag)

**Status:** Beschlossen
**Datum:** 2026-06-04
**Führend:** Backend
**Prüfauftrag:** BACKEND/ARCHITEKTUR (Ousterhout)

## Kontext

.md-Converter müssen das legacy `.doc`-Format unterstützen. Das binary OLE-Format kann nur von Microsoft Word zuverlässig gelesen werden. Auf Linux/macOS ist Word nicht verfügbar. Der Mensch fordert "Windows-first; Linux/macOS mitgedacht".

## Entscheidung

**Word-COM als TIEFES Modul hinter DocConverter-Schnittstelle.**

```python
class DocConverter(Protocol):
    """Tiefes Modul: einfache Schnittstelle, komplexes Innenleben."""
    def convert(path: Path, output_dir: Path) -> Path: ...

class WordCOMDocConverter(DocConverter):
    """Windows: Word COM Automation. Komplexität NUR hier."""

class LibreOfficeDocConverter(DocConverter):
    """Linux/macOS: LibreOffice --headless. Stub für v1."""
```

Die Schnittstelle `DocConverter` ist das EINZIGE, was der Rest des Systems sieht. Word COM (Windows) und LibreOffice (Linux) sind austauschbare Implementierungen. Plattform-Erkennung in der Factory, NICHT im Converter.

## Quellenbindung

- **Ousterhout (R4):** "Tiefe Module haben einfache Schnittstellen und komplexe Interna." Die `convert()`-Schnittstelle ist 1 Methode. Word COM, DCOM-Permissions, Makro-Security sind NUR im Inneren. [Karte: `philosophy-of-software-design`]
- **Feathers (R3):** Seam-Pattern: `DocConverter` ist der Seam, an dem getestet wird. [Karte: `working-effectively-with-legacy-code`]

## Plattform-Kollision (Naht Backend↔Plattform)

- **Windows:** Word COM ist verfügbar → `WordCOMDocConverter` aktiv
- **Linux/macOS:** Kein Word → `LibreOfficeDocConverter` (Stub in v1, voll in v2). In v1: klare Fehlermeldung "Installiere LibreOffice oder konvertiere .doc zu .docx".
- **Kein Rang-Konflikt:** Beide Implementierungen sind gültig in ihrer Plattform. Scheinkonflikt (Regel 0).

## Konsequenzen

- Backend-Code kennt NUR `DocConverter`, nie Word COM direkt
- `--check` meldet je nach Plattform das passende fehlende Tool
- LibreOffice-Stub in v1 verhindert "geht nicht auf Linux" — es geht, nur halt später
