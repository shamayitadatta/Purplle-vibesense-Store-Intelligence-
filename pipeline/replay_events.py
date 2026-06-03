import argparse
import json
import urllib.request
import urllib.error
import sys

def main():
    parser = argparse.ArgumentParser(description="Replay events to API")
    parser.add_argument("--file", required=True, help="Path to events.jsonl")
    parser.add_argument("--api", required=True, help="API endpoint URL")
    args = parser.parse_args()

    events = []
    try:
        with open(args.file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except FileNotFoundError:
        print(f"Error: File {args.file} not found.")
        sys.exit(1)

    batch_size = 500
    batch_num = 1
    for i in range(0, len(events), batch_size):
        batch = events[i:i + batch_size]
        
        req = urllib.request.Request(
            args.api,
            data=json.dumps(batch).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                accepted = result.get("accepted", 0)
                rejected = result.get("rejected", 0)
                duplicates = result.get("duplicates", 0)
                print(f"Batch {batch_num}: accepted={accepted} rejected={rejected} duplicates={duplicates}")
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                print(f"Batch {batch_num}: HTTP Error {e.code}: {err_data}")
            except:
                print(f"Batch {batch_num}: HTTP Error {e.code}")
        except urllib.error.URLError as e:
            print(f"Batch {batch_num}: URL Error: {e.reason}")
        except Exception as e:
            print(f"Batch {batch_num}: Error: {str(e)}")
            
        batch_num += 1

if __name__ == "__main__":
    main()
