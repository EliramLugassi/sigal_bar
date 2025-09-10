"""Parse scanned receipts using OpenAI."""
import openai
import base64
from PIL import Image
import io
from dotenv import load_dotenv
import os
import re
from datetime import datetime
import json
from PyPDF2 import PdfReader
from openai import OpenAI
from pdf2image import convert_from_path

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(path):
    """Extract raw text from the first page of a PDF."""
    reader = PdfReader(path)
    text = ""
    for page in reader.pages[:1]:  # Use first page (or more)
        text += page.extract_text() or ""
    return text.strip()

def extract_receipt_data_via_chatgpt(file_path):
    """
    Sends a scanned receipt to OpenAI GPT-4-Vision and parses structured data from it.
    Expected output includes:
      - receipt_id
      - total_cost
      - start_date
      - end_date
      - expense_type
      - notes
    """

    # Read and encode image file as base64
    with open(file_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert assistant that extracts data from scanned receipts. "
                        "Always return a JSON object with the following fields: "
                        "`receipt_id`, `total_cost`, `start_date`, `end_date`, `expense_type`, and `notes`. "
                        "If a field is missing in the image, return null or an empty string."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract the following fields from this receipt image and return them in JSON format:\n\n"
                                "- receipt_id: A unique number or alphanumeric code if available.\n"
                                "- total_cost: The total amount paid (in numbers only).\n"
                                "- start_date: The starting date of the service or contract, if present.\n"
                                "- end_date: The ending date of the service or contract, if present.\n"
                                "- expense_type: What kind of expense is it? (e.g. cleaning, repairs, electricity).\n"
                                "- notes: Any extra details like frequency, context, or service period."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded_image}"}
                        }
                    ]
                }
            ],
            max_tokens=500
        )

        # Parse the JSON-like response (assumes GPT returns it properly formatted)
        content = response.choices[0].message['content']

        import json
        parsed_data = json.loads(content)
        return parsed_data

    except Exception as e:
        print("Error during OpenAI API call:", e)
        return None


def parse_extracted_text_to_dict(text):
    """
    Parses a GPT-generated text response to extract structured receipt fields.
    Expected fields:
        - receipt_id
        - total_cost
        - start_date
        - end_date
        - expense_type
        - notes
    """
    def extract_date(line):
        try:
            return datetime.strptime(line.strip(), "%Y-%m-%d").date()
        except:
            match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", line)
            if match:
                try:
                    return datetime.strptime(match.group(1), "%d/%m/%Y").date()
                except:
                    try:
                        return datetime.strptime(match.group(1), "%m/%d/%Y").date()
                    except:
                        pass
        return None

    data = {
        "receipt_id": None,
        "total_cost": 0.0,
        "start_date": None,
        "end_date": None,
        "expense_type": None,
        "notes": ""
    }

    lines = text.splitlines()
    for line in lines:
        l = line.lower()

        if "receipt" in l or "invoice" in l:
            match = re.search(r'#?(\w+[-]?\w+)', line)
            if match:
                data["receipt_id"] = match.group(1)

        if "total" in l:
            match = re.search(r'₪?\s?([\d,.]+)', line)
            if match:
                data["total_cost"] = float(match.group(1).replace(",", ""))

        if "start date" in l:
            date_val = extract_date(line)
            if date_val:
                data["start_date"] = date_val

        if "end date" in l:
            date_val = extract_date(line)
            if date_val:
                data["end_date"] = date_val

        if "type" in l or "category" in l:
            data["expense_type"] = line.split(":")[-1].strip()

        # Fallback to general notes
        if not any(keyword in l for keyword in ["receipt", "total", "date", "type", "category"]):
            data["notes"] += line.strip() + " "

    return data


def send_receipt_url_to_chatgpt(public_url):
    """Send an image URL to OpenAI and return parsed receipt data."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant that extracts receipt data. "
                    "Return a JSON object with: receipt_id, total_cost, start_date, end_date, expense_type, and notes."
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the data from the receipt image:"},
                    {"type": "image_url", "image_url": {"url": public_url}}
                ]
            }
        ],
        max_tokens=500
    )

    return json.loads(response.choices[0].message.content)
def send_pdf_text_to_gpt(text):
    """Send OCR text to OpenAI and return structured data."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant that extracts structured data from receipts. "
                    "Always respond with **valid JSON only**, including these fields:\n"
                    "`receipt_id`, `total_cost`, `start_date`, `end_date`, `expense_type`, `notes`.\n"
                    "If a field is missing, use null or an empty string."
                )
            },
            {
                "role": "user",
                "content": text.strip()
            }
        ]
    )

    content = response.choices[0].message.content.strip()

    import json
    return json.loads(content)

# Inside receipt_parser.py


def convert_file_to_gpt_image(file_path):
    """Convert PDF or image to a JPEG suitable for GPT vision."""
    ext = os.path.splitext(file_path)[-1].lower()

    if ext == ".pdf":
        images = convert_from_path(file_path, first_page=1, last_page=1)
        image = images[0]
    else:
        image = Image.open(file_path).convert("RGB")

    output_path = os.path.splitext(file_path)[0] + "_converted.jpeg"
    image.save(output_path, format="JPEG")
    return output_path
