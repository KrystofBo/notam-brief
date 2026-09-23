# Benchmark results

Snapshot `2026-09-22`, labels `eval/labels_flat.csv`. Recall and precision are pooled over routes; the other columns are means per briefing. *Hints* is the computed route geometry given to the model; *Prompt* is the first 7 hex digits of the system prompt's SHA-1.

| Model | Pre-filter | Hints | Reasoning | Prompt | Recall | Precision | Items to read | NOTAMs sent | Tokens in | Tokens out | Cost / briefing | Pre-filter time | Model latency |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 100% | 56% | 8.5 | 30 | 7,332 | 2,046 | $0.00160 | 9.5 ms | 13.6 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 100% | 64% | 7.5 | 30 | 6,086 | 2,020 | $0.00142 | 11.4 ms | 14.1 s |

## Per route

| Model | Pre-filter | Hints | Reasoning | Prompt | Route (run) | Recall | Precision | Flagged / labelled | Missed | False positives | Tokens in/out | Cost | Pre-filter time | Model latency |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 1 (1) | 100% | 70% | 10 / 7 | - | A1529/26 A2203/26 B1037/26 | 6,145 / 1,887 | $0.00139 | 4.5 ms | 11.9 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 2 (1) | 100% | 100% | 3 / 3 | - | - | 5,377 / 1,086 | $0.00106 | 7.1 ms | 9.8 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 3 (1) | 100% | 36% | 11 / 4 | - | A1595/26 A2099/26 A2228/26 A2243/26 B0792/26 B0923/26 B1076/26 | 12,763 / 3,510 | $0.00277 | 15.9 ms | 19.0 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 4 (1) | 100% | 50% | 10 / 5 | - | B0733/26 F2264/26 F2609/26 F2633/26 F2924/26 | 6,555 / 1,796 | $0.00142 | 5.5 ms | 9.6 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 5 (1) | 100% | 50% | 10 / 5 | - | A1491/26 B0733/26 B0896/26 B1074/26 F2967/26 | 5,821 / 1,908 | $0.00135 | 5.5 ms | 13.7 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 1 (1) | 100% | 88% | 8 / 7 | - | A2203/26 | 5,299 / 1,816 | $0.00125 | 13.3 ms | 9.6 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 2 (1) | 100% | 100% | 3 / 3 | - | - | 4,591 / 1,206 | $0.00098 | 6.1 ms | 7.8 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 3 (1) | 100% | 50% | 8 / 4 | - | A1595/26 A2099/26 A2243/26 B0792/26 | 10,198 / 3,210 | $0.00233 | 14.9 ms | 22.4 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 4 (1) | 100% | 50% | 10 / 5 | - | B0733/26 F2264/26 F2609/26 F2633/26 F2924/26 | 5,406 / 1,925 | $0.00130 | 8.1 ms | 10.2 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 5 (1) | 100% | 56% | 9 / 5 | - | A1491/26 B0733/26 B1074/26 F2967/26 | 4,934 / 1,816 | $0.00120 | 43.2 ms | 12.3 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 1 (2) | 100% | 78% | 9 / 7 | - | A2203/26 B1037/26 | 6,145 / 1,813 | $0.00137 | 6.0 ms | 11.9 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 2 (2) | 100% | 100% | 3 / 3 | - | - | 5,377 / 1,267 | $0.00111 | 4.3 ms | 15.5 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 3 (2) | 100% | 36% | 11 / 4 | - | A1595/26 A2099/26 A2228/26 A2243/26 B0792/26 B0923/26 B1076/26 | 12,763 / 3,515 | $0.00277 | 16.2 ms | 19.9 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 4 (2) | 100% | 50% | 10 / 5 | - | B0733/26 F2264/26 F2609/26 F2633/26 F2924/26 | 6,555 / 1,766 | $0.00141 | 8.4 ms | 11.1 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 5 (2) | 100% | 62% | 8 / 5 | - | A1491/26 B0733/26 B1074/26 | 5,821 / 1,758 | $0.00131 | 21.4 ms | 11.2 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 1 (2) | 100% | 88% | 8 / 7 | - | A2203/26 | 5,299 / 2,031 | $0.00131 | 5.9 ms | 17.3 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 2 (2) | 100% | 100% | 3 / 3 | - | - | 4,591 / 1,121 | $0.00096 | 4.3 ms | 6.5 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 3 (2) | 100% | 50% | 8 / 4 | - | A1595/26 A2099/26 A2243/26 B0792/26 | 10,198 / 3,430 | $0.00239 | 12.8 ms | 21.9 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 4 (2) | 100% | 50% | 10 / 5 | - | B0733/26 F2264/26 F2609/26 F2633/26 F2924/26 | 5,406 / 1,753 | $0.00125 | 19.6 ms | 10.3 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 5 (2) | 100% | 56% | 9 / 5 | - | A1491/26 B0733/26 B1074/26 F2967/26 | 4,934 / 1,847 | $0.00121 | 8.3 ms | 12.1 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 1 (3) | 100% | 78% | 9 / 7 | - | A2203/26 B1037/26 | 6,145 / 1,835 | $0.00137 | 4.2 ms | 11.5 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 2 (3) | 100% | 100% | 3 / 3 | - | - | 5,377 / 1,138 | $0.00107 | 4.7 ms | 6.9 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 3 (3) | 100% | 36% | 11 / 4 | - | A1595/26 A2099/26 A2228/26 A2243/26 B0792/26 B0923/26 B1076/26 | 12,763 / 3,499 | $0.00277 | 25.3 ms | 23.2 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 4 (3) | 100% | 50% | 10 / 5 | - | B0733/26 F2264/26 F2609/26 F2633/26 F2924/26 | 6,555 / 1,788 | $0.00142 | 8.6 ms | 11.2 s |
| DeepSeek-V4-Flash-0731 | on | on | none | ff0299f | 5 (3) | 100% | 50% | 10 / 5 | - | A1491/26 B0733/26 B0896/26 B1074/26 F2967/26 | 5,821 / 2,126 | $0.00141 | 5.3 ms | 17.6 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 1 (3) | 100% | 100% | 7 / 7 | - | - | 5,299 / 1,748 | $0.00123 | 4.4 ms | 11.4 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 2 (3) | 100% | 100% | 3 / 3 | - | - | 4,591 / 1,181 | $0.00097 | 6.3 ms | 11.2 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 3 (3) | 100% | 50% | 8 / 4 | - | A1595/26 A2099/26 A2243/26 B0792/26 | 10,198 / 3,417 | $0.00238 | 13.1 ms | 27.1 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 4 (3) | 100% | 50% | 10 / 5 | - | B0733/26 F2264/26 F2609/26 F2633/26 F2924/26 | 5,406 / 1,967 | $0.00131 | 4.9 ms | 14.4 s |
| DeepSeek-V4-Flash-0731 | on | off | none | ff0299f | 5 (3) | 100% | 56% | 9 / 5 | - | A1491/26 B0733/26 B1074/26 F2967/26 | 4,934 / 1,835 | $0.00120 | 5.7 ms | 16.6 s |
