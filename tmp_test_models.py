import os
import requests

headers = {
    'Content-Type': 'application/json',
    'x-api-key': os.environ['ANTHROPIC_AUTH_TOKEN'],
    'anthropic-version': '2023-06-01'
}

base = {
    'model': 'deepseek-v4-flash',
    'max_tokens': 200,
    'messages': [{'role': 'user', 'content': 'say hello'}],
    'stream': False
}

tests = []

# Test 1: nothing special - baseline
tests.append(('Baseline (no thinking at all)', {**base}))

# Test 2: thinking disabled
tests.append(('thinking disabled', {**base, 'thinking': {'type': 'disabled'}}))

# Test 3: system string + thinking disabled
tests.append(('system string + thinking disabled', {**base, 'thinking': {'type': 'disabled'}, 'system': 'You are a helpful assistant.'}))

# Test 4: system array + thinking disabled
tests.append(('system array + thinking disabled', {**base, 'thinking': {'type': 'disabled'}, 'system': [{'type': 'text', 'text': 'You are a helpful assistant.'}]}))

# Test 5: with tool_choice + thinking disabled
tests.append(('tool_choice + thinking disabled', {**base, 'thinking': {'type': 'disabled'}, 'tool_choice': {'type': 'auto'}}))

# Test 6: thinking disabled + metadata
tests.append(('thinking disabled + metadata', {**base, 'thinking': {'type': 'disabled'}, 'metadata': {'user_id': 'test'}}))

# Test 7: thinking enabled
tests.append(('thinking enabled', {**base, 'thinking': {'type': 'enabled', 'budget_tokens': 200}, 'max_tokens': 500}))

# Test 8: with system array + cache control + thinking disabled
tests.append(('system cache + thinking disabled', {
    **base, 'thinking': {'type': 'disabled'},
    'system': [{'type': 'text', 'text': 'You are a helpful assistant.', 'cache_control': {'type': 'ephemeral'}}]
}))

# Test 9: thinking disabled + reasoning_effort explicit
tests.append(('thinking disabled + reasoning_effort', {**base, 'thinking': {'type': 'disabled'}, 'reasoning_effort': 'medium'}))

# Test 10: reasoning_effort only
tests.append(('reasoning_effort only', {**base, 'reasoning_effort': 'medium'}))

# Run all tests
for label, body in tests:
    try:
        r = requests.post('https://api-slb.packyapi.com/v1/messages', headers=headers, json=body, timeout=15)
        status = r.status_code
        if status == 200:
            data = r.json()
            content_type = data['content'][0]['type'] if data.get('content') else '?'
            print(f'  [OK] {label}: HTTP {status} [{content_type}]')
        else:
            err = r.text[:150].replace('\n', ' ')
            print(f'  [FAIL] {label}: HTTP {status} - {err}')
    except Exception as e:
        print(f'  [FAIL] {label}: {type(e).__name__} - {str(e)[:100]}')

print('\nDone.')
