# B-032 results (third audit · OF-21 · local unpushed)

- window UTC: 2026-11-20T14:19:31Z → 2026-11-20T14:20:47Z
- window Asia/Singapore: 2026-11-20T22:19:31+08:00 → 2026-11-20T22:20:47+08:00
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
| PB-B01-AC1 | PASS | http_success_message | True | FAIL |
| PB-B01-AC1 | PASS | single_placed_order_two_lines | True | FAIL |
| PB-B01-AC1 | PASS | line_qtys_match_cart | True | FAIL |
| PB-B01-AC1 | PASS | no_open_legacy_intent | True | FAIL |
| PB-B01-AC1 | PASS | response_no_failure_wording | True | FAIL |
| PB-B01-AC2 | PASS | place_success | True | FAIL |
| PB-B01-AC2 | PASS | five_state_sequence | True | FAIL |
| PB-B01-AC2 | PASS | skip_step_rejected | True | FAIL |
| PB-B01-AC2 | PASS | no_rollback_to_prior_state | True | FAIL |
| PB-B01-AC2 | PASS | customer_admin_advance_tip | True | FAIL |
| PB-B01-AC2 | PASS | no_auto_transition_after_wait | True | FAIL |
| PB-B01-AC2 | PASS | completed_terminal | True | FAIL |
| PB-B01-AC3 | PASS | completed_no_advance | True | FAIL |
| PB-B01-AC3 | PASS | completed_no_customer_cancel | True | FAIL |
| PB-B01-AC3 | PASS | cancelled_no_advance | True | FAIL |
| PB-B01-AC3 | PASS | merchant_cancel_completed_rejected | True | FAIL |
| PB-B01-AC3 | PASS | no_timeout_auto_cancel_scheduler_absent_and_wait_placed | True | FAIL |
| PB-B01-AC4 | PASS | api_full_flow_no_logistics_fields | True | FAIL |
| PB-B01-AC4 | PASS | merchant_ui_orders_flow_screenshot | True | FAIL |
| PB-B01-AC5 | PASS | dup_confirm_rejected_stock_unchanged | True | FAIL |
| PB-B01-AC5 | PASS | dup_ship_complete_stock_unchanged | True | FAIL |
| PB-B01-AC5 | PASS | concurrent_confirm_one_success | True | FAIL |
| PB-B02-AC1 | PASS | place_success | True | FAIL |
| PB-B02-AC1 | PASS | direct_deduct_on_place | True | FAIL |
| PB-B02-AC1 | PASS | complete_no_re_deduct | True | FAIL |
| PB-B02-AC2 | PASS | others_see_deducted_stock | True | FAIL |
| PB-B02-AC2 | PASS | offline_keeps_existing_order_to_complete | True | FAIL |
| PB-B02-AC2 | PASS | new_order_refused_while_offline | True | FAIL |
| PB-B02-AC3 | PASS | reject_invalid_stock_exact_tip_and_stock_unchanged | True | FAIL |
| PB-B02-AC3 | PASS | accept_valid_stock_same_product | True | FAIL |
| PB-B02-AC3 | PASS | stock_edit_same_product_does_not_change_existing_order_lines | True | FAIL |
| PB-B02-AC4 | PASS | list_page1_ok | True | FAIL |
| PB-B02-AC4 | PASS | list_page2_boundary | True | FAIL |
| PB-B02-AC4 | PASS | list_pages_no_id_overlap_when_both_nonempty | True | FAIL |
| PB-B02-AC4 | PASS | list_page0_rejected | True | FAIL |
| PB-B02-AC4 | PASS | base_offline_invisible_cycles | True | FAIL |
| PB-B02-AC5 | PASS | place_deducts_stock | True | FAIL |
| PB-B02-AC5 | PASS | complete_stock_unchanged | True | FAIL |
| PB-B02-AC5 | PASS | cancel_restores_stock | True | FAIL |
| PB-B02-AC5 | PASS | zero_stock_auto_offline_then_cancel_restores_online | True | FAIL |
| PB-B02-AC5 | PASS | manual_offline_stays_offline_after_cancel | True | FAIL |
| PB-B03-AC1 | PASS | unselected_not_in_confirm_snapshot | True | FAIL |
| PB-B03-AC1 | PASS | order_detail_line_by_line | True | FAIL |
| PB-B03-AC1 | PASS | three_place_amount_consistent_confirm_detail_total | True | FAIL |
| PB-B03-AC1 | PASS | new_identity_republish_keeps_old_snapshot | True | FAIL |
| PB-B03-AC1 | PASS | order_created | True | FAIL |
| PB-B03-AC1 | PASS | three_ui_places_list_lines_total | True | FAIL |
| PB-B03-AC2 | PASS | name_price_immutable | True | FAIL |
| PB-B03-AC2 | PASS | description_not_silently_replaced_or_explicit | True | FAIL |
| PB-B03-AC2 | PASS | images_immutable_after_replace_attempts | True | FAIL |
| PB-B03-AC3 | PASS | order_pagination_no_overlap_total_desc | True | FAIL |
| PB-B03-AC3 | PASS | customer_sees_only_own_orders | True | FAIL |
| PB-B03-AC3 | PASS | merchant_sees_sitewide_orders | True | FAIL |
| PB-B03-AC3 | PASS | merchant_order_pagination_page2_no_overlap_total_desc | True | FAIL |
| PB-B03-AC3 | PASS | cancel_party_and_time_in_detail | True | FAIL |
| PB-B03-AC3 | PASS | history_and_admin_polymorphic_screenshots | True | FAIL |
| PB-B03-AC3 | PASS | cancel_party_and_time_in_ui_modal | True | FAIL |
| PB-B03-AC4 | PASS | unauth_tip | True | FAIL |
| PB-B03-AC4 | PASS | invalid_token_tip | True | FAIL |
| PB-B03-AC4 | PASS | multi_incomplete_orders_allowed | True | FAIL |
| PB-B03-AC4 | PASS | other_buyer_access_denied | True | FAIL |
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
| PB-B03-AC5 | PASS | archive_real_id_mutations_rejected_no_state_write | True | FAIL |
| PB-B12-AC1 | PASS | no_direct_order_without_cart_confirm | True | FAIL |
| PB-B12-AC1 | PASS | unauth_confirm_tip | True | FAIL |
| PB-B12-AC1 | PASS | invalid_token_confirm_tip | True | FAIL |
| PB-B12-AC1 | PASS | other_cart_line_tip | True | FAIL |
| PB-B12-AC1 | PASS | mixed_cart_tip | True | FAIL |
| PB-B12-AC1 | PASS | reject_keeps_stock_cart_no_order | True | FAIL |
| PB-B12-AC1 | PASS | product_detail_no_direct_buy_ui | True | FAIL |
| PB-B12-AC2 | PASS | multi_product_one_order_placed | True | FAIL |
| PB-B12-AC2 | PASS | multi_product_whole_order_cancel | True | FAIL |
| PB-B12-AC2 | PASS | single_qty_order | True | FAIL |
| PB-B12-AC3 | PASS | empty_select_rejected | True | FAIL |
| PB-B12-AC3 | PASS | submit_only_valid_selected | True | FAIL |
| PB-B12-AC3 | PASS | ui_invalid_disabled_and_insufficient_hint | True | FAIL |
| PB-B12-AC3 | PASS | ui_select_all_deselect_and_row_toggle | True | FAIL |
| PB-B12-AC3 | PASS | default_selects_only_orderable_after_valid_removed | True | FAIL |
| PB-B12-AC3 | PASS | row_level_checked_maps_to_orderable | True | FAIL |
| PB-B12-AC3 | PASS | stale_offline_row_prepared | True | FAIL |
| PB-B12-AC4 | PASS | confirm_keeps_stock_online | True | FAIL |
| PB-B12-AC4 | PASS | qty_change_rejects | True | FAIL |
| PB-B12-AC4 | PASS | after_confirm_still_online_before_submit | True | FAIL |
| PB-B12-AC4 | PASS | reject_keeps_orders_stock_cart_full_set | True | FAIL |
| PB-B12-AC4 | PASS | new_product_identity_published | True | FAIL |
| PB-B12-AC4 | PASS | reonline_reconfirm_success | True | FAIL |
| PB-B12-AC4 | PASS | after_success_stock_down_still_online | True | FAIL |
| PB-B12-AC4 | PASS | inplace_price_N_A_immutable | True | FAIL |
| PB-B12-AC4 | PASS | confirm_ui_modal_distinct | True | FAIL |
| PB-B12-AC5 | PASS | ui_checkbox_toggle_no_stock_change | True | FAIL |
| PB-B12-AC5 | PASS | clear_cart_api_no_order_stock_change | True | FAIL |
| PB-B12-AC5 | PASS | clear_cart_confirm_modal_screenshot | True | FAIL |
| PB-B12-AC6 | PASS | valid_confirm_first | True | FAIL |
| PB-B12-AC6 | PASS | final_submit_multi_problem_exact_templates | True | FAIL |
| PB-B12-AC6 | PASS | final_submit_fail_full_set_unchanged | True | FAIL |
| PB-B12-AC6 | PASS | empty_select_message | True | FAIL |
| PB-B12-AC6 | PASS | missing_product_rejected | True | FAIL |
| PB-B12-AC6 | PASS | ui_confirm_then_break_then_submit | True | FAIL |
| PB-B12-AC6 | PASS | ui_error_tip_stock_or_offline | True | FAIL |
| PB-B13-AC1 | PASS | pos_http_message | True | FAIL |
| PB-B13-AC1 | PASS | pos_stock_delta | True | FAIL |
| PB-B13-AC1 | PASS | pos_cart_full_set_cleared | True | FAIL |
| PB-B13-AC1 | PASS | pos_order_items_and_checkout_receipt | True | FAIL |
| PB-B13-AC1 | PASS | pos_success_ui_screenshot | True | FAIL |
| PB-B13-AC1 | PASS | neg_no_order_stock_cart_full_set | True | FAIL |
| PB-B13-AC1 | PASS | neg_failure_reason_not_generic_only | True | FAIL |
| PB-B13-AC1 | PASS | multi_product_mid_fault_batch_unchanged | True | FAIL |
| PB-B13-AC1 | PASS | breakpoint_after_order_rollback_and_probe | True | FAIL |
| PB-B13-AC1 | PASS | breakpoint_after_stock_rollback_and_probe | True | FAIL |
| PB-B13-AC1 | PASS | breakpoint_after_cart_rollback_and_probe | True | FAIL |
| PB-B13-AC2 | FAIL | unselected_kept_full_set | True | FAIL |
| PB-B13-AC2 | FAIL | pre_lock_patch_then_submit_rejects | True | FAIL |
| PB-B13-AC2 | FAIL | during_hold_add_same_product_hold_proven | True | FAIL |
| PB-B13-AC2 | FAIL | during_hold_add_retained_in_cart | True | FAIL |
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
| PB-B13-AC4 | PASS | same_product_new_settlement_key_allows_second_order | True | FAIL |
| PB-B13-AC5 | PASS | no_oversell_single_sku | True | FAIL |
| PB-B13-AC5 | PASS | multi_product_no_half_order | True | FAIL |
| PB-B13-AC5 | PASS | lock_before_patch_delete_add_serial_rejects | True | FAIL |
| PB-B13-AC5 | PASS | in_flight_pre_lock_delete_add | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_patch_qty_hold_proven | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_patch_final_order_qty_unchanged | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_delete_selected_hold_proven | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_delete_final_state | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_add_same_selected_hold_proven | True | FAIL |
| PB-B13-AC5 | PASS | during_hold_add_final_retained | True | FAIL |
| PB-B13-AC5 | PASS | offline_submit_rejected | True | FAIL |
