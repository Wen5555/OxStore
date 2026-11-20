# B-032 results (second audit · OF-19)

- window UTC: 2026-11-20T12:34:07Z → 2026-11-20T12:35:11Z
- window Asia/Singapore: 2026-11-20T20:34:07+08:00 → 2026-11-20T20:35:11+08:00
- sut: develop@29c20ea0927528a98f873f4a1a0e169a6fa12281
- db: oxstore_b032_local
- totals: PASS 25 / FAIL 1 / BLOCKED 0 / NOT_EXECUTED 0 / total 26

## AC verdicts

| AC | Verdict |
|---|---|
| PB-B01-AC1 | PASS |
| PB-B01-AC2 | PASS |
| PB-B01-AC3 | PASS |
| PB-B01-AC4 | PASS |
| PB-B01-AC5 | PASS |
| PB-B02-AC1 | PASS |
| PB-B02-AC2 | PASS |
| PB-B02-AC3 | PASS |
| PB-B02-AC4 | PASS |
| PB-B02-AC5 | PASS |
| PB-B03-AC1 | PASS |
| PB-B03-AC2 | PASS |
| PB-B03-AC3 | PASS |
| PB-B03-AC4 | PASS |
| PB-B03-AC5 | PASS |
| PB-B12-AC1 | PASS |
| PB-B12-AC2 | PASS |
| PB-B12-AC3 | PASS |
| PB-B12-AC4 | PASS |
| PB-B12-AC5 | PASS |
| PB-B12-AC6 | PASS |
| PB-B13-AC1 | PASS |
| PB-B13-AC2 | FAIL |
| PB-B13-AC3 | PASS |
| PB-B13-AC4 | PASS |
| PB-B13-AC5 | PASS |

## Conjunct evidence table

| AC | AC verdict | Conjunct | Pass | If fail |
|---|---|---|---|---|
| PB-B01-AC1 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B01-AC2 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B01-AC3 | PASS | completed_no_advance | True | FAIL |
| PB-B01-AC3 | PASS | completed_no_customer_cancel | True | FAIL |
| PB-B01-AC3 | PASS | cancelled_no_advance | True | FAIL |
| PB-B01-AC3 | PASS | merchant_cancel_placed | True | FAIL |
| PB-B01-AC3 | PASS | no_timeout_auto_cancel_source_and_wait | True | FAIL |
| PB-B01-AC4 | PASS | api_full_flow_no_logistics_fields | True | FAIL |
| PB-B01-AC4 | PASS | merchant_ui_orders_flow_screenshot | True | FAIL |
| PB-B01-AC5 | PASS | dup_confirm_rejected_stock_unchanged | True | FAIL |
| PB-B01-AC5 | PASS | dup_ship_complete_stock_unchanged | True | FAIL |
| PB-B01-AC5 | PASS | concurrent_confirm_one_success | True | FAIL |
| PB-B02-AC1 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B02-AC2 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B02-AC3 | PASS | reject_non_numeric_and_signed | True | FAIL |
| PB-B02-AC3 | PASS | accept_valid_stock | True | FAIL |
| PB-B02-AC3 | PASS | stock_edit_does_not_change_existing_order | True | FAIL |
| PB-B02-AC4 | PASS | list_page1_ok | True | FAIL |
| PB-B02-AC4 | PASS | list_page2_boundary | True | FAIL |
| PB-B02-AC4 | PASS | list_pages_no_id_overlap_when_both_nonempty | True | FAIL |
| PB-B02-AC4 | PASS | list_page0_rejected | True | FAIL |
| PB-B02-AC4 | PASS | base_offline_invisible_cycles | True | FAIL |
| PB-B02-AC5 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B03-AC1 | PASS | unselected_not_in_confirm_snapshot | True | FAIL |
| PB-B03-AC1 | PASS | snapshot_stable_after_republish_mutate | True | FAIL |
| PB-B03-AC1 | PASS | detail_lines_match_total | True | FAIL |
| PB-B03-AC1 | PASS | confirm_detail_total_consistent | True | FAIL |
| PB-B03-AC1 | PASS | order_created | True | FAIL |
| PB-B03-AC2 | PASS | name_price_immutable | True | FAIL |
| PB-B03-AC2 | PASS | description_not_silently_replaced_or_explicit | True | FAIL |
| PB-B03-AC3 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B03-AC4 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B03-AC5 | PASS | no_fake_close_api_as_path | True | FAIL |
| PB-B03-AC5 | PASS | seed_statuses_SUCCESS_FAILED_QUEUING_IN_TRANSACTION | True | FAIL |
| PB-B03-AC5 | PASS | seed_FROZEN_TRADE_and_MANUAL_products | True | FAIL |
| PB-B03-AC5 | PASS | seed_unfinished_trade_attempt | True | FAIL |
| PB-B03-AC5 | PASS | v8_migration_executed | True | NOT_EXECUTED |
| PB-B03-AC5 | PASS | migration_closes_QUEUING_IN_TRANSACTION_keep_status | True | FAIL |
| PB-B03-AC5 | PASS | SUCCESS_FAILED_history_untouched | True | FAIL |
| PB-B03-AC5 | PASS | trade_attempt_legacy_closed_unfinished | True | FAIL |
| PB-B03-AC5 | PASS | TRADE_product_unfrozen_ONLINE | True | FAIL |
| PB-B03-AC5 | PASS | MANUAL_frozen_becomes_OFFLINE_MANUAL | True | FAIL |
| PB-B03-AC5 | PASS | stock_not_replenished | True | FAIL |
| PB-B03-AC5 | PASS | no_new_order_from_migration | True | FAIL |
| PB-B03-AC5 | PASS | archive_admin_response_content | True | FAIL |
| PB-B03-AC5 | PASS | archive_customer_own_response_content | True | FAIL |
| PB-B03-AC5 | PASS | archive_customer_isolation | True | FAIL |
| PB-B03-AC5 | PASS | archive_read_only_rejects_mutations | True | FAIL |
| PB-B12-AC1 | PASS | (legacy single-verdict AC — no explicit conjunct list) | True |  |
| PB-B12-AC2 | PASS | multi_product_one_order_placed | True | FAIL |
| PB-B12-AC2 | PASS | multi_product_whole_order_cancel | True | FAIL |
| PB-B12-AC2 | PASS | single_qty_order | True | FAIL |
| PB-B12-AC3 | PASS | empty_select_rejected | True | FAIL |
| PB-B12-AC3 | PASS | submit_only_valid_selected | True | FAIL |
| PB-B12-AC3 | PASS | ui_has_invalid_or_disabled_offline_rows | True | FAIL |
| PB-B12-AC3 | PASS | stale_offline_row_prepared | True | FAIL |
| PB-B12-AC4 | PASS | confirm_keeps_stock_online | True | FAIL |
| PB-B12-AC4 | PASS | qty_change_rejects | True | FAIL |
| PB-B12-AC4 | PASS | reject_keeps_orders_stock_cart_full_set | True | FAIL |
| PB-B12-AC4 | PASS | republish_reconfirm_success | True | FAIL |
| PB-B12-AC4 | PASS | after_success_stock_down_still_online | True | FAIL |
| PB-B12-AC4 | PASS | inplace_price_N_A_immutable | True | FAIL |
| PB-B12-AC4 | PASS | confirm_ui_modal_distinct | True | FAIL |
| PB-B12-AC5 | PASS | select_toggle_no_stock_change | True | FAIL |
| PB-B12-AC5 | PASS | clear_cart_api_no_order_stock_change | True | FAIL |
| PB-B12-AC5 | PASS | clear_cart_confirm_modal_screenshot | True | FAIL |
| PB-B12-AC6 | PASS | multi_problem_rows_listed | True | FAIL |
| PB-B12-AC6 | PASS | final_fail_stock_cart_unchanged | True | FAIL |
| PB-B12-AC6 | PASS | empty_select_message | True | FAIL |
| PB-B12-AC6 | PASS | ui_error_tip_screenshot | True | FAIL |
| PB-B13-AC1 | PASS | pos_http_message | True | FAIL |
| PB-B13-AC1 | PASS | pos_stock_delta | True | FAIL |
| PB-B13-AC1 | PASS | pos_cart_full_set_cleared | True | FAIL |
| PB-B13-AC1 | PASS | pos_order_items_receipts_persisted | True | FAIL |
| PB-B13-AC1 | PASS | pos_success_ui_screenshot | True | FAIL |
| PB-B13-AC1 | PASS | neg_no_order_stock_cart_full_set | True | FAIL |
| PB-B13-AC1 | PASS | neg_failure_reason_not_generic_only | True | FAIL |
| PB-B13-AC1 | PASS | multi_product_mid_fault_batch_unchanged | True | FAIL |
| PB-B13-AC1 | PASS | breakpoint_after_order_rollback_and_probe | True | FAIL |
| PB-B13-AC1 | PASS | breakpoint_after_stock_rollback_and_probe | True | FAIL |
| PB-B13-AC1 | PASS | breakpoint_after_cart_rollback_and_probe | True | FAIL |
| PB-B13-AC2 | FAIL | unselected_kept_full_set | True | FAIL |
| PB-B13-AC2 | FAIL | pre_lock_patch_then_submit_rejects | True | FAIL |
| PB-B13-AC2 | FAIL | during_hold_add_same_product_timeline | True | FAIL |
| PB-B13-AC2 | FAIL | during_hold_add_final_state_recorded | True | FAIL |
| PB-B13-AC2 | FAIL | remainder_gt0_via_public_api | False | FAIL |
| PB-B13-AC3 | PASS | snapshot_stable_through_complete | True | FAIL |
| PB-B13-AC3 | PASS | stock0_existing_cart_submit_rejected | True | FAIL |
| PB-B13-AC3 | PASS | customer_cancel_no_cart_restore | True | FAIL |
| PB-B13-AC3 | PASS | merchant_cancel_no_cart_restore | True | FAIL |
| PB-B13-AC4 | PASS | first_success | True | FAIL |
| PB-B13-AC4 | PASS | lost_response_replay | True | FAIL |
| PB-B13-AC4 | PASS | recovered_in_history | True | FAIL |
| PB-B13-AC4 | PASS | idempotency_not_cart_clear_after_new_add | True | FAIL |
| PB-B13-AC4 | PASS | concurrent_same_key_one_order_stock_once | True | FAIL |
| PB-B13-AC5 | PASS | no_oversell_single_sku | True | FAIL |
| PB-B13-AC5 | PASS | multi_product_no_half_order | True | FAIL |
| PB-B13-AC5 | PASS | lock_before_patch_serial_rejects | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_patch_qty_started_in_hold | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_patch_does_not_inflate_order | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_delete_selected_started_in_hold | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_add_same_selected_started_in_hold | True | FAIL |
| PB-B13-AC5 | PASS | offline_submit_rejected | True | FAIL |
