import asyncio
import os
import httpx
import time

async def main():
    base_url = "http://localhost:8000/api/v1"
    filepath = "../Updated_Crail_idea.docx"
    
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return
        
    print(f"1. Uploading {filepath} to get session ID...")
    async with httpx.AsyncClient() as client:
        with open(filepath, "rb") as f:
            files = {"file": (os.path.basename(filepath), f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            data = {"title": "Test RFP", "client_name": "Test Client"}
            
            response = await client.post(f"{base_url}/rfp/upload", files=files, data=data, timeout=30.0)
            
        if response.status_code != 201:
            print("Failed to upload. Response:", response.text)
            return
            
        session_id = response.json()["id"]
        print(f"Session created with ID: {session_id}")
        
        print("\n2. Triggering analysis...")
        response = await client.post(f"{base_url}/rfp/{session_id}/analyze")
        print("Trigger response:", response.json())
        
        print("\n3. Polling analysis status...")
        start_time = time.time()
        max_wait = 60 # wait up to 60 seconds
        
        while time.time() - start_time < max_wait:
            response = await client.get(f"{base_url}/rfp/{session_id}")
            status = response.json()["status"]
            print(f"Current Status: {status} (elapsed: {int(time.time() - start_time)}s)")
            
            if status == "analyzed":
                print("\nSuccess! RFP status changed to 'analyzed'.")
                
                # Fetch structured analysis
                response = await client.get(f"{base_url}/rfp/{session_id}/analysis")
                analysis_result = response.json()
                print("\nExtracted RFP Analysis Results:")
                import pprint
                pprint.pprint(analysis_result)
                return
            elif status == "analysis_failed":
                print("Error: Analysis failed on backend worker.")
                return
                
            await asyncio.sleep(3)
            
        print("Timeout: Analysis did not complete within 60 seconds.")

if __name__ == "__main__":
    asyncio.run(main())
