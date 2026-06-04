# Retrospektive — mdmaker (CLI- + GUI-Durchstich) — 2026-06

> Erster Durchlauf des Studios an einem echten Projekt: ein formatagnostischer E-Book→Markdown-Konverter, greenfield durch Direktion + Backend + Frontend/Design + Security gebaut, in zwei Durchstichen (CLI, dann GUI), mit echtem Nutzertest durch den Menschen. Auswertung beider Läufe.

---

GETRAGEN HAT:
- **Architektur-Disziplin (Backend):** Der Kern blieb über beide Durchstiche EINE Bibliothek hinter `convert_batch()`; CLI und GUI rufen denselben Pfad — kein zweiter Codepfad in die Oberfläche geleckt. Die harte Architektur-Vorgabe hat unter Last gehalten.
- **Naht Backend↔Frontend (sauber gelöst):** `progress_callback(current, total, filename) + cancel_event` in der Pipeline-Signatur; QThread-Worker; Marshalling via Qt Signal/Slot in den UI-Thread. Das nicht-blockierende Muster steht im Code, nicht nur in der Doku — das klassische „GUI friert während langem Job ein" wurde von vornherein vermieden.
- **Security-Härtung (Stufe 0/4):** Zip-Bomb-Limit, Path-Traversal/Zip-Slip, XXE/Makros, `shell=False` — beim CLI-Durchstich umgesetzt, nicht nur empfohlen. Eigenes System, defensiv → nicht blockierend, aber Härtung war Teil von „Done".
- **Ehrliche Fehlerbehandlung im Kern:** Die 3 Tesseract-Fehlschläge wurden KORREKT als FAIL geführt — kein stilles Überspringen, kein Fake-Erfolg. Das Tool war an der Stelle ehrlich, wo es zählt.
- **Output-Qualität:** Die erzeugten .md sind sauber (Urteil des Menschen).

GEREIBT HAT:
- **Design-Gate anweisungstreu, aber NICHT proaktiv (das zentrale Reibungsmuster, 2× aufgetreten):**
  - Lauf 1: Gate lieferte den explizit vorgeschriebenen DRM-Banner, verfehlte aber die mageren Fehlermeldungen („3 fehlgeschlagen" ohne Grund) und das nicht-responsive UI (Ergebnis erst ganz am Ende).
  - Lauf 2: Fehlermeldungen nachgeliefert, aber NICHT kopierbar; und keine Vorab-Warnung, dass OCR-Dateien ohne Tesseract scheitern werden — Fehlschlag erst nach ~10 Min Wartezeit.
  Muster: Das Gate erfüllt zuverlässig, was im Brief STEHT; es fängt (noch) nicht das Unaufgeforderte, das ein erfahrener Designer von selbst sähe.
- **Naht --check ↔ Lauf lückenhaft:** `--check` zeigt fehlende Tools, aber die GUI lässt einen Lauf starten, der dann an genau diesem Tool (Tesseract) scheitert. Die Verfügbarkeitsprüfung greift nicht VOR dem teuren Vorgang.
- **DRM-Hinweis zu aggressiv:** gelber Banner, vom Menschen als bevormundend empfunden — die Gate-Anforderung „sichtbar" wurde als „laut" überimplementiert.

KOLLISIONEN:
- Plattform-Kollision (Windows-COM vs. Linux/macOS) sauber als tiefes Modul gekapselt — kein Streit, korrekt aufgelöst.
- Vision-Änderung „kein GUI → GUI" über Mensch-Souveränität entschieden (D-04), nicht über die Rangleiter — korrekt verortet.
- Keine neue Normenkollision aufgetreten, die das Register nicht kannte.

QUELLEN:
- Entscheidend & korrekt genutzt: Security (Entpack-Härtung), Ousterhout (Modul-Kapselung).
- GEFEHLT in der Praxis: eine Karte/Regel für „proaktive Fehler-/Fortschritts-Ehrlichkeit" und „kopierbare Meldungen" — das Gate hatte keinen expliziten Anker dafür und verfehlte es deshalb. (→ jetzt als Design-OS-Regel ergänzt.)
- ZU PRÜFEN: Trugen die Design-Beleg-Blöcke eigene Karteikarten-Begründungen (Norman/Ehrlichkeit) — oder nur „laut Briefing"? (Mensch-Stichprobe offen.)

NÄHTE:
- Backend↔Frontend (Threading/Fortschritt): gut — sauber durchgereicht.
- Frontend↔Mensch (UX-Feedback): hier entstand der eigentliche Erkenntnisgewinn — der Nutzertest leistete, was das Gate hätte leisten sollen.
- --check↔Laufstart: schwach — Vorab-Verfügbarkeitsprüfung fehlt.

BIAS:
- **Survivorship-Bias bestätigt sich als reales Risiko:** „96%/283 Bücher" und „17 fertig / 3 FAIL" verbergen, dass die 3 FAIL (alle Tesseract) die diagnostisch wichtigsten waren. „Lief durch" ≠ „gut konvertiert".
- **Performance nicht geraten, sondern zu messen:** Verdacht OCR-Last (621s, ~31s/Datei) + evtl. nicht greifende `-j`-Parallelität im GUI-Worker — Messung steht aus, NICHT als Annahme behandeln.

GATES:
- Security-Gate: korrekt, nicht blockierend (eigenes System, defensiv), Härtung geliefert. OK.
- Design-Ethik-Gate: anweisungstreu, aber proaktiv-blind (siehe GEREIBT). KEINE Schwächung des Gates — sondern Hinweis, die Gate-Checkliste um proaktive UX-Ehrlichkeit zu erweitern. (Drift-Guard beachtet: Gate wird verschärft, nicht aufgeweicht.)

ERKENNTNIS-VORSCHLAG (getaggt; für LEARNINGS.md → Update-Protokoll):
1. [zusammenarbeit/logik] **Kopierbare Meldungen als Studioregel** — Fehler-/Status-/Logtexte ausnahmslos selektierbar + kopierbar. Häufigkeit: 1×, aber grundsätzlich. → Bereits umgesetzt: `design v1.1.0` (design-os-addendum_kopierbare-meldungen.md). REIF.
2. [logik] **Design-Gate-Checkliste um proaktive UX-Ehrlichkeit erweitern** — Fehler mit Ursache (nicht nur Zahl); inkrementelle Ergebnisanzeige; Vorab-Warnung bei absehbarem Scheitern (fehlende Abhängigkeit). Häufigkeit: 2× im selben Projekt = Muster. → REIF, ins Design-Gate (Teil von v1.1.0).
3. [zusammenarbeit] **Naht „Tool-Verfügbarkeit vor teurem Lauf prüfen"** — wenn ein Vorgang eine externe Abhängigkeit braucht, die fehlt, VORHER warnen statt hinterher scheitern. Häufigkeit: 1× — beobachten; als Frontend/Backend-Muster vormerken.
4. [bias] **Erfolgskennzahlen entsurvivorshippen** — „n fertig" immer mit „welche scheiterten + warum" berichten; Qualität ≠ Exit-Code. Häufigkeit: wiederholt sichtbar. → in Antibias-Prompts der bauenden Abteilungen prominent halten (bereits im Katalog).

OFFEN (Mensch / nächster Lauf):
- Backend-Performance-Messung: Zeit pro Datei/Pipeline; ist OCR der Treiber? Greift `-j` im GUI-Worker?
- Stichprobe: tragen die Beleg-Blöcke echte 1e/1n-Quellen + Provenienz, oder pauschales „R1"?

---

## Bilanz (ehrlich, beide Richtungen)
Der erste echte Studio-Einsatz zeigt ein konsistentes Bild: **Das Studio liefert dort echten Wert, wo Disziplin und Quellenbindung greifen** (Architektur-Kapselung, Naht-Threading, defensive Entpack-Härtung, ehrliche Kern-Fehlerbehandlung) — und es **lernt aus seinen Lücken** (kopierbare Meldungen werden Regel, proaktive Ehrlichkeit Gate-Standard). **Die Schwäche ist real und wiederholt:** die Gates sind anweisungstreu, nicht proaktiv — sie brauchen den aufmerksamen Menschen in der Schleife, um das Unaufgeforderte zu fangen. Das deckt sich exakt mit der dokumentierten Grenze in `tools/PRUEFER.md` (Form wird geprüft, Substanz braucht den Menschen) und bestätigt: Das Studio ist ein starkes Gerüst mit Mensch-in-the-Loop, kein autonomer Brillanz-Apparat. Genau diese Befunde sind nur entstanden, weil ein Mensch das Tool wirklich benutzt hat — der erste unabhängige Test des Kernsystems über mehrere Abteilungen.
