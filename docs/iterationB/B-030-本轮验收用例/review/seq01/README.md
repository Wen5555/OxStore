# SEQ-01 三模式终态证据

- SUT：develop / `29c20ea0927528a98f873f4a1a0e169a6fa12281`
- DB：`oxstore_b030_local`
- all_pass：`True`

| mode | pass | winner | stock | 一单成功 | 失败方车保留 |
|---|---|---|---|---|---|
| a_first | True | A | 0 | True | True |
| b_first | True | B | 0 | True | True |
| simultaneous | True | A | 0 | True | True |

明细 JSON：`review/seq01/<mode>.json`
