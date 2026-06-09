# -*- coding: utf-8 -*-
import requests, json, sys, time
sys.stdout.reconfigure(encoding='utf-8')

def search(label, query, rows=10):
    print(f'\n=== {label} ===')
    r = requests.get('https://api.crossref.org/works', params={
        'query': query, 'rows': rows, 'sort': 'relevance'
    }, timeout=15)
    if r.status_code != 200:
        print(f'  ERROR {r.status_code}')
        return
    for item in r.json()['message']['items']:
        auth = ', '.join([(a.get('given','')+' '+a.get('family','')).strip() for a in item.get('author',[])][:3]) or 'Unknown'
        dp = item.get('published-print',{}).get('date-parts',[[None]])[0]
        yr = dp[0] if dp and dp[0] else item.get('created',{}).get('date-parts',[[None]])[0][0]
        tit = item['title'][0] if item.get('title') else 'No title'
        ven = item.get('container-title',[''])[0] if item.get('container-title') else ''
        doi = item.get('DOI','')
        print(f'  {auth} ({yr}). {tit}. {ven}  DOI:{doi}')
    time.sleep(0.5)

print('='*70)
print('SRAM PUF DEEP RESEARCH - 对比传感器瞬态PUF')
print('='*70)

# 1. SRAM PUF fundamentals
search('SRAM PUF 基本原理与IID特性', 'SRAM physical unclonable function power-up state random IID bits')

# 2. SRAM PUF reliability issues
search('SRAM PUF 可靠性问题', 'SRAM PUF reliability temperature voltage noise bit error rate')

# 3. SRAM PUF applications
search('SRAM PUF 应用场景', 'SRAM PUF application authentication key generation IoT security')

# 4. SRAM PUF vs other PUFs
search('SRAM PUF vs其他PUF对比', 'SRAM PUF comparison arbiter PUF ring oscillator PUF performance')

# 5. Sensor PUF works
search('传感器PUF相关工作', 'sensor based physical unclonable function authentication identification')

# 6. SRAM PUF limitations
search('SRAM PUF 局限性', 'SRAM PUF limitation disadvantage challenge scalability')

# 7. PUF IoT authentication real deployment
search('PUF IoT实际部署认证', 'PUF IoT device authentication real-world deployment commercial')

# 8. PUF key generation vs authentication
search('PUF密钥生成vs认证差异', 'PUF key generation authentication difference use case')

print('\nDone.')
