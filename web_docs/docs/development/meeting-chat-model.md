---
title: Meeting chat model
description: Which model answers the meeting chat, how to change it, and what it costs (#848).
---

# Meeting chat model (#848)

The meeting chat (`POST /api/chat/meetings`, #630) makes one model call per question: it finds up to five analysed
meetings, or one meeting's transcript passages, and asks the model to answer from them.

## Which model

Claude Haiku 5.5 (`claude-haiku-5-5`) by default, through the official `anthropic` SDK
(`packages/llm/src/llm/claude/text_client.py`). Before #848 the call went to Gemini Flash-Lite.

| Setting | Values | Default |
|---|---|---|
| `CHAT_PROVIDER` | `anthropic` or `gemini` | `anthropic` |
| `CHAT_MODEL` | a model id of the chosen provider | `claude-haiku-5-5`, or the Flash-Lite default for `gemini` |
| `ANTHROPIC_API_KEY` | the Anthropic key; read by the SDK, never logged | none |

Set them in `.env` and restart the API. To go back to Gemini, set `CHAT_PROVIDER=gemini`; that path is unchanged and
needs a Gemini key with credit.

## How the call is made

- One system prompt and one user message. No tools, no conversation history.
- Thinking is left at the model's default and kept shallow with `output_config.effort = "low"`. No `temperature` is
  sent: current Claude models reject non-default sampling settings.
- `max_tokens` is 2,048. Output tokens include the model's thinking tokens, because that is how they are billed.
- If the model declines (`stop_reason` is `refusal`) the chat returns its usual 502 "answer service is temporarily
  unavailable". A refusal is never shown as an answer.

## Cost

`usage.estimated_usd` in the response is the token counts multiplied by the price in
`packages/llm/src/llm/usage/prices.yaml`: 0.10 USD per million input tokens and 0.50 USD per million output tokens,
read from Anthropic's pricing page on November 24, 2026. Those are the rates for prompts up to 100,000 tokens; the chat
caps its prompt far below that (`CHAT_PASSAGE_CHAR_CAP`). A model with no price in that file gives `null`, not a guess,
and then adds nothing to the daily total.

`CHAT_DAILY_SPEND_CAP_USD` (default 1.00) still stops the chat for the day once the estimates add up to it.

## When it fails

The API log line `chat model call failed (<error type>): …` names the cause:

| Error type | Meaning | Fix |
|---|---|---|
| `AuthenticationError`, or a message about a missing key | `ANTHROPIC_API_KEY` is absent or wrong | set it in `.env`, restart |
| `RateLimitError` | the account's rate limit | wait, or raise the limit |
| `NotFoundError` | `CHAT_MODEL` is not a model the key can use | correct the id |
| `ClaudeRefusalError` | the model declined the question | nothing to fix |

### Telling "not set up" from "the model failed" (#916)

After a deploy on November 24, 2026 the live chat failed for every question that found meetings, and the page said only
"Something went wrong". Three things now make the cause visible:

- **`GET /api/chat/status`** returns `{ "provider", "model", "configured" }`. `configured` is false when the provider's
  key variable is not set. It holds no secret.
- **Before any model call**, a missing key answers **503** with "Chat is not set up on this site yet." and logs one error
  line naming the provider and the missing variable (`ANTHROPIC_API_KEY` or `GEMINI_API_KEY`), never a value. A question
  that finds no meetings still answers normally, because it needs no model.
- **A model call that fails** still answers 502, and the log line gives the provider, model, exception type and status code.

The page shows the server's own reason for a failed request (`web_app/src/utils/chatError.ts`), with separate wording
for a request that timed out after a minute and for no connection, and points to "Contact us" at the top of the panel.

## Chat and Contact are one header item (#860)

The site header has a single "Chat & Contact" item that opens `/chat`. The top of the chat panel says the chat
answers from meeting records and offers a "Contact us" email link for reaching a person. The link's address is
`CONTACT_EMAIL` in `web_app/src/utils/contact.ts`, which the older `/support` page also uses; that page stays for
existing links.

## Closing the chat (#879)

The panel's top strip has a close button, and Escape closes it too unless a message is being typed. Closing goes back
to the page the visitor came from, or to the home page when the chat was the first page opened
(`closeChatTarget` in `web_app/src/utils/contact.ts`).
