INTENT_PROMPT = """\
You are an intent classifier for a multi-modal agent. Classify the user's request.

User query: "{query}"
Extracted file content (first 600 chars): "{content_preview}"
File type detected: "{file_type}"

Recent Chat History:
{history_context}

Return valid JSON:
{{
  "intent": "<one of: summarize | sentiment | code_explain | youtube_transcript | image_pdf_extract | audio_transcribe | rag_qa | conversational | unclear>",
  "confidence": <float 0.0 to 1.0>,
  "needs_clarification": <true or false>,
  "clarification_question": "<short question string, or null>",
  "reasoning": "<one sentence>"
}}
"""

OCR_PROMPT = """\
Transcribe all text found in the provided image/document.

Return your response as a valid JSON object matching the following structure:
{{
  "extracted_text": "<exact, complete transcription of all text in the image/document>",
  "answer": "<your response to the user's question, or null if no question was provided>"
}}
"""

RAG_PROMPT = """\
You are an assistant. Answer the user's question based ONLY on the provided document text. 
Do not use outside knowledge. If the answer is not in the text, say so.
Format your answer with Markdown.

Document Text:
{text}

User Question: {query}"""

CODE_EXPLAIN_PROMPT = """\
Analyze the code below. Return valid JSON only.

{{
  "language": "<detected programming language>",
  "explanation": "<2-3 sentences explaining what this code does in plain English>",
  "bugs": ["<bug or issue description>"],
  "has_bugs": true or false,
  "time_complexity": "<Big-O notation + one-line justification>",
  "space_complexity": "<Big-O notation>"
}}

If no bugs found, return an empty list for bugs and false for has_bugs.

CODE:
{code}
"""

CONVERSATIONAL_PROMPT = """\
You are a helpful assistant.
Answer the user's question concisely and clearly, keeping in mind the recent conversation history.

Recent Conversation:
{history_context}

User's Current Question: {source}
"""

SENTIMENT_PROMPT = """\
Analyze the sentiment of the text below. Return valid JSON only.

{{
  "label": "Positive" or "Negative" or "Neutral" or "Mixed",
  "confidence": <float between 0.0 and 1.0>,
  "justification": "<one sentence explaining the key signal that determined the sentiment>"
}}

TEXT:
{text}
"""

SUMMARIZE_PROMPT = """\
Summarize the following text using EXACTLY this structure.

ONE-LINE SUMMARY:
[Single sentence, max 20 words, capturing the core idea]

KEY POINTS:
• [Point 1]
• [Point 2]
• [Point 3]

DETAILED SUMMARY:
[Exactly 5 sentences. Be specific.]

---
TEXT TO SUMMARIZE:
{text}
"""
