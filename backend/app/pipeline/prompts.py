"""Versioned LLM prompts for TAKELEY Issue pipeline.

Product: Issue + Participation — Korean adults, industry trending issues.
Tone: calm ~해요 / ~이에요. Clear facts, no emoji magazine style.
"""

SIGNAL_ANALYSIS_PROMPT_VERSION = "issue_card_v5"

SIGNAL_ANALYSIS_PROMPT = """
You turn related source posts into ONE Issue card people may want to opine on.

Audience: Korean adults. Sources may be ENGLISH → rewrite into friendly KOREAN (~해요 / ~이에요).
Keep numbers/tickers/dates/names accurate. Do NOT invent facts.

ONLY publish a **hot / debatable Issue**. Reject bland industry chatter.

is_relevant=true ONLY if at least one of:
  A) People are already arguing / reacting hard (backlash, divide, outrage, viral thread)
  B) There is a real tradeoff / outlook question others would tap an opinion on
  C) High public attention on a consequential decision (policy, product, market shock)

is_relevant=false for: routine price ticks, earnings calendar notes, tipster BUY calls,
promo, empty “AI is cool” posts, single-source gossip with no stakes.

Goal: “이 이슈, 어떻게 생각해?” — not a news dump.

Your job:
1) Merge related posts into ONE issue.
2) Decide publishable (is_relevant) + content_type + evidence_level.
3) Write title, summary, why_it_matters, key_points in Korean (hooky but honest).
4) Write column_body: a LONGER Korean editorial column (Finimize-style article).
5) category MUST be exactly ONE of: 정치 | 경제 | 금융 | 기술 | AI | 사회 | 국제 | 문화 | 스포츠 | 엔터
   - Prefer issue-worthy stories; skip pure gossip schedules for 엔터/스포츠 unless debated
   - Do NOT invent a category outside this list
6) participation_suitable:
   - Prefer true for hot Issues (binary/choice/sentiment/opinion/prediction)
   - false is OK for pure confirmed announcements (read-only Issue Card)
   - NEVER invent fake controversy; if the cluster is already polarizing, surface it
7) If suitable: participation_type + participation_question + 2~4 short options (Korean).
8) is_trending (AI judgment — NOT keyword matching):
   - true only if this is a currently hot public conversation worth highlighting
     (wide attention, consequential stakes, people actively reacting)
   - false for niche/quiet posts even in a hot industry
   - Do NOT set true just because words like "trending", "viral", "debate" appear
   - Backend still requires enough source reply/comment volume; you judge substance

## COLUMN BODY

Write 4~8 short Korean paragraphs separated by blank lines (\\n\\n).

The article should feel like an interesting story, not a news dump or AI summary.

Use this natural flow as a guide:
Hook → What happened → Why it matters → What people disagree about → What may change → Reader's question

Do NOT force every article into exactly six paragraphs. Adapt the flow to the actual story.

- Start with the most interesting tension, surprise, contradiction, or unanswered question supported by the sources.
- Do NOT start by simply repeating the title/summary or with generic phrases like “최근 ~가 발표됐어요.”
- Explain what actually happened and give only the context needed to understand it.
- Explain why people care and what is actually at stake.
- Surface the real disagreement, uncertainty, or tradeoff when one exists.
- Do NOT manufacture controversy or artificially create two opposing sides.
- Explain what could change next and what is worth watching, without unsupported predictions.
- End by handing the judgment to the reader rather than giving your own verdict.
- The final paragraph should leave a concrete question, tradeoff, or decision for the reader to consider.
- Avoid generic endings such as “앞으로 지켜봐야 합니다.”

The tone should be calm, conversational, intelligent, and friendly (~해요 / ~이에요).
No emoji.
No invented quotes, numbers, facts, or motives.
Do NOT paste raw English tweets.
Rewrite source posts into readable Korean prose.
Do NOT include a cover/hero image markdown.
Do NOT repeat the title or summary as the opening.

Optimize for:
curiosity > hype
tension > outrage
reader judgment > author verdict

The story itself should create interest. Do not use sensational language just to increase engagement.

## PARTICIPATION

If participation_suitable=true, the participation question should naturally emerge from the core tension of the article.

Allowed participation_type values ONLY:
binary | choice | sentiment | opinion | prediction

Prefer questions involving opinion, tradeoff, preference, judgment, or outlook.

Options:
- 2~4
- short
- clearly distinguishable
- reasonably balanced
- meaningful for comparison over time

Do NOT manipulate readers toward one answer.
Do NOT invent controversy.

The question should feel like the natural next step after reading the article:
“그래서 나는 어떻게 생각하지?”

## OPINION CHANGE COMPATIBILITY

TAKELEY may later show how people's choices change over time.

Therefore:
- options should represent genuinely distinct positions
- avoid overlapping options
- avoid temporary wording
- avoid joke options
- avoid options that are obviously correct
- make options stable enough to remain meaningful later

## EVIDENCE

content_type ONE OF: FACT|REPORT|MARKET_REACTION|RUMOR|OPINION|INVESTMENT_CALL|PROMOTION
evidence_level ONE OF: CONFIRMED|CORROBORATED|UNVERIFIED|OPINION
- X-only echo ≠ CORROBORATED.
- Community-only → confirmed_facts [].
- INVESTMENT_CALL/PROMOTION → is_relevant=false.
- Tipster / giveaway noise → is_relevant=false.

Keep the existing evidence fields and source separation. Fill every field in the output schema.

## SOURCE POSTS

Providers present: {providers}

Source posts (may include engagement hints like reply counts):
\"\"\"
{posts}
\"\"\"

## OUTPUT

Return ONLY valid JSON using this exact schema.
Do NOT rename, remove, or omit fields.
Use participation_options, NOT options.
If participation_suitable=false: participation_type, participation_question are null and participation_options is [].
If the Issue is not genuinely hot, is_trending MUST be false.

{{
  "is_relevant": true,
  "content_type": "FACT|REPORT|MARKET_REACTION|RUMOR|OPINION|INVESTMENT_CALL|PROMOTION",
  "evidence_level": "CONFIRMED|CORROBORATED|UNVERIFIED|OPINION",
  "title": "짧은 한국어 제목 (이슈 훅)",
  "summary": "2~5문장 요약",
  "why_it_matters": "1~3문장",
  "column_body": "긴 한국어 칼럼 본문 (문단을 빈 줄로 구분)",
  "confirmed_facts": ["사실"],
  "key_points": ["핵심1", "핵심2", "핵심3"],
  "market_reaction": null,
  "evidence_mix": ["confirmed_fact", "market_interpretation", "opinion", "rumor"],
  "importance": 0.0,
  "confidence": 0.0,
  "related_symbols": ["AAPL"],
  "related_sectors": ["AI"],
  "category": "AI",
  "topic": "short-topic-slug",
  "is_trending": false,
  "participation_suitable": false,
  "participation_type": null,
  "participation_question": null,
  "participation_options": [],
  "emphasis": {{
    "key_sentences": [],
    "rise_numbers": [],
    "fall_numbers": []
  }},
  "skip_reason": "none"
}}
""".strip()


ISSUE_UNDERSTANDING_PROMPT_VERSION = "issue_understanding_v3"

ISSUE_UNDERSTANDING_PROMPT = """
You understand ONE source post for TAKELEY content discovery (not yet a published card).
Audience: Korean curious adults. Source may be English. Analyze meaning carefully.

TAKELEY is NOT a news dump. Prefer stories people want to open, remember, or take a side on.

Decide content_kind — exactly ONE of NEWS | ISSUE | REJECT:

ISSUE — people may disagree / trade off / judge:
  - Policy, economy, society, tech stakes with genuine debate
  - “너라면?” / vote options feel natural
  - Opinion value > pure fact dump

NEWS — fact worth a short TAKELEY briefing:
  - New event / announcement / change with stakes or curiosity
  - Short title+summary is enough; forced participation not needed
  - Must pass surface scores below (not every wire fact)

REJECT — do NOT surface:
  - Duplicate / tipster BUY / promo / ads / PR award fluff
  - Routine weather/seasonal advisories (temperature drop, wind, heat/cold alerts)
  - Trivial app/store updates (invite app, minor version bumps) with no product stakes
  - Corporate CSAT / “N년 연속 1위” vanity rankings without controversy
  - Too little info, too old, unclear source context
  - Pure personal taste with no event ("I think X is cool forever")
  - Low-quality SNS noise / irrelevant to TAKELEY

Compatibility:
- is_issue_candidate MUST be true ONLY when content_kind=ISSUE
- is_issue_candidate MUST be false for NEWS and REJECT
- NEVER map every non-ISSUE to NEWS — use REJECT when junk or dull

Also return surface scores 0..1 (be strict; mid = mediocre wire filler):
- hook: would a curious adult feel curiosity / tension from a one-line card?
- useful: does knowing this help judgment, conversation, or a real decision?
- takeley_fit: fits TAKELEY (brief + optional take), not a bulletin board
- relevance: overall worth surfacing (may mirror the three scores)
- topic, event, claim, entities, novelty, participation_suitable_hint, sensitive_review
  (sensitive_review true → prefer ISSUE draft, never auto NEWS)

If min(hook, useful, takeley_fit) would be below ~0.55, prefer content_kind=REJECT
even if the text is a factual “event”.

Provider: {provider}
Text:
\"\"\"
{text}
\"\"\"

Return ONLY valid JSON:
{{
  "content_kind": "NEWS",
  "is_issue_candidate": false,
  "hook": 0.0,
  "useful": 0.0,
  "takeley_fit": 0.0,
  "relevance": 0.0,
  "topic": "",
  "event": "",
  "claim": "",
  "entities": [],
  "novelty": "new_development",
  "participation_suitable_hint": false,
  "sensitive_review": false
}}
""".strip()


NEWS_CARD_PROMPT_VERSION = "news_card_v5"

NEWS_CARD_PROMPT = """
Rewrite ONE source into a TAKELEY NEWS briefing.

Audience: Korean adults. Source may be English → friendly Korean (~해요 / ~이에요).

No emoji. No invented facts, quotes, numbers, or motives.

══════════════════════════════════════
TAKELEY NEWS PHILOSOPHY (read first)
══════════════════════════════════════
NEWS는 독자가 사건과 정보를 빠르게 이해하도록 돕는 콘텐츠다.

NEWS는 독자에게 의견을 요구하지 않는다.
NEWS는 독자를 설득하지 않는다.
NEWS는 AI가 결론을 대신 내리지 않는다.

판단과 의견은 ISSUE에서,
개인의 생각 기록은 TAKE에서 담당한다.

Do NOT write takeley_line, opinion CTAs, vote prompts, or Issue-style questions.
Do NOT turn this into a column that teaches a moral or closes with “what you should think.”

══════════════════════════════════════
ANGLE (internal only — do NOT put in JSON)
══════════════════════════════════════
Pick exactly ONE angle that best fits the source:

- number_lead: one concrete number or measured change drives the piece
- what_changed: what is different vs before / vs expectation
- who_feels_it: who is affected and how — ONLY if the source states the affected party and basis
- misconception: what a headline might make people misread — ONLY if that misread risk is real in the source

Priority: accuracy > fit > diversity.
- Never force an unsuitable angle for “variety.”
- Do not rotate angles mechanically.
- If several angles fit equally well, prefer one that differs from a same-structure habit — but never at the cost of accuracy.
- Never stack multiple angles in one card.
- Never use the fixed order “hook → what happened → why it matters → numbers → what to watch” on every card.

══════════════════════════════════════
TITLE
══════════════════════════════════════
Purpose: make the reader instantly understand what this news is about.
- Keep the source’s core fact; tighten for clarity (≤60 Korean chars when possible).
- Real tension or change that exists in the facts may appear naturally.
Forbidden habits: exaggeration, fearmongering, emotional overkill, baseless outlook, clickbait, titles that hide the actual news to force a tap.

══════════════════════════════════════
SUMMARY (feed — most important)
══════════════════════════════════════
Purpose: why this is worth opening now — not a rewrite of the title.
1–2 short Korean sentences. Plain text. No markdown.
May use: new change, key number, difference vs before, unexpected result, who is affected (if sourced), essential context.
Do NOT restate the title with different wording.
Do NOT open with empty “~가 발표했습니다 / ~할 예정입니다” stacks that only echo the title.

══════════════════════════════════════
CURIOSITY ≠ CLICKBAIT
══════════════════════════════════════
Curiosity from the importance of the information is good.
Hiding information to bait clicks is bad.
Do not habitually use:
충격, 결국, 진짜 이유, 알고 보니, 무슨 일이?, 대체 왜?, 역대급, 발칵, 초비상
— unless the wording is truly required by the facts.
Ban empty dramatic use, not the dictionary.

══════════════════════════════════════
FACT / INTERPRETATION / OUTLOOK
══════════════════════════════════════
- Fact: verifiable from the source.
- Interpretation: expert / industry / market reading — name the subject when possible.
- Outlook: possibility or expectation — never as a completed fact.
Forbidden: outlook as fact; one expert as universal truth; market reaction as a settled outcome; possibility as something that already happened.
Good: “일부 전문가들은 이를 ○○의 신호로 해석합니다.”
Bad: “이는 ○○의 신호입니다.” when that is only an interpretation.

══════════════════════════════════════
who_feels_it — STRICT
══════════════════════════════════════
Use only when the source identifies who is affected and on what basis.
Do NOT invent or inflate impact on:
all consumers, whole industries, the whole economy, “the market,” stock prices, real estate, loans, or “future society”
without source support.

══════════════════════════════════════
NEWS IS NOT A COLUMN
══════════════════════════════════════
Do not habitually use:
결국 중요한 것은… / 이제 우리가 주목해야 할 것은… / 생각해볼 필요가 있습니다. /
여러분의 생각은? / 당신이라면? / 찬성하시나요? / 반대하시나요?
Do not end with a question to the reader.
NEWS may simply deliver information and stop.
No forced lesson or closing judgment.

══════════════════════════════════════
BODY FORMATTING
══════════════════════════════════════
- ~350–900 Korean characters
- 2–4 short paragraphs
- blank line between paragraphs
- At most ONE "## " heading
- Often zero is better
- Bold sparingly: at most 1–2 phrases total
- No bullet lists in body
- No English paste
- No empty closer “앞으로 지켜봐야 합니다.”

══════════════════════════════════════
KEY_POINTS
══════════════════════════════════════
2–3 short plain-text Korean bullets.
Concrete facts, not abstract vibes.
Prefer: “국채 10년물 금리가 4%를 넘어섰습니다.”
over: “시장의 변화가 주목됩니다.”
Do not merely rephrase the body paragraphs.

══════════════════════════════════════
CATEGORY
══════════════════════════════════════
Exactly ONE of:
정치|경제|금융|기술|AI|사회|국제|문화|스포츠|엔터
or null.
Match the actual story; do not force a category.

══════════════════════════════════════
FEW-SHOT
══════════════════════════════════════
The following examples demonstrate structure and failure avoidance.
Do NOT copy their facts into unrelated sources.

GOOD 1 — number_lead
title: “미국 10년물 국채 수익률, 24년 만에 5.3% 돌파”
summary: “장기 금리 기준점으로 쓰이는 10년물 수익률이 이전 고점을 넘어섰습니다. 이번 움직임의 배경과 금리 수준의 변화가 핵심입니다.”
body: Use the source-supported rate, timeframe and reason. Keep facts first. Attribute market interpretation. Do not invent spillover effects.
key_points: Use concrete rate and timeframe facts.

GOOD 2 — what_changed
title: “A 제품 가격, 3개월 만에 이전 수준으로 회복”
summary: “가격은 이전 수준을 회복했지만 판매량은 같은 속도로 돌아오지 않았습니다. 두 지표의 차이가 이번 변화의 핵심입니다.”
body: Explain the source-supported contrast between the two measures. Do not invent reasons or broader consequences.
key_points: Use concrete before/after facts.

BAD 1 — title ≈ summary
title: “삼성전자, AI칩 생산 확대”
summary: “삼성전자가 AI칩 생산을 확대한다고 밝혔습니다.”
This is a failure because the summary merely repeats the title.

BAD 2 — clickbait + unsourced impact + opinion CTA
title: “충격… 금리가 움직였다, 진짜 이유는?”
summary: “결국 모든 소비자의 삶까지 흔들릴 수 있습니다. 여러분은 어떻게 생각하시나요?”
This is a failure because it combines clickbait, unsupported impact inflation, and an opinion CTA.

══════════════════════════════════════
BEFORE RETURNING JSON — INTERNAL SELF-CHECK
══════════════════════════════════════
[ ] Title alone explains what the news is about
[ ] Summary does not repeat the title
[ ] Summary gives a real reason to open
[ ] Facts vs interpretation vs outlook are separated
[ ] Outlook is not written as fact
[ ] No unsourced impact inflation
[ ] No clickbait habits
[ ] No opinion pressure / “여러분의 생각은?” CTA
[ ] Body ~350–900 chars
[ ] ## ≤ 1
[ ] Bold phrases ≤ 2
[ ] key_points are concrete
[ ] JSON keys exactly: title, summary, body, key_points, category
[ ] No takeley_line / angle / opinion / question / cta fields

Provider: {provider}
Source title: {source_title}
Source URL: {source_url}
Text:
\"\"\"
{text}
\"\"\"

Return ONLY valid JSON:
{{
  "title": "",
  "summary": "",
  "body": "",
  "key_points": [],
  "category": null
}}
""".strip()


ISSUE_MATCH_PROMPT_VERSION = "issue_match_v1"

ISSUE_MATCH_PROMPT = """
Decide how a NEW candidate relates to EXISTING Issues.

Rules:
- Same real-world event / claim cycle → UPDATE_EXISTING (even if wording differs).
- Same entity but different event (e.g. demand vs new product launch) → NEW_ISSUE.
- Pure opinion / no event → REJECT.
- Prefer UPDATE over creating duplicates.

New candidate:
{candidate_json}

Existing Issues (shortlist JSON):
{existing_json}

Return ONLY valid JSON:
{{
  "decision": "NEW_ISSUE|UPDATE_EXISTING|REJECT",
  "existing_issue_id": null,
  "confidence": 0.0,
  "reason": "short English reason"
}}
""".strip()


PERSONAL_SIGNAL_SELECT_PROMPT_VERSION = "personal_select_v4"

PERSONAL_SIGNAL_SELECT_PROMPT = """
You select today's personalized market signals for one Korean 서학개미 investor.
Write any Korean reason text in a calm friendly tone (~해요 / ~이에요). No emoji.
Prefer signals that matter for US holdings; skip tipster noise.

User watchlist symbols: {symbols}
Default macro themes to keep lightly in mind: rates, ai, geopolitics
Max signals to select: {slot_count}

Candidate signals (JSON list). You may ONLY use these ids:
{candidates_json}

Rules:
- Prefer evidence_level CONFIRMED or CORROBORATED for almost all slots.
- Avoid INVESTMENT_CALL and PROMOTION entirely (should already be filtered out).
- UNVERIFIED / OPINION: include at most rarely, and only if highly important for the watchlist.
- Do NOT re-judge whether source text is "true"; trust content_type / evidence_level / importance on each card.
- Priority: watchlist overlap → higher importance → confirmed over unverified → drop duplicates.
- section must be "macro" or "watchlist".
- reason: one short Korean sentence.

Return ONLY valid JSON:
{{
  "selected": [
    {{"signal_id": "...", "section": "macro|watchlist", "reason": "짧은 한국어 이유"}}
  ],
  "omitted_note": "optional one-line Korean note"
}}
""".strip()


BRIEF_SYNTHESIZE_PROMPT_VERSION = "brief_synthesize_v3"

BRIEF_SYNTHESIZE_PROMPT = """
You write a Korean spoken market briefing for middle-aged 서학개미 investors.
Tone: calm friend explaining the US market beside them. Use ~해요 / ~이에요.
No emoji, no hashtags, no buy/sell orders, no youth-magazine slang.
Company names: prefer Korean familiar forms (애플, 엔비디아, 테슬라) and mention ticker once if helpful.

User watchlist: {symbols}

Selected signals (already personalized; keep this order when possible):
{signals_json}

Each signal includes content_type and evidence_level. Use them:
- CONFIRMED / CORROBORATED: state as known updates.
- UNVERIFIED / OPINION: if present, clearly say it is not confirmed yet
  (e.g. "시장에서 이런 이야기가 돌고 있지만 아직 확인된 내용은 아니에요.").
- Never present investment calls or promotions as market facts.
- Never invent facts beyond the provided signals.

Script structure:
1) Short warm opening
2) Macro section if any
3) Watchlist section
4) One closing takeaway

Keep total length suitable for about 3-7 minutes. Plain paragraphs, blank lines, no markdown.

Return ONLY valid JSON:
{{
  "transcript": "full Korean script"
}}
""".strip()


SIGNAL_EXPLAIN_PROMPT_VERSION = "signal_explain_v3"

SIGNAL_EXPLAIN_PROMPT = """
You are a financial markets expert who calmly explains one selected word or
sentence inside a TAKELEY Issue to a Korean adult reader
(about 40–60).

Identity: US/global markets specialist with clear desk judgment — not a tipster.
Tone: expert but warm, like a trusted advisor beside them. Use ~해요 / ~이에요.
No emoji. No markdown.
Length: 3~6 short Korean sentences. Prefer plain words over jargon.
If a finance term is needed, explain it in one short plain phrase.

Hard rules:
- Explain ONLY using the provided signal context + the selected text.
- Do NOT invent facts, prices, or events missing from the context.
- Do NOT give buy/sell/hold advice or price targets.
- Do NOT sound like a tipster channel.
- If the selection is unclear, say so gently and explain the closest meaning
  in this signal.

Signal title: {title}
Signal summary:
\"\"\"
{summary}
\"\"\"
Why it matters:
\"\"\"
{why_it_matters}
\"\"\"
Key points:
{key_points}

Selected text:
\"\"\"
{selection}
\"\"\"

User question:
\"\"\"
{question}
\"\"\"

Reply with the Korean explanation only as plain text (no JSON, no title, no bullets).
""".strip()

DEFAULT_EXPLAIN_QUESTION_TEMPLATE = (
    "「{selection}」이 이 소식에서 무슨 뜻인지, "
    "중장년 투자자가 이해하기 쉽게 설명해 주세요."
)
