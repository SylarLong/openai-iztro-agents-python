# Prod timeout diagnostic

Endpoint: `https://chat-api.iztro.com`


## A. Auth check (light prompt)

- **light call**: ✅ ok in **3.2s**, 30 chars

## B. Single heavy 流年 call (timed)

- **heavy #1**: ✅ ok in **225.8s**, 2507 chars

## C. Two heavy calls back-to-back on one agent (connection-reuse test)

- **reuse call #1**: ✅ ok in **74.3s**, 2590 chars
- **reuse call #2**: ❌ **InternalServerError** after **294.9s** — Error code: 500 - {'detail': 'Internal server error: OperationalError'}
  <details><summary>trace</summary>

```
openai.InternalServerError: Error code: 500 - {'detail': 'Internal server error: OperationalError'}
```
  </details>

---
_done._
