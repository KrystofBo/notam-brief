# Benchmark results

Snapshot `2026-09-22`, labels `eval/labels_flat.csv`. Recall and precision are pooled over routes; the other columns are means per briefing. Latency is the model stage only.

| Model | Pre-filter | Reasoning | Recall | Precision | Items to read | NOTAMs sent | Tokens in | Tokens out | Cost / briefing | Latency |
|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-ai/DeepSeek-V4-Flash-0731 | off | none | 75% | 47% | 7.6 | 457 | 68,211 | 25,437 | $0.0167 | 36.4 s |

## Per route

| Model | Pre-filter | Reasoning | Route | Recall | Precision | Flagged / labelled | Missed | False positives | Tokens in/out | Cost | Latency |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DeepSeek-V4-Flash-0731 | off | none | 1 | 100% | 54% | 13 / 7 | - | A1473/26 A1529/26 A1595/26 A2070/26 A2195/26 B1025/26 | 20,186 / 7,714 | $0.00499 | 20.8 s |
| DeepSeek-V4-Flash-0731 | off | none | 2 | 100% | 100% | 3 / 3 | - | - | 20,184 / 7,579 | $0.00495 | 21.6 s |
| DeepSeek-V4-Flash-0731 | off | none | 3 | 100% | 44% | 9 / 4 | - | A1595/26 A2099/26 A2228/26 A2243/26 B0792/26 | 20,280 / 7,338 | $0.00489 | 19.8 s |
| DeepSeek-V4-Flash-0731 | off | none | 4 | 0% | 0% | 2 / 5 | F2082/26 F2087/26 F2133/26 F2167/26 F2313/26 | A2195/26 B1025/26 | 140,239 / 52,424 | $0.0343 | 57.9 s |
| DeepSeek-V4-Flash-0731 | off | none | 5 | 80% | 36% | 11 / 5 | F2864/26 | A1491/26 A1595/26 A2195/26 B1025/26 B1074/26 D3131/26 D3132/26 | 140,167 / 52,128 | $0.0342 | 61.7 s |
