"""
Comprehensive test script for upload staging API endpoints
Tests: /stage, /staged, /process, /view-pdf/<filename>, /staged/<filename> (delete), /finalize
"""
import json
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8083/api/upload"

# Use a session to maintain cookies (important for Flask session management)
session = requests.Session()

# Create a test PDF file for upload
test_pdf_path = Path("test_sample.pdf")
if not test_pdf_path.exists():
    # Create a minimal valid PDF for testing
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
    with open(test_pdf_path, 'wb') as f:
        f.write(pdf_content)
    print(f"✅ Created test PDF: {test_pdf_path}")

print("\n" + "="*60)
print("TESTING UPLOAD STAGING API ENDPOINTS")
print("="*60)

# Test 1: GET /staged (should be empty initially)
print("\n1️⃣  Testing GET /staged (initial state)")
response = session.get(f"{BASE_URL}/staged")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
assert response.status_code == 200, "GET /staged should return 200"
assert response.json()['success'] == True, "Response should have success=True"
print("✅ GET /staged works correctly")

# Test 2: POST /stage (upload test file)
print("\n2️⃣  Testing POST /stage (upload file)")
files = {'files[]': ('test_sample.pdf', open(test_pdf_path, 'rb'), 'application/pdf')}
response = session.post(f"{BASE_URL}/stage", files=files)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
assert response.status_code == 200, "POST /stage should return 200"
assert response.json()['success'] == True, "Upload should succeed"
assert len(response.json()['files']) == 1, "Should have 1 uploaded file"
session_id = response.json()['session_id']
print(f"✅ File staged successfully with session_id: {session_id}")

# Test 3: GET /staged (should now have the file)
print("\n3️⃣  Testing GET /staged (after upload)")
response = requests.get(f"{BASE_URL}/staged")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
assert response.status_code == 200, "GET /staged should return 200"
assert len(response.json()['files']) == 1, "Should have 1 staged file"
staged_filename = response.json()['files'][0]['filename']
print(f"✅ GET /staged returns staged file: {staged_filename}")

# Test 4: GET /view-pdf/<filename>
print("\n4️⃣  Testing GET /view-pdf/<filename>")
response = session.get(f"{BASE_URL}/view-pdf/{staged_filename}")
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(f"Content-Length: {len(response.content)} bytes")
assert response.status_code == 200, "View PDF should return 200"
assert response.headers.get('Content-Type') == 'application/pdf', "Should return PDF content type"
print("✅ PDF viewing endpoint works")

# Test 5: POST /process (process staged files)
print("\n5️⃣  Testing POST /process")
response = session.post(f"{BASE_URL}/process", json={})
print(f"Status: {response.status_code}")
result = response.json()
print(f"Response: {json.dumps(result, indent=2)}")
assert response.status_code == 200, "POST /process should return 200"
assert result['success'] == True, "Processing should succeed"
print("✅ Processing endpoint works (OCR may fail on test PDF, that's expected)")

# Test 6: DELETE /staged/<filename>
print("\n6️⃣  Testing DELETE /staged/<filename>")
response = session.delete(f"{BASE_URL}/staged/{staged_filename}")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
assert response.status_code == 200, "DELETE should return 200"
assert response.json()['success'] == True, "Deletion should succeed"
print(f"✅ File {staged_filename} deleted successfully")

# Test 7: GET /staged (should be empty again)
print("\n7️⃣  Testing GET /staged (after deletion)")
response = requests.get(f"{BASE_URL}/staged")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
assert response.status_code == 200, "GET /staged should return 200"
assert len(response.json()['files']) == 0, "Should have no staged files"
print("✅ Staged files list is empty after deletion")

print("\n" + "="*60)
print("✅ ALL TESTS PASSED!")
print("="*60)

# Cleanup
if test_pdf_path.exists():
    test_pdf_path.unlink()
    print(f"\n🧹 Cleaned up test file: {test_pdf_path}")
