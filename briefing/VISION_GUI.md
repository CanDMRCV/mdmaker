# Vision-Erweiterung — GUI

> Director-Brief D-01.ii · 4. Juni 2026

## 0. Änderung (Mensch → Direktion)

Das Nicht-Ziel "kein GUI" wird aufgehoben. mdmaker bekommt eine Desktop-GUI. Der Kern bleibt unverändert.

## 1. Architektur-Entscheidung (Direktion)

**GUI = dünne Schicht über dem bestehenden Kern.** Der Kern liegt bereits als Bibliothek vor:
- `pipeline.convert_file()` / `pipeline.convert_batch()` — Konvertierungslogik
- `converters.REGISTRY` / `find_converter()` — Format-Routing
- `detector.detect_format()` / `classify_pdf()` — Erkennung
- `security.*` — Härtung

Die GUI ruft NUR diese Schnittstellen — keine eigene Konvertierungslogik. CLI und GUI = zwei Oberflächen, EIN Kern.

## 2. Routing

| Arbeitsstück | Führt | Berät |
|---|---|---|
| GUI-Fenster, Layout, Widgets | **Frontend** | Design |
| Worker-Thread, Fortschritts-Events | **Backend** | Frontend |
| Design-Ethik-Gate (DRM, Ehrlichkeit, A11y) | **Design** | Frontend |
| Kern-Schnittstelle prüfen/glätten | **Backend** | — |

## 3. Technikwahl: PySide6/Qt (Direktion empfiehlt)

**Beleg-Block:**
- Quellen: Qt ist die Referenz für desktop-native, veröffentlichbare GUI (R3, etablierte Methodik)
- Plattform: Windows/macOS/Linux ohne Änderung
- Threading: QThread + Signal/Slot für langlaufende Konvertierung → UI blockiert nie
- Angriffsfläche: Keine lokale Netzwerk-Öffnung (kein localhost-Webserver)
- Gegenposition (Web-UI): electron/tauri fügt Web-Stack-Abhängigkeiten ein, öffnet Port,
  bringt keinen Mehrwert für "lokal, keine Cloud". Verworfen.

## 4. Design-Ethik-Gate (Pflicht)

- [ ] DRM-Hinweis SICHTBAR im Hauptfenster (nicht nur in Doku)
- [ ] Fehlerliste nach Lauf: jede fehlgeschlagene Datei + Grund sichtbar
- [ ] Fortschrittsbalken mit ECHTEM Fortschritt (Datei n/N), keine Fake-Prozente
- [ ] Tastatur-Navigation (Tab-Reihenfolge) + ausreichender Kontrast

## 5. Naht Backend↔Frontend (Lernschleife)

Der Kern (`pipeline.py`) muss um Fortschritts-Callbacks erweitert werden:
- `convert_batch()` bekommt einen optionalen `progress_callback(current, total, filename)`
- Der Callback wird von der GUI via Signal/Slot in den UI-Thread gemarshallt
- Abbruch via `cancel_event` (threading.Event) — GUI kann Stop-Knopf setzen

## 6. GUI-Durchstich (Definition of Done)

1. Ordner wählen (QFileDialog) → Dateien werden gescannt und angezeigt
2. `--check`-Ergebnis im Hauptfenster sichtbar (fehlende Tools)
3. Start-Knopf → Worker-Thread → Live-Fortschritt (Datei n/N + Name)
4. Nach Abschluss: klare OK/SKIP/FAIL-Liste
5. .md-Dateien im gewählten Ausgabeordner
6. Kern-Code UNVERÄNDERT — GUI ruft dieselbe convert()-Bibliothek
