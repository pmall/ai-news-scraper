SCORING_PROMPT_TEMPLATE = """
You are an AI expert tasked with scoring articles based on their relevance to artificial intelligence.

Score each article from 0-100 based on how relevant it is to artificial intelligence, machine learning, LLMs, neural networks, AI research, AI applications, or AI industry developments.

Scoring guidelines:
- 90-100: Core AI/ML content (new models, AI research breakthroughs, AI company developments)
- 70-89: AI applications, AI tools, AI industry news
- 50-69: Technology with significant AI components
- 30-49: Technology that mentions AI but isn't primarily about it
- 10-29: Brief AI mentions in broader context
- 0-9: No meaningful AI relevance

Return ONLY a JSON array with scores in the same order as the articles below:

$articles

Respond with exactly $n scores as a JSON array: [score1, score2, ...]
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
