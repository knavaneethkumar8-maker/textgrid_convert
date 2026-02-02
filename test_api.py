import requests
import json
import os
from pathlib import Path

def test_api():
    """Test the Flask API with various curl commands"""
    
    base_url = "http://localhost:5000"
    
    print("=" * 60)
    print("Testing TextGrid to JSON Converter API")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n1. Testing health check endpoint:")
    print(f"curl -X GET {base_url}/health")
    response = requests.get(f"{base_url}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 2: Get API info
    print("\n2. Testing API info endpoint:")
    print(f"curl -X GET {base_url}/")
    response = requests.get(f"{base_url}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    # Test 3: Convert file upload
    print("\n3. Testing file upload conversion:")
    
    # Check if we have a test TextGrid file
    test_file = "/Volumes/akshar_data/demo/data/chunk_0/chunk_0.TextGrid"
    if os.path.exists(test_file):
        print(f"curl -X POST -F 'file=@\"{test_file}\"' {base_url}/convert")
        
        with open(test_file, 'rb') as f:
            files = {'file': (os.path.basename(test_file), f, 'text/plain')}
            data = {'audio_id': 'test_audio_001'}
            response = requests.post(f"{base_url}/convert", files=files, data=data)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Generated JSON with {len(result.get('grids', []))} grids")
            
            # Save the result to a file
            output_file = "converted_output.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Saved result to: {output_file}")
        else:
            print(f"Error: {response.json()}")
    else:
        print(f"Test file not found: {test_file}")
        print("Skipping file upload test.")
    
    # Test 4: Local conversion (debug endpoint)
    print("\n4. Testing local file conversion (debug):")
    if os.path.exists(test_file):
        print(f"curl -X POST -H 'Content-Type: application/json' -d '{{\"filepath\": \"{test_file}\", \"audio_id\": \"debug_test\"}}' {base_url}/convert/local")
        
        payload = {
            "filepath": test_file,
            "audio_id": "debug_test"
        }
        response = requests.post(f"{base_url}/convert/local", json=payload)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Generated JSON with {len(result.get('grids', []))} grids")
        else:
            print(f"Error: {response.json()}")
    else:
        print("Skipping local conversion test.")
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)

if __name__ == "__main__":
    # Make sure the Flask app is running on localhost:5000 before running tests
    test_api()
