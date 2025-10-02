import json
import boto3
import uuid
import re
from datetime import datetime
from urllib.parse import unquote_plus

# Initialize AWS clients
s3_client = boto3.client("s3")
textract_client = boto3.client("textract")
dynamodb = boto3.resource("dynamodb")
ses_client = boto3.client("ses")

# DynamoDB table
table = dynamodb.Table("${dynamodb_table}")

def lambda_handler(event, context):
    try:
        # Process each S3 event record
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
            
            # Generate unique receipt ID
            receipt_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            # Get S3 object URL
            receipt_url = f"https://$${bucket}.s3.amazonaws.com/$${key}"
            
            # Extract text using Textract
            extracted_data = extract_receipt_data(bucket, key)
            
            # Store data in DynamoDB
            store_receipt_data(receipt_id, timestamp, receipt_url, extracted_data)
            
            # Send notification email
            send_notification(receipt_id, extracted_data)
            
        return {
            "statusCode": 200,
            "body": json.dumps("Receipt processing completed successfully")
        }
        
    except Exception as e:
        print(f"Error processing receipt: $${str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error: $${str(e)}")
        }

def extract_receipt_data(bucket, key):
    """Extract structured data from receipt using Textract"""
    try:
        response = textract_client.analyze_document(
            Document={
                "S3Object": {
                    "Bucket": bucket,
                    "Name": key
                }
            },
            FeatureTypes=["TABLES", "FORMS"]
        )
        
        # Extract all text lines
        lines = []
        for block in response["Blocks"]:
            if block["BlockType"] == "LINE":
                lines.append(block["Text"].strip())
        
        # Remove empty lines
        lines = [line for line in lines if line]
        
        # Initialize result
        result = {
            "vendor_name": "",
            "date": "",
            "time": "",
            "total_amount": "",
            "subtotal": "",
            "tax_amount": "",
            "address": "",
            "items": [],
            "raw_text": ""
        }
        
        print(f"Extracted lines: $${lines[:10]}")  # Debug: print first 10 lines
        
        # Extract vendor name - look for Starbucks or first meaningful line
        for line in lines[:5]:
            if line and len(line) > 2 and not re.search(r'^[0-9/.-]+$', line):
                result["vendor_name"] = line
                break
        
        # Extract all monetary amounts (including pounds symbol)
        amounts = []
        for i, line in enumerate(lines):
            # Find amounts with pounds, dollars, and decimal patterns
            pound_matches = re.findall(r'£\s*([0-9,]+\.?[0-9]*)', line)
            dollar_matches = re.findall(r'\$\s*([0-9,]+\.?[0-9]*)', line)
            decimal_matches = re.findall(r'([0-9,]+\.[0-9]{2})', line)
            
            for match in pound_matches + dollar_matches + decimal_matches:
                try:
                    clean_amount = match.replace(',', '')
                    amount_value = float(clean_amount)
                    if amount_value > 0:
                        amounts.append({
                            'value': amount_value,
                            'line': line,
                            'line_index': i
                        })
                except:
                    continue
        
        print(f"Found amounts: $${amounts}")  # Debug: print found amounts
        
        # Extract specific fields
        for amount_info in amounts:
            line_lower = amount_info['line'].lower()
            value = amount_info['value']
            
            # Check for total
            if 'total' in line_lower and not result["total_amount"]:
                result["total_amount"] = str(value)
            
            # Check for subtotal
            elif 'subtotal' in line_lower or 'sub total' in line_lower:
                result["subtotal"] = str(value)
            
            # Check for tax
            elif 'tax' in line_lower:
                result["tax_amount"] = str(value)
        
        # If no total found, use the largest amount
        if not result["total_amount"] and amounts:
            largest = max(amounts, key=lambda x: x['value'])
            result["total_amount"] = str(largest['value'])
        
        # Extract date and time for Starbucks receipt format
        for i, line in enumerate(lines):
            # Look for date starting with "Sunday" and ending with "2025"
            if line.startswith('Sunday') and line.endswith('2025'):
                result["date"] = line.strip()
                
                # Look for time in the next line after date
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    time_patterns = [
                        r'\d{1,2}:\d{2}\s*[APap][Mm]',
                        r'\d{1,2}:\d{2}:\d{2}',
                        r'\d{1,2}:\d{2}'
                    ]
                    for pattern in time_patterns:
                        if re.search(pattern, next_line):
                            result["time"] = next_line
                            break
                break
        
        # Fallback date patterns if Sunday format not found
        if not result["date"]:
            for line in lines:
                date_patterns = [
                    r'\d{1,2}/\d{1,2}/\d{4}',
                    r'\d{1,2}-\d{1,2}-\d{4}',
                    r'[A-Za-z]{3}\s+\d{1,2},?\s+\d{4}'
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, line)
                    if match:
                        result["date"] = match.group().strip()
                        break
                if result["date"]:
                    break
        
        # Extract address - line directly under "Starbucks" vendor name
        vendor_found = False
        for i, line in enumerate(lines):
            if 'starbucks' in line.lower():
                result["vendor_name"] = line  # Update vendor name to exact Starbucks line
                # Address is the next line after Starbucks
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Skip if next line looks like a phone number or date
                    if not re.search(r'^\d{3}[-.]?\d{3}[-.]?\d{4}$', next_line) and not re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', next_line):
                        result["address"] = next_line
                vendor_found = True
                break
        
        # Fallback address extraction if Starbucks not found
        if not vendor_found and not result["address"]:
            address_keywords = ['street', 'st', 'ave', 'avenue', 'road', 'rd']
            for line in lines:
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in address_keywords):
                    result["address"] = line.strip()
                    break
        
        # Extract items (lines with amounts that aren't totals)
        items = []
        for amount_info in amounts:
            line = amount_info['line']
            line_lower = line.lower()
            value = amount_info['value']
            
            # Skip if it's a total/tax line
            if any(word in line_lower for word in ['total', 'tax', 'subtotal']):
                continue
            
            # Add as item
            items.append({
                "description": line,
                "amount": str(value)
            })
        
        result["items"] = items
        
        # Create filtered raw text (exclude vendor, date, time, total, address)
        filtered_lines = []
        for line in lines:
            line_lower = line.lower()
            
            # Skip if it's vendor name, date, time, total, or address
            if (line == result["vendor_name"] or
                (result["date"] and result["date"] in line) or
                (result["time"] and result["time"] in line) or
                (result["address"] and line == result["address"]) or
                'total' in line_lower):
                continue
            
            filtered_lines.append(line)
        
        result["raw_text"] = " | ".join(filtered_lines)
        
        print(f"Final result: $${result}")  # Debug: print final result
        
        return result
        
    except Exception as e:
        print(f"Error in extract_receipt_data: $${str(e)}")
        return {
            "vendor_name": "Extraction Error",
            "date": "",
            "total_amount": "",
            "subtotal": "",
            "tax_amount": "",
            "items": [],
            "raw_text": f"Error: $${str(e)}"
        }

def store_receipt_data(receipt_id, timestamp, receipt_url, extracted_data):
    """Store extracted receipt data in DynamoDB"""
    try:
        item = {
            "receipt_id": receipt_id,
            "timestamp": timestamp,
            "receipt_url": receipt_url,
            "vendor_name": extracted_data.get("vendor_name", "Unknown"),
            "date": extracted_data.get("date", ""),
            "time": extracted_data.get("time", ""),
            "total_amount": extracted_data.get("total_amount", ""),
            "subtotal": extracted_data.get("subtotal", ""),
            "tax_amount": extracted_data.get("tax_amount", ""),
            "address": extracted_data.get("address", ""),
            "items": extracted_data.get("items", []),
            "raw_text": extracted_data.get("raw_text", ""),
            "processing_status": "completed"
        }
        
        table.put_item(Item=item)
        print(f"Successfully stored receipt data for ID: $${receipt_id}")
        
    except Exception as e:
        print(f"Error storing data in DynamoDB: $${str(e)}")
        raise

def send_notification(receipt_id, extracted_data):
    """Send email notification about processed receipt"""
    try:
        subject = f"Receipt Processed - ID: $${receipt_id}"
        
        items_summary = ""
        if extracted_data.get("items"):
            items_summary = f"\\nFound $${len(extracted_data['items'])} items"
        
        body = f"""
Receipt Processing Complete!

Receipt ID: $${receipt_id}
Vendor: $${extracted_data.get("vendor_name", "Not found")}
Date: $${extracted_data.get("date", "Not found")}
Time: $${extracted_data.get("time", "Not found")}
Address: $${extracted_data.get("address", "Not found")}
Total: $${extracted_data.get("total_amount", "Not found")}
Subtotal: $${extracted_data.get("subtotal", "N/A")}
Tax: $${extracted_data.get("tax_amount", "N/A")}
$${items_summary}

Filtered raw text: $${extracted_data.get("raw_text", "")[:200]}...

Data stored successfully in database.
        """
        
        ses_client.send_email(
            Source="${ses_email}",
            Destination={"ToAddresses": ["${ses_email}"]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}}
            }
        )
        
        print(f"Notification sent for receipt ID: $${receipt_id}")
        
    except Exception as e:
        print(f"Error sending notification: $${str(e)}")