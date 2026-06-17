---
inclusion: manual
description: "How to fetch content from docs.cradlepoint.com (FluidTopics SPA)"
---
# Cradlepoint Docs Portal API

The docs.cradlepoint.com portal is a FluidTopics SPA. Every URL (including `/r/{slug}`) returns the same ~3.7 KB HTML shell. Plain curl on a page URL won't return article text. Use the internal APIs instead.

## Required Headers (all requests)

```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Ft-Calling-App: ft/turnkey-portal
Ft-Calling-App-Version: 5.3.0
Ft-Origin-Type: internal
```

Plus `Accept: application/json` for search/topics, `Accept: text/html` for content.

## Step 1: Search for an article

```bash
/usr/bin/curl -sL --max-time 15 \
  'https://docs.cradlepoint.com/internal/api/webapp/search' \
  -H 'Ft-Calling-App-Version: 5.3.0' \
  -H 'X-HTTP-Method-Override: POST' \
  -H 'Ft-Calling-App: ft/turnkey-portal' \
  -H 'Ft-Origin-Type: internal' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Referer: https://docs.cradlepoint.com/search/all?query=test&content-lang=en-US' \
  --data-raw '{"query":"YOUR SEARCH TERM","metadataFilters":[],"priors":[],"page":1,"limit":10,"sortId":"relevance","contentLocale":"en-US","virtualField":"EVERYWHERE","keywordMatch":null}'
```

**Response**: JSON at `data.results.retrievedResults[]`. Each hit has:
- `variants[0].map.id` → the **mapId** (needed for Steps 2–3)
- `variants[0].map.title` → article title
- Inside `allMetadata`, a `resource` key → the article slug (e.g., `NCOS-Configuration-of-Failover-and-Failback`)

User-facing URL: `https://docs.cradlepoint.com/r/{slug}`

## Step 2: Get the topic list for an article

```bash
/usr/bin/curl -sL --max-time 15 \
  'https://docs.cradlepoint.com/api/khub/maps/{mapId}/topics' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' \
  -H 'Accept: application/json' \
  -H 'Ft-Calling-App: ft/turnkey-portal' \
  -H 'Ft-Calling-App-Version: 5.3.0' \
  -H 'Ft-Origin-Type: internal'
```

**Response**: JSON array of topics. Each has:
- `id` → the **topicId**
- `title` → section heading

## Step 3: Get the actual content

```bash
/usr/bin/curl -sL --max-time 15 \
  'https://docs.cradlepoint.com/api/khub/maps/{mapId}/topics/{topicId}/content' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' \
  -H 'Accept: text/html' \
  -H 'Ft-Calling-App: ft/turnkey-portal' \
  -H 'Ft-Calling-App-Version: 5.3.0' \
  -H 'Ft-Origin-Type: internal'
```

**Response**: Full HTML body of that section.

## Key Gotchas

- The slug is NOT guessable — always resolve via the search API first
- You cannot just curl `https://docs.cradlepoint.com/r/some-slug` — returns empty SPA shell
- Headers are required — without them you get 403 or empty responses
- Step 2 gives all sections — most articles have 1–3 topics; some have many
