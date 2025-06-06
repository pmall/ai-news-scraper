SCORING_PROMPT_TEMPLATE = """
You are an AI expert tasked with analyzing articles for relevance to artificial intelligence, categorizing them, and extracting relevant tags.

For each article, provide:
1. A relevance score (0-100)
2. A category (1-6)  
3. A list of relevant tags

SCORING GUIDELINES (0-100):
- 90-100: Core AI/ML content (new models, AI research breakthroughs, AI company developments)
- 70-89: AI applications, AI tools, AI industry news
- 50-69: Technology with significant AI components
- 30-49: Technology that mentions AI but isn't primarily about it
- 10-29: Brief AI mentions in broader context
- 0-9: No meaningful AI relevance

CATEGORIES (1-6):
1. New Models & Releases (new AI models, model updates, version releases)
2. Research & Breakthroughs (scientific papers, research findings, technical advances)
3. Industry News (company announcements, funding, partnerships, business developments)
4. Tools & Applications (new AI tools, software, practical applications)
5. Policy & Regulation (government actions, regulations, policy discussions)
6. Unrelated (does not fit meaningfully in categories 1-5, or has very low AI relevance)

TAGS GUIDELINES:
- Extract 3-8 relevant tags per article
- Include company names, model names, technology types, application domains
- Use consistent naming (e.g., "GPT-4", "OpenAI", "natural-language-processing", "computer-vision")
- Keep tags concise and lowercase with hyphens for multi-word tags
- Focus on AI/ML specific terms and key entities

Return ONLY a JSON array with objects containing score, category, and tags for each article in the same order:

$articles

Respond with exactly $n objects as a JSON array:
[
  {"score": 85, "category": 1, "tags": ["openai", "gpt-4", "language-model", "api"]},
  {"score": 92, "category": 2, "tags": ["deepmind", "alphafold", "protein-folding", "research"]},
  ...
]
""".strip()

SUMMARY_PROMPT_TEMPLATE = f"""
Please create a concise summary of the following AI news items organized by categories.

Instructions:
- Organize content into these categories using bullet points (only include categories that have relevant content):
    
### New Models & Releases
(New AI models, model updates, version releases)
    
### Research & Breakthroughs  
(Scientific papers, research findings, technical advances)
    
### Industry News
(Company announcements, funding, partnerships, business developments)
    
### Tools & Applications
(New AI tools, software, practical applications, but skip simple showcases)
    
### Policy & Regulation
(Government actions, regulations, policy discussions)
    
- Write each item as a bullet point with natural news style
- each item must contain the link to the referenced article
- CRITICAL: Integrate links naturally into the sentence flow. The link text should BE PART OF the sentence, not added at the end

Examples of GOOD bullet point integration:
- OpenAI released [GPT-4 Turbo](url) with enhanced context window and reduced pricing
- Researchers at Stanford published [Constitutional AI paper](url) showing improved safety alignment  
- Anthropic's [Claude 3.5 Sonnet](url) demonstrates significant improvements in coding tasks
- Google DeepMind's [Gemini Ultra](url) achieves state-of-the-art performance on mathematical reasoning
- Meta announced [Llama 3.2](url) with improved reasoning capabilities for mobile devices

Examples of BAD formatting (avoid these):
- OpenAI released GPT-4 Turbo with enhanced features. [GPT-4 Turbo](url)
- New research on constitutional AI shows promising results. [Constitutional AI paper](url)

- Each bullet point should be a single flowing sentence with embedded links
- Never repeat the same name/title twice in one sentence  
- Keep it under 600 words total
- Skip categories that don't have relevant content

News items with their URLs:
$content
"""
