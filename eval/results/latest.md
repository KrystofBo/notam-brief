# Benchmark results (20260923-092314-combined)

Snapshot `2026-09-22`, labels `eval/labels_flat.csv`. Recall and precision are pooled over routes; the other columns are means per briefing. Latency is the model stage only.

| Model | Pre-filter | Reasoning | Recall | Precision | Items to read | NOTAMs sent | Tokens in | Tokens out | Cost / briefing | Latency |
|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-ai/DeepSeek-V4-Flash-0731 | on | none | 100% | 63% | 7.6 | 30 | 5,852 | 2,031 | $0.00139 | 14.1 s |
| deepseek-ai/DeepSeek-V4-Flash-0731 | on | default | 96% | 79% | 5.8 | 30 | 5,852 | 5,739 | $0.00243 | 39.1 s |
| deepseek-ai/DeepSeek-V4-Flash-0731 | off | none | 75% | 47% | 7.6 | 457 | 68,211 | 25,437 | $0.0167 | 36.4 s |

## Per route

| Model | Pre-filter | Reasoning | Route | Recall | Precision | Flagged / labelled | Missed | False positives | Tokens in/out | Cost | Latency |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DeepSeek-V4-Flash-0731 | on | none | 1 | 100% | 100% | 7 / 7 | - | - | 5,065 / 1,672 | $0.00118 | 13.0 s |
| DeepSeek-V4-Flash-0731 | on | none | 2 | 100% | 100% | 3 / 3 | - | - | 4,357 / 1,159 | $0.00093 | 8.1 s |
| DeepSeek-V4-Flash-0731 | on | none | 3 | 100% | 50% | 8 / 4 | - | A1595/26 A2099/26 A2243/26 B0792/26 | 9,964 / 3,567 | $0.00239 | 21.3 s |
| DeepSeek-V4-Flash-0731 | on | none | 4 | 100% | 50% | 10 / 5 | - | B0733/26 F2264/26 F2609/26 F2633/26 F2924/26 | 5,172 / 1,914 | $0.00126 | 13.5 s |
| DeepSeek-V4-Flash-0731 | on | none | 5 | 100% | 50% | 10 / 5 | - | A1491/26 B0733/26 B0896/26 B1074/26 F2967/26 | 4,700 / 1,841 | $0.00117 | 14.6 s |
| DeepSeek-V4-Flash-0731 | on | default | 1 | 86% | 100% | 6 / 7 | A2068/26 | - | 5,065 / 4,810 | $0.00206 | 35.3 s |
| DeepSeek-V4-Flash-0731 | on | default | 2 | 100% | 100% | 3 / 3 | - | - | 4,357 / 2,520 | $0.00132 | 18.0 s |
| DeepSeek-V4-Flash-0731 | on | default | 3 | 100% | 67% | 6 / 4 | - | A1595/26 A2099/26 | 9,964 / 10,867 | $0.00444 | 69.3 s |
| DeepSeek-V4-Flash-0731 | on | default | 4 | 100% | 56% | 9 / 5 | - | F2264/26 F2609/26 F2633/26 F2924/26 | 5,172 / 5,287 | $0.00220 | 35.5 s |
| DeepSeek-V4-Flash-0731 | on | default | 5 | 100% | 100% | 5 / 5 | - | - | 4,700 / 5,213 | $0.00212 | 37.2 s |
| DeepSeek-V4-Flash-0731 | off | none | 1 | 100% | 54% | 13 / 7 | - | A1473/26 A1529/26 A1595/26 A2070/26 A2195/26 B1025/26 | 20,186 / 7,714 | $0.00499 | 20.8 s |
| DeepSeek-V4-Flash-0731 | off | none | 2 | 100% | 100% | 3 / 3 | - | - | 20,184 / 7,579 | $0.00495 | 21.6 s |
| DeepSeek-V4-Flash-0731 | off | none | 3 | 100% | 44% | 9 / 4 | - | A1595/26 A2099/26 A2228/26 A2243/26 B0792/26 | 20,280 / 7,338 | $0.00489 | 19.8 s |
| DeepSeek-V4-Flash-0731 | off | none | 4 | 0% | 0% | 2 / 5 | F2082/26 F2087/26 F2133/26 F2167/26 F2313/26 | A2195/26 B1025/26 | 140,239 / 52,424 | $0.0343 | 57.9 s |
| DeepSeek-V4-Flash-0731 | off | none | 5 | 80% | 36% | 11 / 5 | F2864/26 | A1491/26 A1595/26 A2195/26 B1025/26 B1074/26 D3131/26 D3132/26 | 140,167 / 52,128 | $0.0342 | 61.7 s |
