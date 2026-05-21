INTENT_PROMPT = """\
You are an intent classifier for a multi-modal agent. Classify the user's request based on the following strict rules:

1. `rag_qa`: ONLY select this intent if the user's query is specifically a question about human nutrition, vitamins, minerals, diet, MyPlate, or other nutritional topics covered in the global nutrition knowledge base. DO NOT use this for questions about a newly uploaded file (e.g. "what is in this document?", "explain this pdf").
2. `summarize`: Select this if the user wants to summarize, explain, or get an overview of a newly uploaded file or block of text (e.g. "what is this document about?", "summarize this PDF").
3. `conversational`: Select this for general queries, greetings, or questions about the newly uploaded document's contents that are not asking for a summary (e.g. "who is the author of this uploaded file?", "explain the requirements listed in the uploaded file").
4. `sentiment`: Select for sentiment analysis.
5. `code_explain`: Select if analyzing/explaining programming code.
6. `youtube_transcript`: Select if a YouTube URL is present and they want information from it.
7. `image_pdf_extract`: Select if they only want to extract raw text/OCR from an uploaded image or PDF without answering questions.
8. `audio_transcribe`: Select for audio transcription.
9. `unclear`: Select if the user's goal is ambiguous.

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

{document_context}

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
