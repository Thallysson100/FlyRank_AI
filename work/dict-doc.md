# The full warehouse release (weeks 3+)

The starter CSV above is a 30k-row teaching slice. Lane and capstone work run on the **full
pseudonymized warehouse release** — ~79M rows of daily search performance hosted as Parquet on
Hugging Face (gated; notebook 03 walks through access and the DuckDB workflow).

## Tables

| Table | Grain | Use it for |
|---|---|---|
| `dim_clients` | one row per pseudonymized client | history coverage (`gsc_data_start`, `ga4_data_start`), access profile |
| `dim_content` | one row per pseudonymized content item | content metadata, keyword context, joins |
| `fact_content_daily_performance` | report_date × client × content | time-series features, trend labels, forward-window validation. Partitioned by `month=YYYY-MM` |
| `fact_content_query_90d` | client × content × query hash (fixed 90-day window) | query-mix features: diversity, concentration, rare/anonymized tail |


```
dim_clients:
First row: {'client_hash_id': 'client_04660893ae39614a', 'is_active': True, 'has_gsc_access': True, 'has_ga4_access': True, 'access_profile': 'gsc_and_ga4', 'client_created_date': Timestamp('2026-04-15 00:00:00'), 'client_updated_date': Timestamp('2026-06-27 00:00:00'), 'gsc_data_start': NaT, 'ga4_data_start': Timestamp('2026-05-22 00:00:00')}

dim_content:
First row: {'client_hash_id': 'client_04660893ae39614a', 'content_hash_id': 'content_004de9653278b5a4', 'keyword_hash_id': 'keyword_e754999ab88dd9f2', 'url_hash_id': 'url_d6091f18cf628794', 'keyword_char_count': 22, 'keyword_token_count': 4, 'url_char_count': 108, 'content_created_date': Timestamp('2026-05-30 00:00:00'), 'content_updated_date': Timestamp('2026-07-01 00:00:00'), 'content_type': 'keyword article', 'search_volume': 30, 'competition': 0.91, 'competition_level': 'HIGH', 'cpc': 0.98, 'main_intent': 'transactional', 'backlinks': 16, 'category_count': 3, 'keyword_created_date': Timestamp('2026-05-12 00:00:00'), 'provider_used': 'gemini-generate-content', 'model_used': 'gemini-3-flash-preview', 'char_count': 15682, 'word_count': 2555, 'last_optimized_date': NaT, 'optimization_eligible_date': NaT, 'is_published': True, 'is_deleted': False}

fact_daily_sample:
First row: {'report_date': Timestamp('2026-06-01 00:00:00'), 'client_hash_id': 'client_3ffa76342f366962', 'content_hash_id': 'content_1a6296faee432dae', 'client_has_gsc': True, 'client_has_ga4': True, 'gsc_data_available': False, 'ga4_data_available': False, 'gsc_impressions': 0, 'gsc_clicks': 0, 'gsc_sum_position': 0, 'gsc_avg_position': nan, 'ga4_pageviews': 0, 'ga4_sessions': 0, 'ga4_users': 0, 'ga4_engaged_sessions': 0, 'ga4_total_engagement_sec': 0, 'sessions_organic': 0, 'sessions_direct': 0, 'sessions_referral': 0, 'sessions_social': 0, 'sessions_paid': 0, 'sessions_ai': 0, 'ai_chatgpt': 0, 'ai_perplexity': 0, 'ai_gemini': 0, 'ai_copilot': 0, 'ai_claude': 0, 'ai_meta': 0, 'ai_other': 0, 'scroll_events': 0, 'month': '2026-06'}

fact_query_90d:
First row: {'client_hash_id': 'client_08a6a72ff48e62c0', 'content_hash_id': 'content_447894f2faf0d2bc', 'query_hash_id': 'query_58b1b001f839d699', 'query_char_count': 17, 'query_token_count': 3, 'window_start': Timestamp('2026-04-02 00:00:00'), 'window_end': Timestamp('2026-06-30 00:00:00'), 'impressions_90d': 11, 'clicks_90d': 0, 'impressions_last30': 0, 'clicks_last30': 0, 'impressions_prev30': 11, 'clicks_prev30': 0, 'avg_position_90d': 10.818181818181818, 'avg_position_last30': nan, 'avg_position_prev30': 10.818181818181818, 'content_total_impressions_90d': 1466, 'content_visible_query_count': 14, 'rare_query_count': 32, 'rare_impressions_share': 0.04365620736698499, 'anonymized_impressions_share': 0.7251023192360164}

```

---
# Feature descriptions for the FlyRank warehouse tables

This file summarizes the main features shown in the warehouse sample rows and aligns them with the project data dictionary conventions: identifiers are for joins and grouping, ratings are stored as percentages, and trend/label fields should not be used as model features.

## dim_clients

| Feature | Description |
|---|---|
| `client_hash_id` | Pseudonymous client ID used to join client-level records across tables. It is an identifier, not a predictive feature. |
| `is_active` | Whether the client is currently active in the platform. Useful for filtering or cohort analysis. |
| `has_gsc_access` | Indicates whether the client has Google Search Console access for the relevant data window. |
| `has_ga4_access` | Indicates whether the client has Google Analytics 4 access for the relevant data window. |
| `access_profile` | High-level access type, such as `gsc_and_ga4`, showing which data sources are available to the client. |
| `client_created_date` | Date the client record was created in the platform data. |
| `client_updated_date` | Most recent update date for the client record. |
| `gsc_data_start` | Earliest date with usable GSC data for that client. Important for defining valid time windows and avoiding leakage from incomplete histories. Can be `NaT` (NULL) for clients without GSC access. |
| `ga4_data_start` | Earliest date with usable GA4 data for that client. GA4 values before this date may be zero-filled and should not be treated as true zeros. Can be `NaT` (NULL) for clients without GA4 access. |

## dim_content

| Feature | Description |
|---|---|
| `client_hash_id` | Pseudonymous client identifier linking the article to its owner. |
| `content_hash_id` | Pseudonymous content ID for a single page or article. This is a row key and should be used for joins or splits, not as a feature. |
| `keyword_hash_id` | Pseudonymous keyword identifier for the target keyword associated with the content. Useful for keyword-level context and joins. |
| `url_hash_id` | Pseudonymous URL identifier. Helps trace the URL used for a piece of content without exposing raw URLs. |
| `keyword_char_count` | Number of characters in the target keyword. Small signal for query specificity or complexity. |
| `keyword_token_count` | Number of tokens in the target keyword. Can help distinguish short vs. long queries. |
| `url_char_count` | URL length in characters. Can serve as a weak content or page-structure indicator. |
| `content_created_date` | Date the content was created. Used for content age and recency analysis. |
| `content_updated_date` | Most recent content update date. Useful for freshness features and update recency. |
| `content_type` | Category of the content, such as `keyword article`, used for metadata segmentation and missingness checks. **Note:** Missingness in keyword-context columns is systematic, not random — follows `content_type` patterns. Check missingness per `content_type` before imputing. |
| `search_volume` | Estimated search volume for the target keyword. A content demand metric and a common SEO feature. |
| `competition` | Keyword competition score on a 0–1 scale. Higher numbers mean tougher ranking competition. |
| `competition_level` | Categorical competition level (`LOW`, `MEDIUM`, `HIGH`). Useful for coarse-grained keyword quality segmentation. |
| `cpc` | Estimated cost-per-click for the keyword. Reflects keyword commercial value and often correlates with intent and monetization. |
| `main_intent` | The main search intent behind the page, such as `transactional` or `informational`. Useful as a categorical context signal. |
| `backlinks` | Estimated number of backlinks pointing to the content or URL. A proxy for authority or link support. |
| `category_count` | Number of topical categories associated with the content. A coarse topic coverage signal. |
| `keyword_created_date` | Date the keyword record was created. Can help with query maturity or historical context. |
| `provider_used` | LLM provider used to generate the content (for example, `gemini-generate-content`). Not a model feature; it is metadata about generation. |
| `model_used` | LLM model used for generation (for example, `gemini-3-flash-preview`). A metadata field, not a predictive feature. |
| `char_count` | Total character count of the content body. Useful to capture article length. |
| `word_count` | Total word count of the content body. Common length signal for quality, depth, and readability. |
| `last_optimized_date` | Most recent optimization date, if the content has been optimized. Missing values indicate no recorded optimization. |
| `optimization_eligible_date` | Date when the content became eligible for optimization. Used for optimization timing and recency analysis. |
| `is_published` | Boolean flag indicating whether the content is currently published. |
| `is_deleted` | Boolean flag indicating whether the content has been removed or deleted. |

## fact_content_daily_performance

| Feature | Description |
|---|---|
| `report_date` | The daily reporting date for the row. This table is organized by day, client, and content. |
| `client_hash_id` | Pseudonymous client ID linking the row to the client record. |
| `content_hash_id` | Pseudonymous content ID linking the row to the page record. |
| `client_has_gsc` | Whether the client has GSC access in the reporting context. |
| `client_has_ga4` | Whether the client has GA4 access in the reporting context. |
| `gsc_data_available` | ⚠️ **Three-valued flag** (`TRUE`, `FALSE`, or `NULL`) indicating whether GSC data is available for the row. **Critical:** Use `IS TRUE`/`IS NOT TRUE` in SQL filters — never `= FALSE` or `NOT`, as these will miss NULL values. If `FALSE` or `NULL`, GSC metrics may reflect missing coverage rather than true zero traffic. **Note:** Millions of rows carry NULL values, and 10 of 104 clients have NULL access flags in `dim_clients` — making strict flag handling essential. |
| `ga4_data_available` | ⚠️ **Three-valued flag** (`TRUE`, `FALSE`, or `NULL`) indicating whether GA4 data is available for the row. **Critical:** Use `IS TRUE`/`IS NOT TRUE` in SQL filters — never `= FALSE` or `NOT`, as these will miss NULL values. If `FALSE` or `NULL`, GA4 metrics may reflect missing coverage rather than true zero engagement. **Note:** Millions of rows carry NULL values, and 10 of 104 clients have NULL access flags in `dim_clients` — making strict flag handling essential. |
| `gsc_impressions` | Search impressions captured in GSC for that day and content item. |
| `gsc_clicks` | Search clicks captured in GSC for that day and content item. |
| `gsc_sum_position` | Sum of GSC positions observed during the day. Used to derive average position. |
| `gsc_avg_position` | Average search position for the content on that date. Lower is better. A `NaN` or zero-like missing value often indicates no position data available. |
| `ga4_pageviews` | Daily pageviews from GA4 for the content page. |
| `ga4_sessions` | Daily GA4 sessions. |
| `ga4_users` | Daily unique GA4 users. |
| `ga4_engaged_sessions` | Daily engaged sessions, used for engagement-rate calculations. |
| `ga4_total_engagement_sec` | Total engagement time in seconds from GA4 for the page on that day. |
| `sessions_organic` | Sessions from organic search traffic. |
| `sessions_direct` | Sessions from direct traffic. |
| `sessions_referral` | Sessions from referral traffic. |
| `sessions_social` | Sessions from social traffic. |
| `sessions_paid` | Sessions from paid traffic. |
| `sessions_ai` | Sessions attributed to AI referral or assistant traffic. |
| `ai_chatgpt` | AI traffic specifically attributed to ChatGPT. |
| `ai_perplexity` | AI traffic specifically attributed to Perplexity. |
| `ai_gemini` | AI traffic specifically attributed to Gemini. |
| `ai_copilot` | AI traffic specifically attributed to Copilot. |
| `ai_claude` | AI traffic specifically attributed to Claude. |
| `ai_meta` | AI traffic attributed to Meta/other AI sources in the grouped bucket. |
| `ai_other` | Remaining AI traffic not captured by the named AI sources. |
| `scroll_events` | Daily page scroll events captured by GA4. Useful for scroll-depth or engagement proxies. |
| `month` | Month string (for example, `2026-06`) used to partition time-series data and make time filtering easy. |

## fact_content_query_90d

| Feature | Description |
|---|---|
| `client_hash_id` | Pseudonymous client ID for the content's owner. |
| `content_hash_id` | Pseudonymous content ID for the page being analyzed. |
| `query_hash_id` | Pseudonymous query identifier. Each row represents one content item and one query hash over a fixed 90-day window (the most recent ~3 months of the snapshot), for queries that drove at least 1 impression. |
| `query_char_count` | Number of characters in the query string. A light proxy for query complexity. |
| `query_token_count` | Number of tokens or words in the query string. Useful for query specificity analysis. |
| `window_start` | Start date of the fixed 90-day query window. |
| `window_end` | End date of the fixed 90-day query window. |
| `impressions_90d` | Total impressions attributed to the query over the 90-day window. ⚠️ **Can cause label leakage** — only use if your label period is before this window. |
| `clicks_90d` | Total clicks attributed to the query over the 90-day window. ⚠️ **Same leakage warning as `impressions_90d`.** |
| `impressions_last30` | Impressions in the most recent 30-day slice of the query window. ⚠️ **Likely contains your label period** — avoid as a feature for prediction. |
| `clicks_last30` | Clicks in the most recent 30-day slice of the query window. ⚠️ **Same leakage warning as `impressions_last30`.** |
| `impressions_prev30` | Impressions in the previous 30-day slice of the query window. ✅ **Safe for features** — this period is before the label period. |
| `clicks_prev30` | Clicks in the previous 30-day slice of the query window. ✅ **Safe for features.** |
| `avg_position_90d` | Average ranking position for the query over the 90-day window. Lower is better. ⚠️ **Leakage warning applies.** |
| `avg_position_last30` | Average position in the most recent 30-day period. Useful for short-term ranking trend analysis. ⚠️ **Same leakage warning.** |
| `avg_position_prev30` | Average position in the previous 30-day period. Provides a baseline for trend comparison. ✅ **Safe for features.** |
| `content_total_impressions_90d` | Total impressions for the content item over the 90-day window, used as the denominator in query-share analysis. Matches daily fact for ~98.5%. The remaining ~1.5% are items registered mid-window — daily fact only has history from registration day, query table uses current URL map  **⚠️ IMPORTANT:** Treat this as the query table's own denominator. The per-content context columns repeat on every row of that content item — use `ANY_VALUE()` or `MAX()` for context columns, never `SUM()` them. |
| `content_visible_query_count` | Number of visible or distinct queries associated with the content over the window. |
| `rare_query_count` | Count of rare or low-frequency queries in the content's query mix. Useful for concentration and tail analysis. |
| `rare_impressions_share` | Share of impressions coming from rare queries (queries with 1–9 impressions). Stored as a decimal (0–1). Helps quantify how concentrated or diversified the content's query mix is. **Note:** Kept rows (≥ 10 impressions) + `rare_impressions_share` + `anonymized_impressions_share` account for exactly 100% of `content_total_impressions_90d`. |
| `anonymized_impressions_share` | Share of impressions attributable to anonymized or protected query buckets. Stored as a decimal (0–1). This helps explain how much of the content's visibility comes from less interpretable query segments. **Note:** Kept rows (≥ 10 impressions) + `rare_impressions_share` + `anonymized_impressions_share` account for exactly 100% of `content_total_impressions_90d`. |

## Notes on usage

- The raw tables are not all model-ready features; some fields exist for segmentation, time-window validation, or label construction.
- `gsc_data_available` and `ga4_data_available` are **three-valued flags** (`TRUE`, `FALSE`, or `NULL`). Zero values before a client's data-start date do not mean "no traffic"; they often mean "not available yet." **Always filter using `IS TRUE`/`IS NOT TRUE` — never `= FALSE` or `NOT`**, as these will miss NULL rows. This is especially critical because millions of rows carry NULL values and 10 of 104 clients have NULL access flags in `dim_clients`.
- **Rate columns in the warehouse tables are stored as decimals (0–1), not as percentages.** This applies to columns like `competition`, `rare_impressions_share`, and `anonymized_impressions_share`. The ×100 percentage convention applies only to the starter CSV dictionary, not the warehouse tables.
- Fields like `query_hash_id`, `client_hash_id`, and `content_hash_id` are identifiers and should be used for joins and grouped validation, not as direct input signals to machine learning models.
- **Missingness in keyword-context columns is systematic, not random** — it follows `content_type` patterns. Always check missingness per `content_type` before imputing.

### Building safe features from the query table
```sql
-- Aggregate per content item using ONLY the safe columns
SELECT 
    content_hash_id,
    SUM(impressions_prev30) as impressions_prev30_total,
    AVG(avg_position_prev30) as avg_position_prev30_avg,
    COUNT(DISTINCT query_hash_id) as query_count_prev30
FROM fact_content_query_90d
GROUP BY content_hash_id
-- Do NOT include impressions_last30 or impressions_90d if your label is in that period.
-- The query table's fixed 90-day window is the most recent ~3 months of the snapshot. If your label is "will this page decline next month?" and that month is within this window, impressions_90d, impressions_last30, and related fields contain your label period — using them is leakage.
-- IMPORTANT: Use ANY_VALUE() or MAX() for context columns (client_hash_id, etc.) when selecting them
```

### Client-holdout splits (avoiding client-level leakage)
```python
# Group by client, not by row
clients = df['client_hash_id'].unique()
train_clients, test_clients = train_test_split(clients, test_size=0.2, random_state=42)
train = df[df['client_hash_id'].isin(train_clients)]
test = df[df['client_hash_id'].isin(test_clients)]
```

### Model feature definitions
The definitive list of which columns are used as model features is defined in one place: `MODEL_NUMERIC_FEATURES` and `MODEL_CATEGORICAL_FEATURES` in `scripts/ml_utils.py`. Always refer to this source when building models rather than deriving features from the data dictionary.

---

## Validation Checklist

Before building any model:

- [ ] Did I filter GSC/GA4 flags with `IS TRUE` / `IS NOT TRUE` (not `= FALSE`)?
- [ ] Did I use per-client start dates from `dim_clients` (not a global window)?
- [ ] Did I exclude `provider_used` and `model_used` from features?
- [ ] Did I check missingness patterns by `content_type` before imputing?
- [ ] Did I verify my feature columns don't overlap with my label period?
- [ ] Did I use client-holdout splits (not random row splits)?
- [ ] Did I confirm rate columns are being treated as decimals (0–1), not percentages?
- [ ] Did I use `ANY_VALUE()` or `MAX()` for context columns when aggregating query table data?
- [ ] Did I reference `MODEL_NUMERIC_FEATURES`/`MODEL_CATEGORICAL_FEATURES` for the definitive feature list?
- [ ] Did I confirm the label period does not overlap with the query table's 90-day window?
