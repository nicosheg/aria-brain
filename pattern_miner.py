# ════════════════════════════════════════════════════════════════════
#  ARIA Pattern Mining Engine — pattern_miner.py
#  Built by Egwame Nicholas (nicosheg) | github.com/nicosheg
#
#  PURPOSE:
#  Analyzes ARIA's interaction logs and discovers what makes
#  responses work. Saves discovered patterns as new lessons.
#
#  HOW IT RUNS:
#  Triggered via: GET /mine?key=aria_mine_nicholas_2026
#  Run manually after every 50+ new rated interactions.
#
#  WHAT IT DISCOVERS:
#  - Do short or long responses rate higher per topic?
#  - Do responses ending with questions rate higher?
#  - Does Nigerian slang increase satisfaction?
#  - Which topics need more context before advising?
# ════════════════════════════════════════════════════════════════════

from datetime import datetime


def mine_patterns(db):
    """
    Main mining function.
    Reads rated interactions, finds patterns, saves as lessons.
    Returns a summary of what was discovered.
    """
    if not db:
        return {"error": "Firebase not connected"}

    results = {
        "status": "complete",
        "total_interactions": 0,
        "topics_analyzed": 0,
        "patterns_discovered": 0,
        "lessons_saved": 0,
        "details": []
    }

    # ── Step 1: Fetch all rated interactions ──────────────────────
    # Try new schema field first (feedback_score), then old (rating)
    docs = []
    try:
        docs = list(db.collection("aria_learning")
                     .where("feedback_score", ">", 0)
                     .stream())
    except:
        pass

    if not docs:
        try:
            docs = list(db.collection("aria_learning")
                         .where("rating", ">", 0)
                         .stream())
        except:
            return {"error": "Could not fetch interactions from Firestore"}

    if len(docs) < 20:
        return {
            "status": "insufficient_data",
            "message": f"Only {len(docs)} rated interactions. Need 20+ to mine patterns. Keep collecting feedback."
        }

    results["total_interactions"] = len(docs)

    # ── Step 2: Group interactions by topic ───────────────────────
    by_topic = {}
    for doc in docs:
        data = doc.to_dict()
        topic   = data.get("topic", "general")
        score   = data.get("feedback_score") or data.get("rating") or 0
        resp    = data.get("aria_response", "")
        msg     = data.get("user_message", "")

        if score == 0 or not resp:
            continue

        if topic not in by_topic:
            by_topic[topic] = {"high": [], "low": [], "all": []}

        entry = {
            "response":        resp,
            "message":         msg,
            "score":           score,
            "resp_length":     data.get("response_length", len(resp)),
            "msg_length":      data.get("message_length", len(msg))
        }

        by_topic[topic]["all"].append(entry)
        if score >= 4:
            by_topic[topic]["high"].append(entry)
        elif score <= 2:
            by_topic[topic]["low"].append(entry)

    # ── Step 3: Analyze each topic ────────────────────────────────
    for topic, data in by_topic.items():
        high = data["high"]
        low  = data["low"]

        # Need at least 5 high-rated samples to draw conclusions
        if len(high) < 5:
            continue

        results["topics_analyzed"] += 1

        # ── Pattern A: Response length preference ─────────────────
        avg_high_len = sum(e["resp_length"] for e in high) / len(high)
        avg_low_len  = sum(e["resp_length"] for e in low)  / len(low) if low else avg_high_len

        if avg_high_len < avg_low_len * 0.7:
            # High-rated responses are significantly shorter
            lesson = (
                f"For {topic} questions, shorter responses "
                f"(under {int(avg_high_len)} characters) consistently get "
                f"higher ratings. Users prefer concise answers over long ones."
            )
            confidence = min(0.92, 0.5 + len(high) * 0.01)
            saved = _save_lesson(db, lesson, topic, confidence, len(high))
            results["patterns_discovered"] += 1
            if saved: results["lessons_saved"] += 1
            results["details"].append({
                "topic":   topic,
                "pattern": "shorter_responses_preferred",
                "avg_high_length": int(avg_high_len),
                "avg_low_length":  int(avg_low_len),
                "samples": len(high)
            })

        elif avg_high_len > avg_low_len * 1.3:
            # High-rated responses are significantly longer
            lesson = (
                f"For {topic} questions, detailed responses "
                f"({int(avg_high_len)}+ characters) get higher ratings. "
                f"Users want depth and explanation, not short answers."
            )
            confidence = min(0.88, 0.5 + len(high) * 0.009)
            saved = _save_lesson(db, lesson, topic, confidence, len(high))
            results["patterns_discovered"] += 1
            if saved: results["lessons_saved"] += 1
            results["details"].append({
                "topic":   topic,
                "pattern": "detailed_responses_preferred",
                "avg_high_length": int(avg_high_len),
                "samples": len(high)
            })

        # ── Pattern B: Question ending preference ─────────────────
        high_with_q = (
            sum(1 for e in high if "?" in e["response"][-150:]) / len(high)
        )
        low_with_q = (
            sum(1 for e in low if "?" in e["response"][-150:]) / len(low)
            if low else 0.5
        )

        if high_with_q > 0.65 and high_with_q > low_with_q + 0.20:
            lesson = (
                f"For {topic} conversations, ending responses with a "
                f"follow-up question increases ratings significantly. "
                f"{int(high_with_q*100)}% of top-rated responses ended with a question."
            )
            confidence = min(0.90, 0.5 + len(high) * 0.008)
            saved = _save_lesson(db, lesson, topic, confidence, len(high))
            results["patterns_discovered"] += 1
            if saved: results["lessons_saved"] += 1
            results["details"].append({
                "topic":             topic,
                "pattern":           "question_ending_preferred",
                "high_question_rate": round(high_with_q, 2),
                "low_question_rate":  round(low_with_q, 2),
                "samples":           len(high)
            })

        # ── Pattern C: Nigerian slang increases satisfaction ───────
        nigerian = ["omo","enh","na ","sha","abeg","wahala","wetin","dey ","naira","₦"]
        high_ng = (
            sum(1 for e in high if any(w in e["response"].lower() for w in nigerian))
            / len(high)
        )
        low_ng = (
            sum(1 for e in low if any(w in e["response"].lower() for w in nigerian))
            / len(low) if low else 0.5
        )

        if high_ng > 0.55 and high_ng > low_ng + 0.15:
            lesson = (
                f"For {topic} conversations, using natural Nigerian expressions "
                f"increases user satisfaction. "
                f"{int(high_ng*100)}% of top-rated responses used Nigerian slang naturally."
            )
            confidence = min(0.85, 0.5 + len(high) * 0.007)
            saved = _save_lesson(db, lesson, topic, confidence, len(high))
            results["patterns_discovered"] += 1
            if saved: results["lessons_saved"] += 1
            results["details"].append({
                "topic":           topic,
                "pattern":         "nigerian_slang_increases_rating",
                "high_slang_rate": round(high_ng, 2),
                "low_slang_rate":  round(low_ng, 2),
                "samples":         len(high)
            })

        # ── Pattern D: Context-first preference ───────────────────
        # Responses that don't start with a question (answer first)
        high_ans_first = (
            sum(1 for e in high
                if not e["response"].strip()[:60].startswith(("Before","Can you","Could","What","Which","Where","How many")))
            / len(high)
        )

        low_ans_first = (
            sum(1 for e in low
                if not e["response"].strip()[:60].startswith(("Before","Can you","Could","What","Which","Where","How many")))
            / len(low) if low else 0.5
        )

        if high_ans_first > 0.75 and high_ans_first > low_ans_first + 0.15:
            lesson = (
                f"For {topic} questions, leading with the answer or insight "
                f"before asking for context gets higher ratings. "
                f"{int(high_ans_first*100)}% of top-rated responses gave value first."
            )
            confidence = min(0.88, 0.5 + len(high) * 0.008)
            saved = _save_lesson(db, lesson, topic, confidence, len(high))
            results["patterns_discovered"] += 1
            if saved: results["lessons_saved"] += 1
            results["details"].append({
                "topic":           topic,
                "pattern":         "answer_first_preferred",
                "answer_first_rate": round(high_ans_first, 2),
                "samples":         len(high)
            })

    return results


def _save_lesson(db, lesson, category, confidence, evidence_count):
    """
    Save a discovered pattern as a new lesson in aria_lessons.
    Skips if a similar auto-generated lesson already exists for this topic.
    Returns True if saved, False if skipped.
    """
    try:
        # Check for existing auto-generated lessons in this category
        existing = list(
            db.collection("aria_lessons")
              .where("category",       "==", category)
              .where("auto_generated", "==", True)
              .stream()
        )

        # Simple dedup: if same category pattern type already exists, update it
        for doc in existing:
            data = doc.to_dict()
            # If this lesson text is very similar, update confidence instead
            if data.get("pattern_type","") == f"{category}_{lesson[:30]}":
                if confidence > data.get("confidence_score", 0):
                    doc.reference.update({
                        "confidence_score": confidence,
                        "evidence_count":   evidence_count,
                        "last_updated":     datetime.now().isoformat()
                    })
                return False  # Not a new save

        # Save new discovered lesson
        db.collection("aria_lessons").add({
            "lesson":           lesson,
            "category":         category,
            "priority":         int(confidence * 7),  # Max 6-7 for auto-generated (lower than manual seeds at 10)
            "active":           True,
            "auto_generated":   True,
            "confidence_score": confidence,
            "evidence_count":   evidence_count,
            "created_by":       "pattern_miner",
            "created_at":       datetime.now().isoformat(),
            "times_triggered":  0,
            "times_helpful":    0
        })
        return True

    except:
        return False

