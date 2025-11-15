import json
import time

import requests


def test_sse():
    url = 'http://localhost:11011/api/state/sse'
    print('Connecting to SSE endpoint...')
    try:
        with requests.get(url, stream=True, timeout=30) as response:
            if response.status_code != 200:
                print(f'Failed to connect: {response.status_code}')
                return
            print('Connected. Listening for events...')
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        try:
                            event_data = json.loads(data_str)
                            print(f'Received event: {event_data}')
                        except json.JSONDecodeError as e:
                            print(f'Failed to parse JSON: {e}, data: {data_str}')
                    elif line_str.startswith('event: '):
                        event_type = line_str[7:]
                        print(f'Event type: {event_type}')
                    # For simplicity, just print all non-empty lines
                    else:
                        print(f'Raw line: {line_str}')
                time.sleep(0.1)  # Small delay to avoid overwhelming
    except requests.exceptions.RequestException as e:
        print(f'Request failed: {e}')
    except KeyboardInterrupt:
        print('Test interrupted by user.')


if __name__ == '__main__':
    test_sse()
