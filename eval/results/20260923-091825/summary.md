# Benchmark results

Snapshot `2026-09-22`, labels `eval/labels_flat.csv`. Recall and precision are pooled over routes; the other columns are means per briefing. Latency is the model stage only.

| Model | Pre-filter | Reasoning | Recall | Precision | Items to read | NOTAMs sent | Tokens in | Tokens out | Cost / briefing | Latency |
|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-ai/DeepSeek-V4-Flash-0731 | on | none | 100% | 63% | 7.6 | 30 | 5,852 | 2,031 | $0.00139 | 14.1 s |
| deepseek-ai/DeepSeek-V4-Flash-0731 | on | default | 96% | 79% | 5.8 | 30 | 5,852 | 5,739 | $0.00243 | 39.1 s |

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
