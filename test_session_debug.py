"""
Test script with explicit session cookie debug
"""
import json
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8083/api/upload"

# Use a session to maintain cookies
s = requests.Session()

print("\n========== INITIAL GET /staged ==========")
response = s.get(f"{BASE_URL}/staged")
print(f"Status: {response.status_code}")
print(f"Cookies after GET: {s.cookies.get_dict()}")
print(f"Response: {response.json()}")

print("\n========== POST /stage (upload file) ==========")
# Create test PDF
test_pdf = Path("test.pdf")
pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000056 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
203
%%EOF"""
test_pdf.write_bytes(pdf_content)

files = {'files[]': ('test.pdf', open(test_pdf, 'rb'), 'application/pdf')}
response = s.post(f"{BASE_URL}/stage", files=files)
print(f"Status: {response.status_code}")
print(f"Cookies after POST: {s.cookies.get_dict()}")
result = response.json()
print(f"Session ID from response: {result.get('session_id')}")
print(f"Files uploaded: {len(result.get('files', []))}")

print("\n========== SECOND GET /staged ==========")
response = s.get(f"{BASE_URL}/staged")
print(f"Status: {response.status_code}")
print(f"Cookies: {s.cookies.get_dict()}")
result = response.json()
print(f"Files in response: {len(result.get('files', []))}")
print(f"Response: {json.dumps(result, indent=2)}")

# Cleanup
test_pdf.unlink()
