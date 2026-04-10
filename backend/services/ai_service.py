"""
AI extraction service - PDF document analysis and timeline extraction.
Extracted from server.py during Phase 3 modularization.
"""
import os
import re
import json
import base64
import logging
import openai
import fitz  # PyMuPDF

from core.monitoring import capture_ai_error

logger = logging.getLogger("evohome.ai")

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')


async def extract_document_from_pdf(pdf_path: str, filename: str) -> dict:
    """Extract document data from PDF using AI (OpenAI GPT-4o with vision)"""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, returning fallback extraction")
        return {
            "title": filename.replace('.pdf', '').replace('_', ' ').title(),
            "amount": None,
            "items": [],
            "supplier_name": None,
            "description": "AI extraction unavailable - please enter details manually",
            "confidence": "low",
            "extraction_failed": True
        }

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        system_prompt = """You are a document extraction assistant for a real estate construction/renovation project management system.

Your task is to extract structured data from quotes, invoices, and other construction-related documents.

EXTRACTION RULES:

1. TOTAL AMOUNT (CRITICAL):
   - Find the FINAL TOTAL at the END of the document
   - This is usually labeled: "Total", "Grand Total", "Total TTC", "Montant Total", "Gesamtbetrag", "Totale"
   - If there are multiple totals (subtotal, tax, grand total), use the GRAND TOTAL
   - Look at the BOTTOM of the document - the final number is what matters
   - Return as a number WITHOUT currency symbols

2. SUMMARY/DESCRIPTION:
   - Write a clean, professional single paragraph (2-4 sentences)
   - Summarize WHAT work/items are covered in this document
   - Include key details: type of work, scope, location if mentioned
   - This will be shown to the client, so be clear and professional

3. LINE ITEMS:
   - Extract individual items with description, quantity, unit price, and line total
   - If items are grouped, extract the group totals
   - If no clear line items, create ONE line item with the document description and total amount

4. SUPPLIER INFO:
   - Extract company name from header/letterhead
   - This is the vendor/contractor providing the quote/invoice

Return ONLY a JSON object with this structure:
{
  "title": "short descriptive title (e.g., 'Bathroom Renovation Quote')",
  "amount": final_total_number_or_null,
  "items": [{"description": "string", "quantity": 1, "unit_price": number, "total": number}],
  "supplier_name": "company name or null",
  "description": "professional single-paragraph summary of the document scope",
  "confidence": "high/medium/low"
}"""

        doc = fitz.open(pdf_path)
        image_contents = []

        for page_num in range(min(5, len(doc))):
            page = doc[page_num]
            mat = fitz.Matrix(200/72, 200/72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}", "detail": "high"}
            })
        doc.close()

        if not image_contents:
            raise ValueError("Could not extract any images from PDF")

        message_content = [
            {
                "type": "text",
                "text": "Extract document information from this PDF (shown as images). Focus on finding the FINAL TOTAL AMOUNT at the end of the document. Write a professional summary. Return only valid JSON."
            }
        ] + image_contents

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_content}
            ],
            max_tokens=4000
        )

        response_text = response.choices[0].message.content
        logger.info(f"AI extraction response: {response_text[:200]}...")

        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            extracted = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found in response")

        result = {
            "title": extracted.get("title") or filename.replace('.pdf', '').replace('_', ' ').title(),
            "amount": extracted.get("amount"),
            "items": extracted.get("items", []),
            "supplier_name": extracted.get("supplier_name"),
            "description": extracted.get("description", ""),
            "confidence": extracted.get("confidence", "medium"),
            "extraction_failed": False
        }

        valid_items = []
        for item in result["items"]:
            if isinstance(item, dict) and item.get("description"):
                valid_items.append({
                    "description": str(item.get("description", "")),
                    "quantity": int(item.get("quantity", 1)),
                    "unit_price": float(item.get("unit_price", 0)),
                    "total": float(item.get("total", item.get("unit_price", 0)))
                })

        if result["amount"] and not valid_items:
            valid_items.append({
                "description": result["description"] or result["title"],
                "quantity": 1,
                "unit_price": float(result["amount"]),
                "total": float(result["amount"])
            })

        result["items"] = valid_items

        logger.info(f"PDF extraction successful: {result.get('title')}, amount: {result.get('amount')}, confidence: {result.get('confidence')}")
        return result

    except Exception as e:
        capture_ai_error(e, operation="pdf_extraction", document_id=filename)
        logger.error(f"PDF extraction failed: {str(e)}")
        error_msg = str(e)
        if '/tmp/' in error_msg or '/app/' in error_msg:
            error_msg = "Could not process document. Please ensure it is a valid PDF."
        return {
            "title": filename.replace('.pdf', '').replace('_', ' ').title() if filename else "Document",
            "amount": None,
            "items": [],
            "supplier_name": None,
            "description": f"Extraction failed: {error_msg[:80]}" if len(error_msg) <= 80 else "Extraction failed. Please enter details manually.",
            "confidence": "low",
            "extraction_failed": True
        }
