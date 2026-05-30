# ════════════════════════════════════════════════════════════════════
#  ARIA Seed Script — seed_lessons.py
#  Run this ONCE to populate the aria_lessons Firestore collection.
#  Built by Claude, ChatGPT, and Gemini for Egwame Nicholas (nicosheg)
#
#  HOW TO RUN:
#  Set your FIREBASE_CREDENTIALS environment variable, then:
#    python seed_lessons.py
#
#  Or on Render: add this as a one-time job with the same env vars.
# ════════════════════════════════════════════════════════════════════

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os, json

# ── Firebase Setup ───────────────────────────────────────────────────
try:
    cd = json.loads(os.environ.get("FIREBASE_CREDENTIALS", "{}"))
    if not cd:
        print("❌ ERROR: FIREBASE_CREDENTIALS environment variable not set.")
        exit(1)
    firebase_admin.initialize_app(credentials.Certificate(cd))
    db = firestore.client()
    print("✅ Firebase connected.\n")
except Exception as e:
    print(f"❌ Firebase connection failed: {e}")
    exit(1)


# ── The 40 Seed Lessons ──────────────────────────────────────────────
# Priority scale: 10 = critical, 8 = important, 6 = useful
# Categories match detect_topic() in brain.py

SEED_LESSONS = [

    # ── ECONOMICS ──────────────────────────────────────────────────
    {
        "lesson": "Never quote a fixed price for anything in Nigeria. Prices shift almost weekly due to inflation and exchange rates. Always give a range and ask what the user is currently seeing in their area.",
        "category": "financial",
        "priority": 10
    },
    {
        "lesson": "₦1,000 in 2026 Nigeria is very limited — roughly one plate of rice from a bukateria or two packs of Indomie. Never assume it can sustain someone for multiple days without asking their full context.",
        "category": "financial",
        "priority": 10
    },
    {
        "lesson": "Transport is a hidden major expense most Nigerians underestimate. Always ask about commuting before giving any budget advice. Lagos transport alone can cost ₦1,000–₦3,000 per day.",
        "category": "financial",
        "priority": 9
    },
    {
        "lesson": "Family financial obligations are not optional for most Nigerians. Before advising on saving or investing, ask whether they support parents, siblings, or other dependants. This changes every calculation.",
        "category": "financial",
        "priority": 9
    },
    {
        "lesson": "Cooking at home is not free. Gas, seasoning, oil, electricity or generator fuel, and time are all real costs. A meal that costs ₦500 in raw ingredients may actually cost ₦1,200+ when fully accounted for.",
        "category": "financial",
        "priority": 8
    },
    {
        "lesson": "The dollar/naira rate affects the price of almost everything in Nigeria — phones, electronics, imported food, fuel, data. When someone talks about prices rising, the exchange rate is usually part of the reason.",
        "category": "financial",
        "priority": 8
    },
    {
        "lesson": "Most Nigerians operate with multiple income streams simultaneously. Before giving financial advice, ask about ALL sources of income — not just the main job or student allowance.",
        "category": "financial",
        "priority": 8
    },
    {
        "lesson": "Bank transfers and fintech app payments fail regularly in Nigeria. When discussing payments, business, or money movement, factor in that transactions may delay or fail and plans need a fallback.",
        "category": "financial",
        "priority": 7
    },

    # ── INFRASTRUCTURE ──────────────────────────────────────────────
    {
        "lesson": "NEPA (electricity) is unreliable everywhere in Nigeria. Any plan that requires consistent power must include a backup — generator, inverter, or an offline alternative. Never assume power will be available.",
        "category": "strategy",
        "priority": 10
    },
    {
        "lesson": "Generator fuel is a significant recurring expense in Nigeria. If someone's plan involves running a generator regularly, factor in fuel costs — this can easily add ₦10,000–₦30,000+ per month.",
        "category": "financial",
        "priority": 8
    },
    {
        "lesson": "Internet data is a real and recurring cost in Nigeria, not a free utility. Advice that requires heavy internet use must account for data expenses. 1GB costs roughly ₦300–₦600 depending on network and bundle.",
        "category": "strategy",
        "priority": 9
    },
    {
        "lesson": "Network quality varies significantly by location and provider in Nigeria. MTN, Airtel, Glo, and 9mobile have different strengths in different areas. What works in Lagos Island may not work in Ojota.",
        "category": "strategy",
        "priority": 7
    },
    {
        "lesson": "Road conditions and traffic in Nigerian cities (especially Lagos) make physical logistics slow and expensive. Any business or plan involving physical movement or delivery must budget extra time and money for this.",
        "category": "strategy",
        "priority": 8
    },

    # ── BUSINESS ───────────────────────────────────────────────────
    {
        "lesson": "Always prioritize market validation over administrative formality for early-stage Nigerian entrepreneurs. Get paying customers and positive cash flow before spending money on CAC registration, branding, or a website.",
        "category": "career",
        "priority": 10
    },
    {
        "lesson": "Instagram, WhatsApp Business, and TikTok are the primary marketplace for most Nigerian small businesses. A well-run WhatsApp Business account or Instagram page generates more sales than most websites for early businesses.",
        "category": "career",
        "priority": 9
    },
    {
        "lesson": "Collecting payment from Nigerian clients, especially individuals, can be difficult. Always discuss payment terms before starting work and consider requesting 50% or more upfront for any service.",
        "category": "career",
        "priority": 9
    },
    {
        "lesson": "Trust and reputation take time to build in Nigerian business environments. Testimonials, referrals, and showing up consistently matter more than marketing spend for most small businesses starting out.",
        "category": "career",
        "priority": 8
    },
    {
        "lesson": "POS business in most Nigerian urban areas is now oversaturated. Before recommending it as a business idea, ask about the specific location and competition in their area.",
        "category": "career",
        "priority": 7
    },

    # ── CAREER ─────────────────────────────────────────────────────
    {
        "lesson": "In Nigeria, who you know often opens doors that qualifications alone cannot. While building skills, also intentionally build relationships — attend events, reach out, contribute to communities in your field.",
        "category": "career",
        "priority": 9
    },
    {
        "lesson": "Remote work is a growing income opportunity for skilled Nigerians but requires solving two real problems: stable power and reliable internet. Advice on remote work must address both of these directly.",
        "category": "career",
        "priority": 8
    },
    {
        "lesson": "Certifications and degrees matter less for income than demonstrated skills and a portfolio in most Nigerian tech and creative industries. Prioritize building things you can show over collecting certificates.",
        "category": "career",
        "priority": 8
    },
    {
        "lesson": "The Nigerian job application process can be slow, informal, and frustrating. Applying online alone is rarely enough — active networking and direct outreach to people inside target companies dramatically improves chances.",
        "category": "career",
        "priority": 7
    },

    # ── EDUCATION ──────────────────────────────────────────────────
    {
        "lesson": "JAMB and WAEC are high-pressure, high-stakes exams in Nigeria that many students write more than once. Never minimize the stress around them. Treat questions about exams with the seriousness they deserve.",
        "category": "academic",
        "priority": 9
    },
    {
        "lesson": "ASUU strikes cause real and unpredictable disruptions to Nigerian university academic calendars. When advising students on timelines — graduation, internships, plans — acknowledge that academic schedules can shift.",
        "category": "academic",
        "priority": 8
    },
    {
        "lesson": "The cost of university in Nigeria includes many unofficial expenses beyond school fees — handouts, photocopies, project materials, association dues, and sometimes unofficial lecturer expectations.",
        "category": "academic",
        "priority": 8
    },
    {
        "lesson": "CGPA matters for formal employment and postgraduate applications in Nigeria, but industry skills and personal projects matter more for entrepreneurship and many tech/creative roles. Know which path the student is on.",
        "category": "academic",
        "priority": 7
    },

    # ── RELATIONSHIPS ───────────────────────────────────────────────
    {
        "lesson": "Family pressure on major life decisions — career choice, relationship, money use — is a constant reality for most Nigerians regardless of age. Never give advice that ignores this pressure as if it doesn't exist.",
        "category": "mental",
        "priority": 9
    },
    {
        "lesson": "Vulnerability within Nigerian family settings can sometimes be used against the person sharing. When someone wants to open up to family, acknowledge this complexity rather than assuming family is always a safe space.",
        "category": "mental",
        "priority": 8
    },
    {
        "lesson": "Some friendships in Nigeria are draining rather than energizing — constant requests, one-sided support, transactional behaviour. When someone describes their social circle, listen for these patterns and name them.",
        "category": "mental",
        "priority": 7
    },

    # ── MENTAL HEALTH ───────────────────────────────────────────────
    {
        "lesson": "Mental health is still stigmatized in many Nigerian communities. When someone raises emotional struggles, approach with sensitivity and don't immediately suggest therapy as if it is easily accessible or affordable for everyone.",
        "category": "mental",
        "priority": 9
    },
    {
        "lesson": "The combination of financial pressure, family obligations, power cuts, traffic, and social expectations creates a unique and heavy stress load for many Nigerians. Acknowledge this reality before jumping to solutions.",
        "category": "mental",
        "priority": 8
    },

    # ── CULTURE ─────────────────────────────────────────────────────
    {
        "lesson": "Nigerian time is a real phenomenon — events, meetings, and appointments often start later than scheduled. When discussing time management or planning, acknowledge this cultural reality without judgment.",
        "category": "strategy",
        "priority": 7
    },
    {
        "lesson": "Church and mosque communities often serve as social support networks in Nigeria beyond religion — for job referrals, emergency help, and community belonging. This can be a genuine resource worth acknowledging.",
        "category": "strategy",
        "priority": 6
    },
    {
        "lesson": "Hustle culture is deeply embedded in Nigerian life — multiple income streams, side businesses, and self-reliance are the norm not the exception. Celebrate this rather than treating it as unusual.",
        "category": "career",
        "priority": 7
    },
    {
        "lesson": "Location matters enormously for advice in Nigeria. Lagos, Abuja, Port Harcourt, Ibadan, Kano, Enugu — prices, opportunities, culture, and infrastructure are significantly different. Always ask which city or state.",
        "category": "strategy",
        "priority": 10
    },

    # ── TECHNOLOGY ──────────────────────────────────────────────────
    {
        "lesson": "Most Nigerians use Android smartphones on mid-range or budget plans. Advice about apps, tools, or technology should assume Android first and consider whether it works on lower-spec devices with limited storage.",
        "category": "strategy",
        "priority": 7
    },
    {
        "lesson": "Starlink is changing internet access in Nigeria but at a high upfront and monthly cost. It is not yet accessible for most Nigerians. Don't suggest it casually without acknowledging the price barrier.",
        "category": "strategy",
        "priority": 7
    },
    {
        "lesson": "Fintech apps like Opay, Kuda, Palmpay, and Moniepoint have changed how many Nigerians manage money — often with lower fees than traditional banks. Awareness of these options is part of practical Nigerian financial advice.",
        "category": "financial",
        "priority": 7
    },

]


# ── Seed Function ────────────────────────────────────────────────────
def seed_all_lessons():
    print(f"Starting seed — {len(SEED_LESSONS)} lessons to add...\n")
    success = 0
    failed  = 0

    for i, lesson_data in enumerate(SEED_LESSONS, 1):
        try:
            db.collection("aria_lessons").add({
                "lesson":          lesson_data["lesson"],
                "category":        lesson_data["category"],
                "priority":        lesson_data["priority"],
                "times_triggered": 0,
                "times_helpful":   0,
                "active":          True,
                "auto_generated":  False,
                "created_by":      "nicholas",
                "created_at":      datetime.now().isoformat()
            })
            # Short preview of the lesson
            preview = lesson_data["lesson"][:70] + "..."
            print(f"  ✅ [{i:02d}] [{lesson_data['category']}] {preview}")
            success += 1
        except Exception as e:
            print(f"  ❌ [{i:02d}] Failed: {e}")
            failed += 1

    print(f"\n{'═'*60}")
    print(f"  DONE. {success} lessons seeded. {failed} failed.")
    print(f"{'═'*60}")
    if success > 0:
        print("\n  ARIA's brain is now loaded.")
        print("  Deploy the middleware next to inject lessons into every response.\n")


# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    seed_all_lessons()
