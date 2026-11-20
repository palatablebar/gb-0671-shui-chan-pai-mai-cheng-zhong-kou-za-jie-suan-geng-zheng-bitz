# 深度登记 水产拍卖结算

规模：中型。使用者：水产批发市场结算员。核心规则：先毛皮配对，再扣杂计价，按更正链选择唯一生效版，只支付差额。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 称重采信 | 查看并执行称重采信 | `POST /api/intake` | `app/modules/intake/rules.py` | `tests/test_intake.py` |
| M2 货品换算 | 查看并执行货品换算 | `POST /api/conversion` | `app/modules/conversion/rules.py` | `tests/test_conversion.py` |
| M3 毛皮配对 | 查看并执行毛皮配对 | `POST /api/pairing` | `app/modules/pairing/rules.py` | `tests/test_pairing.py` |
| M4 补秤结算 | 核验补秤边界并形成每票可付款结果 | `POST /api/reweigh` | `app/modules/reweigh/rules.py` | `tests/test_reweigh.py` |
| M5 扣杂竞价 | 查看并执行扣杂竞价 | `POST /api/auction` | `app/modules/auction/rules.py` | `tests/test_auction.py` |
| M6 更正裁决 | 查看并执行更正裁决 | `POST /api/correction` | `app/modules/correction/rules.py` | `tests/test_correction.py` |
| M7 应付对账 | 查看并执行应付对账 | `POST /api/reconcile` | `app/modules/reconcile/rules.py` | `tests/test_reconcile.py` |
| M8 结算归档 | 查看并执行结算归档 | `POST /api/archive` | `app/modules/archive/rules.py` | `tests/test_archive.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码中文票据 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_legacy_encoding` |
| TRAP-02 | BOM表头 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_bom_real` |
| TRAP-04 | 分段表头 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_repeated_header_real` |
| TRAP-05 | 缺列记录 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_bad_columns_real` |
| TRAP-07 | 空值哨兵 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/conversion/rules.py` | `tests/test_conversion.py::test_sentinel_real` |
| TRAP-08 | 前导零票号 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_leading_zero_real` |
| TRAP-14 | 重复编号不同原值 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_duplicate_conflict_real` |
| TRAP-18 | 三类空态 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_empty_states` |
| TRAP-15 | 吨与千克混合 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/conversion/rules.py` | `tests/test_conversion.py::test_tonnes_counterexample` |
| TRAP-06 | 全角千分位 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/conversion/rules.py` | `tests/test_conversion.py::test_fullwidth_thousands` |
| TRAP-10 | 金额半分舍入 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/auction/rules.py` | `tests/test_auction.py::test_half_cent_rounding` |
| TRAP-26 | 陈旧更正分支 | 静默错算或丢失证据 | 显式归一与原因裁决 | `app/modules/correction/rules.py` | `tests/test_correction.py::test_stale_branch` |
| TRAP-31 | 补秤缺对应原票 | 沿用任意旧票皮重拼证据 | 同票同版本核验，缺失即 REWEIGH_NO_ORIGINAL 隔离 | `app/modules/reweigh/rules.py` | `tests/test_reweigh.py::test_missing_original_blocked_real` |
| TRAP-32 | 补秤品类与原票不一致 | 跨品类沿用皮重错算 | 品类核验，不一致即 REWEIGH_FISH_MISMATCH 隔离 | `app/modules/reweigh/rules.py` | `tests/test_reweigh.py::test_fish_mismatch_blocked_real` |
| TRAP-33 | 补秤成交依据冲突 | 单价扣杂率被悄悄替换 | 留空继承、显式填写必须一致，否则 REWEIGH_DEAL_MISMATCH | `app/modules/reweigh/rules.py` | `tests/test_reweigh.py::test_deal_mismatch_blocked_real` |
| TRAP-34 | 同票补秤重复且毛重冲突 | 重复补款或覆盖原始证据 | 全部 REWEIGH_DUPLICATE 隔离，旧版结果保留；同值重复只计一次 | `app/modules/reweigh/rules.py` | `tests/test_reweigh.py::test_conflicting_duplicate_all_quarantined_real` |

## 对账规则

输入=采纳原始行+隔离行+空行+同值重复行+重复表头+补秤采纳行+同值补秤重复行。计价版本总额与生效票总额分别展示，避免把更正前后重复求和。最终应付=已付+待付，负待付为退款。补秤阻断票保留被替代原票的旧版可付款结果，不进入补秤可付款清单。

## 已知不覆盖

无称重设备实时接入，采用现场导出文件。无支付执行，只生成可复核结算证据。
