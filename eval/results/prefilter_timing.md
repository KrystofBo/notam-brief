# Pre-filter timing

Snapshot `2026-09-22`: 945 NOTAMs (NL + DE). 300 runs per route. CPython 3.9.13 on Windows AMD64 (Intel64 Family 6 Model 158 Stepping 10, GenuineIntel).

Parsing both bulletin HTML files, done once each time a bulletin file changes: median 50.8 ms, p95 63.4 ms. Loading the parsed bulletins from memory on each request: median 0.84 ms, p95 2.65 ms.

| Route | NOTAMs scanned | Kept | Median | p95 | Per NOTAM |
|---|---|---|---|---|---|
| 1 EHLE Lelystad - EHHV Hilversum | 945 | 25 | 4.51 ms | 9.68 ms | 4.8 µs |
| 2 EHTE Teuge - EHHO Hoogeveen | 945 | 17 | 5.17 ms | 11.68 ms | 5.5 µs |
| 3 EHRD Rotterdam - EHTX Texel | 945 | 59 | 11.03 ms | 19.17 ms | 11.7 µs |
| 4 EHTW Twente - EDDG Muenster-Osnabrueck | 945 | 24 | 4.93 ms | 10.74 ms | 5.2 µs |
| 5 EHGG Groningen - EDWE Emden | 945 | 23 | 6.48 ms | 11.32 ms | 6.9 µs |
