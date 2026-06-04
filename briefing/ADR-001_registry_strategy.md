# ADR-001 · Converter-Registry + Strategy-Pattern

**Status:** Beschlossen
**Datum:** 2026-06-04
**Führend:** Backend
**Rang-Auflösung:** —

## Kontext

mdmaker muss 11 Formate unterstützen. Jedes Format braucht eine eigene Konvertierungs-Pipeline. Neue Formate müssen ohne Änderung am Kern-Code hinzufügbar sein.

## Entscheidung

**Registry + Strategy-Pattern.** Jeder Converter ist eine Klasse, die ein `Converter`-Protocol implementiert (`can_handle()`, `check_deps()`, `convert()`). Eine zentrale Registry sammelt alle Converter via Decorator `@register`. Die Pipeline fragt die Registry: "Wer kann Format X?" → delegiert.

## Quellenbindung

- **GoF Design Patterns (R3):** Strategy-Pattern für austauschbare Algorithmen; Registry als erweiterter Factory. [Karte: `design-patterns-gof`]
- **Ousterhout (R4):** Jeder Converter ist ein TIEFES Modul — einfache Schnittstelle (`convert(path) -> md_path`), komplexes Innenleben (Calibre/Tesseract/DjVuLibre). [Karte: `philosophy-of-software-design`]

## Alternativen

- **If-elif-Kette:** Jedes Format hart verdrahtet. Verworfen: nicht erweiterbar.
- **Plugin-System (steckbar, importlib):** Overengineered für v1. Registry als einfaches Modul-Import-Muster reicht.

## Konsequenzen

- Neues Format = neues ~50-Zeilen-Modul + `@register`-Decorator
- Registry ist ein einfaches Python-List-Objekt, keine externe Konfiguration
- Testbarkeit: jeder Converter kann isoliert mit Mock-Dateien getestet werden
