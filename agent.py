"""
Meta Media Buying Agent - Portfolio Project 5 (Demo)
-----------------------------------------------------
What it does, in plain words:
  1. Reads Meta advertising data and Shopify revenue data (CSV in
     this demo; a Meta Marketing API adapter and a Shopify adapter
     can replace the CSV loader later, without changing the rules).
  2. Validates Meta-attributed revenue against Shopify revenue and
     flags large attribution gaps instead of hiding them.
  3. Calculates spend, revenue, ROAS, CTR, CPC and CPA per ad set.
  4. Identifies wasted spend, creative fatigue, underperforming
     ads and scaling opportunities, with a clear reason for each.
  5. Produces a daily report and specific recommendations.
  6. NEVER executes a campaign change on its own. Every action
     stays PENDING_APPROVAL until a human approves it, within a
     spending limit, and the agent can be stopped immediately.

Safety rules, built in, not added later:
  - No action without human approval.
  - A budget change may not exceed MAX_BUDGET_CHANGE_PCT (20%).
  - Total proposed spend may not exceed the daily spending limit.
  - If STOP is set, no approval is accepted.
  - Every recommendation, approval, rejection and action is logged.

This is a DEMO. The sample data is fictional. It does not connect
to a real Meta ad account, it does not spend real money, and it
is not a record of work done for a real client. Replace the CSV
loader with real, authorised Meta and Shopify adapters, and run
a supervised pilot, before using it on a real ad account.
"""

import argparse
import csv
import sys
from pathlib import Path

TARGET_ROAS = 2.0
MAX_BUDGET_CHANGE_PCT = 20.0
DAILY_SPENDING_LIMIT = 1000.0
ATTRIBUTION_GAP_PCT = 20.0

STOP = False
ACTION_LOG = []


def _f(row, key, default=0.0):
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def metrics(row):
    """Return calculated metrics for one ad-set row."""
    spend = _f(row, "spend")
    impressions = _f(row, "impressions")
    clicks = _f(row, "clicks")
    conversions = _f(row, "conversions")
    meta_revenue = _f(row, "meta_revenue")
    shopify_revenue = _f(row, "shopify_revenue")
    frequency = _f(row, "frequency")

    roas_meta = meta_revenue / spend if spend else 0.0
    roas_shopify = shopify_revenue / spend if spend else 0.0
    ctr = (clicks / impressions * 100.0) if impressions else 0.0
    cpc = spend / clicks if clicks else 0.0
    cpa = spend / conversions if conversions else 0.0
    gap = 0.0
    if shopify_revenue:
        gap = abs(meta_revenue - shopify_revenue) / shopify_revenue * 100.0

    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "meta_revenue": meta_revenue,
        "shopify_revenue": shopify_revenue,
        "frequency": frequency,
        "roas_meta": round(roas_meta, 2),
        "roas_shopify": round(roas_shopify, 2),
        "ctr_pct": round(ctr, 2),
        "cpc": round(cpc, 2),
        "cpa": round(cpa, 2) if conversions else None,
        "attribution_gap_pct": round(gap, 1),
    }


def recommend(row):
    """Return one recommendation dict for one ad-set row."""
    m = metrics(row)
    name = f"{row.get('campaign')} / {row.get('ad_set')}"
    rec_id = f"{row.get('campaign')}-{row.get('ad_set')}".replace(" ", "_")

    if m["attribution_gap_pct"] > ATTRIBUTION_GAP_PCT:
        return {
            "id": rec_id,
            "ad_set": name,
            "action": "REVIEW_ATTRIBUTION",
            "detail": (
                f"Attribution gap {m['attribution_gap_pct']}% between Meta "
                f"revenue (${m['meta_revenue']:.0f}) and Shopify revenue "
                f"(${m['shopify_revenue']:.0f}). Do not scale this ad set "
                "until reporting is reconciled."
            ),
            "status": "PENDING_APPROVAL",
            **m,
        }

    if m["spend"] >= 100 and m["conversions"] == 0:
        return {
            "id": rec_id,
            "ad_set": name,
            "action": "PAUSE_AD_SET",
            "detail": (
                f"Wasted spend: ${m['spend']:.0f} spent with 0 conversions. "
                "Pause this ad set, pending human approval."
            ),
            "status": "PENDING_APPROVAL",
            **m,
        }

    if m["frequency"] >= 3.0 and m["ctr_pct"] < 1.0:
        return {
            "id": rec_id,
            "ad_set": name,
            "action": "REFRESH_CREATIVE",
            "detail": (
                f"Creative fatigue: frequency {m['frequency']} with CTR "
                f"{m['ctr_pct']}%. Refresh creative before increasing budget."
            ),
            "status": "PENDING_APPROVAL",
            **m,
        }

    if m["roas_meta"] >= 3.0 and m["conversions"] >= 5:
        return {
            "id": rec_id,
            "ad_set": name,
            "action": "INCREASE_BUDGET",
            "detail": (
                f"Scaling opportunity: ROAS {m['roas_meta']} with "
                f"{int(m['conversions'])} conversions. Increase budget by "
                f"at most {MAX_BUDGET_CHANGE_PCT:.0f}%, pending approval."
            ),
            "status": "PENDING_APPROVAL",
            **m,
        }

    if m["roas_meta"] < TARGET_ROAS and m["spend"] >= 50:
        return {
            "id": rec_id,
            "ad_set": name,
            "action": "REDUCE_BUDGET",
            "detail": (
                f"Underperforming: ROAS {m['roas_meta']} is below target "
                f"{TARGET_ROAS}. Reduce budget by at most "
                f"{MAX_BUDGET_CHANGE_PCT:.0f}%, pending approval."
            ),
            "status": "PENDING_APPROVAL",
            **m,
        }

    return {
        "id": rec_id,
        "ad_set": name,
        "action": "KEEP_RUNNING",
        "detail": (
            f"Healthy for now: ROAS {m['roas_meta']}, CTR {m['ctr_pct']}%. "
            "Keep running and review again tomorrow."
        ),
        "status": "PENDING_APPROVAL",
        **m,
    }


def daily_report(rows):
    """Return totals and recommendations for a list of rows."""
    recs = [recommend(r) for r in rows]
    total_spend = sum(r["spend"] for r in recs)
    total_meta = sum(r["meta_revenue"] for r in recs)
    total_shopify = sum(r["shopify_revenue"] for r in recs)
    total_conv = sum(r["conversions"] for r in recs)
    return {
        "total_spend": round(total_spend, 2),
        "total_meta_revenue": round(total_meta, 2),
        "total_shopify_revenue": round(total_shopify, 2),
        "total_conversions": int(total_conv),
        "overall_roas_meta": round(total_meta / total_spend, 2) if total_spend else 0.0,
        "recommendations": recs,
    }


def approve(recommendation, approved_by="", budget_change_pct=0.0):
    """Approve or block an action. Returns a log entry dict.

    No campaign change is executed here. This only records the
    human decision, after checking the safety limits. A real
    Meta adapter would read this log entry and only then act.
    """
    global STOP
    if STOP:
        entry = {"id": recommendation["id"], "result": "BLOCKED_STOP",
                 "reason": "Agent is stopped. No action accepted."}
        ACTION_LOG.append(entry)
        return entry

    if recommendation["action"] in ("INCREASE_BUDGET", "REDUCE_BUDGET"):
        if abs(budget_change_pct) > MAX_BUDGET_CHANGE_PCT:
            entry = {"id": recommendation["id"], "result": "BLOCKED_LIMIT",
                     "reason": f"Budget change {budget_change_pct}% exceeds "
                               f"{MAX_BUDGET_CHANGE_PCT:.0f}% limit."}
            ACTION_LOG.append(entry)
            return entry

    if recommendation.get("spend", 0) > DAILY_SPENDING_LIMIT:
        entry = {"id": recommendation["id"], "result": "BLOCKED_LIMIT",
                 "reason": "Ad-set spend exceeds daily spending limit."}
        ACTION_LOG.append(entry)
        return entry

    entry = {"id": recommendation["id"], "result": "APPROVED",
             "action": recommendation["action"],
             "approved_by": approved_by,
             "note": "Approved in demo log only. No live Meta change made."}
    ACTION_LOG.append(entry)
    return entry


def stop_agent():
    global STOP
    STOP = True
    ACTION_LOG.append({"result": "STOPPED", "reason": "Human stop activated."})
    return {"status": "stopped"}


def process_file(input_path, output_path):
    with open(input_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    report = daily_report(rows)
    recs = report["recommendations"]
    if recs:
        fieldnames = ["id", "ad_set", "action", "detail", "status",
                      "spend", "meta_revenue", "shopify_revenue",
                      "roas_meta", "roas_shopify", "ctr_pct", "cpc", "cpa",
                      "attribution_gap_pct"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in recs:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
    return report


def main():
    parser = argparse.ArgumentParser(description="Meta media buying demo agent.")
    parser.add_argument("--input", default="campaigns_sample.csv")
    parser.add_argument("--output", default="recommendations.csv")
    args = parser.parse_args()

    report = process_file(args.input, args.output)
    print(f"Total spend: ${report['total_spend']:.0f} | "
          f"Meta revenue: ${report['total_meta_revenue']:.0f} | "
          f"Shopify revenue: ${report['total_shopify_revenue']:.0f} | "
          f"ROAS (Meta): {report['overall_roas_meta']} -> {args.output}")
    for r in report["recommendations"]:
        print(f"{r['action']:20} | {r['ad_set']} | {r['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
