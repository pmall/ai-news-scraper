"""
Prompt templates for AI analysis and summarization
"""

SCORING_PROMPT_TEMPLATE = """
You are an **AI expert** tasked with **analyzing articles** for relevance to artificial intelligence, **categorizing them**, and **extracting relevant tags**.

For each article, provide:
1. A **relevance score** (0–100)  
2. A **category** (1–6)  
3. A **list of relevant tags**

---

**SCORING GUIDELINES (0–100):**
- **90–100**: Core AI/ML content (new models, AI research breakthroughs, AI company developments)  
- **70–89**: AI applications, AI tools, AI industry news  
- **50–69**: Technology with significant AI components  
- **30–49**: Technology that mentions AI but isn't primarily about it  
- **10–29**: Brief AI mentions in broader context  
- **0–9**: No meaningful AI relevance  

---

**CATEGORIES (1–6):**
1. **New Models & Releases** (new AI models, model updates, version releases)  
2. **Research & Breakthroughs** (scientific papers, research findings, technical advances)  
3. **Industry News** (company announcements, funding, partnerships, business developments)  
4. **Tools & Applications** (new AI tools, software, practical applications)  
5. **Policy & Regulation** (government actions, regulations, policy discussions)  
6. **Unrelated** (does not fit meaningfully in categories 1–5, or has very low AI relevance)  

---

**TAGS GUIDELINES:**
- Extract **3–8 relevant tags** per article  
- Include **company names, model names, technology types, application domains**  
- Use **consistent naming** (e.g., `"GPT-4"`, `"OpenAI"`, `"natural-language-processing"`, `"computer-vision"`)  
- Keep tags **concise and lowercase** with **hyphens for multi-word tags**  
- Focus on **AI/ML-specific terms and key entities**

---

Return **ONLY a JSON array** with objects containing `score`, `category`, and `tags` for each article **in the same order**:

$articles

Respond with **exactly $n objects** as a JSON array:
```json
[
  {"score": 85, "category": 1, "tags": ["openai", "gpt-4", "language-model", "api"]},
  {"score": 92, "category": 2, "tags": ["deepmind", "alphafold", "protein-folding", "research"]},
  ...
]
```
""".strip()


SUMMARY_PROMPT_TEMPLATE = """
You are an expert AI news editor. Your task is to generate a **concise and structured list** of AI news headlines based on the input data below.

**Instructions:**

- Output a **JSON array of strings**. Each string is a **headline-style summary of one or more related news articles**.
- Write each string as a **single flowing sentence** using a **natural, journalistic tone**.
- You **must integrate the link naturally** within the sentence using **Markdown syntax**. The linked text should be a **core part of the sentence**, never added at the end.
- **Do not repeat** the same name/title twice in one sentence.
- You **can group multiple articles** into a single summary if they are clearly related.
- **Order the items by importance**, putting the most significant news first.
- **Never output more than 10 items**.
- **Keep the total word count under 600 words.**

**Examples (good format + good link integration):**
```json
[
  "OpenAI introduced [GPT-4 Turbo](url), offering faster performance and lower cost for developers",
  "Stanford researchers released the [Constitutional AI paper](url) advancing alignment techniques",
  "Anthropic's [Claude 3.5 Sonnet](url) shows improved code generation and reasoning"
]
```

**Examples (bad link integration — avoid these):**
```json
[
  "OpenAI released GPT-4 Turbo. [GPT-4 Turbo](url)",
  "New AI model announced. [link](url)"
]
```

Now summarize the following news items:

$content
""".strip()


SUMMARY_PROMPT_TEMPLATE_EN = f"""
OUTPUT IN ENGLISH LANGUAGE

{SUMMARY_PROMPT_TEMPLATE}
""".strip()


SUMMARY_PROMPT_TEMPLATE_FR = f"""
OUTPUT IN FRENCH LANGUAGE

{SUMMARY_PROMPT_TEMPLATE}
""".strip()
