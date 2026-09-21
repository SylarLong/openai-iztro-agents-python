# /v2 streaming timing — iztro tools fire BEFORE the answer (dev)

Backend: `https://api-dev.ziwei.guru` · question: 看看我2026年的事业。生日1995-02-23，17点，女。

## Event order (t = seconds from run start)

- ` 17.06s`  **FIRST_TEXT_DELTA**  
- ` 17.08s`  **on_iztro_tools**  ['iztro-mingpan']
- ` 75.73s`  **on_iztro_tools**  ['iztro-daxian 27']
- ` 75.73s`  **on_iztro_tools**  ['iztro-liunian 2026']

- text delta chunks: 1113  (>1 ⇒ real token streaming)
- agent.model.last_iztro_tools: ['iztro-mingpan', 'iztro-daxian 27', 'iztro-liunian 2026']
- final_output head: 好的，我先为您排盘，获取命盘信息，再结合大限和流年分析2026年的事业运势。已为您排好盘！接下来我看一下您的当前大限和2026年流年事业运势。

您1995年出

**✅ all tools fired before first text delta: False**
