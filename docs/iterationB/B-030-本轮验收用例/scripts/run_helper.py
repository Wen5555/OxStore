#!/usr/bin/env python3
"""CLI for helpers formerly referenced as helper:* in cases.

Examples:
  python3 scripts/run_helper.py place_order --product P-ON-10 --qty 2
  python3 scripts/run_helper.py dual_confirm --product P-ON-1
  python3 scripts/run_helper.py cart_qty --product P-ON-10 --qty 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import load_env, login_customer, login_seller  # noqa: E402
from helpers_lib import HELPERS, load_fixtures  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("helper", choices=sorted(HELPERS.keys()))
    ap.add_argument("--product", default="P-ON-10")
    ap.add_argument("--qty", default="1")
    ap.add_argument("--order-id", default="")
    ap.add_argument("--status", default="PLACED")
    ap.add_argument("--cart-item-id", default="")
    ap.add_argument("--confirmation-token", default="")
    ap.add_argument("--as-seller", action="store_true")
    ap.add_argument("--account", default="CUSTOMER_A")
    args = ap.parse_args()
    env = load_env()
    load_fixtures()  # ensure ready
    fn = HELPERS[args.helper]
    try:
        if args.helper == "place_order":
            out = fn(env, product=args.product, qty=args.qty, account=args.account)
        elif args.helper == "cart_qty":
            token = login_customer(env, args.account)
            out = fn(env, token, product=args.product, qty=args.qty)
        elif args.helper == "checkout_submit":
            token = login_customer(env, args.account)
            if args.confirmation_token:
                out = fn(env, token, confirmation_token=args.confirmation_token)
            elif args.cart_item_id:
                out = fn(env, token, cart_item_ids=[args.cart_item_id])
            else:
                raise SystemExit("need --confirmation-token or --cart-item-id")
        elif args.helper == "dual_confirm":
            out = fn(env, product=args.product, qty=args.qty)
        elif args.helper == "advance_to":
            if not args.order_id:
                raise SystemExit("--order-id required")
            out = fn(env, args.order_id, args.status)
        elif args.helper == "order_in_status":
            out = fn(env, status=args.status, product=args.product, qty=args.qty)
        elif args.helper == "cancel":
            if not args.order_id:
                raise SystemExit("--order-id required")
            out = fn(env, args.order_id, args.status, as_seller=args.as_seller)
        elif args.helper == "confirm":
            token = login_customer(env, args.account)
            out = fn(env, token, args.cart_item_id)
        elif args.helper == "submit":
            token = login_customer(env, args.account)
            out = fn(env, token, args.confirmation_token)
        elif args.helper in ("seed_terminal_orders", "cart_two_lines", "cancel_restock_matrix"):
            out = fn(env)
        elif args.helper == "mutate_product":
            out = fn(env, product=args.product)
        elif args.helper == "favorite_then_offline":
            out = fn(env, product=args.product)
        else:
            out = fn(env)
    except Exception as e:
        print(json.dumps({"ok": False, "helper": args.helper, "error": str(e)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "helper": args.helper, "result": out}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
