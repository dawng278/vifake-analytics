import re

def extract_prices_and_items(text):
    text = text.lower()
    # Regex patterns
    price_pattern = r'(\d+[\.,]?\d*)\s*(k|vnd|đ|đồng)'
    item_pattern = r'(\d+[\.,]?\d*)\s*(robux|rbx|kim cương|kc|quân huy|qh|uc)'
    
    prices = []
    items = []
    
    # Extract prices
    for match in re.finditer(price_pattern, text):
        val_str = match.group(1).replace('.', '').replace(',', '')
        try:
            val = float(val_str)
            unit = match.group(2)
            if unit == 'k':
                val = val * 1000
            # If number is too low (e.g. "10" without 'k' but with 'vnd'), it's usually meant as 10k on social media sometimes
            if val < 1000 and (unit == 'vnd' or unit == 'đ'):
                # Common shorthand: 10vnd = 10k vnd? Usually they write 10k. 
                # If val < 1000 we can skip unless unit is specifically VND
                pass
            prices.append({
                'val': val,
                'pos': match.span(),
                'text': match.group(0)
            })
        except: pass
        
    # Extract items
    for match in re.finditer(item_pattern, text):
        val_str = match.group(1).replace('.', '').replace(',', '')
        try:
            val = float(val_str)
            type_str = match.group(2)
            mapped_type = 'robux'
            if type_str in ['kc', 'kim cương']: mapped_type = 'kc'
            elif type_str in ['qh', 'quân huy']: mapped_type = 'qh'
            elif type_str == 'uc': mapped_type = 'uc'
            
            items.append({
                'val': val,
                'type': mapped_type,
                'pos': match.span(),
                'text': match.group(0)
            })
        except: pass
        
    return prices, items

def check_price_anomalies(text):
    prices, items = extract_prices_and_items(text)
    alerts = []
    
    # Standard thresholds per 1,000 VND
    LIMITS = {
        'robux': 40, # ~10x standard
        'kc':    100,
        'qh':    50,
        'uc':    50
    }
    
    # Loop through pairs and check physical distance (e.g., within 50 chars)
    for p in prices:
        for i in items:
            dist = abs(p['pos'][0] - i['pos'][0])
            if dist < 80: # Near each other
                effective_k = p['val'] / 1000
                if effective_k > 0:
                    ratio = i['val'] / effective_k
                    limit = LIMITS.get(i['type'], 50)
                    
                    if ratio > limit:
                        alerts.append({
                            'type': i['type'],
                            'price': p['val'],
                            'amt': i['val'],
                            'ratio': ratio,
                            'limit': limit
                        })
    return alerts

test_cases = [
    "Bảng giá: 10k được 1000 robux nha ae", # 100 ratio > 40 SCAM
    "Nạp 20.000đ nhận ngay 10.000 kim cương", # 500 ratio > 100 SCAM
    "Shop uy tín 50k = 300 robux", # 6 ratio < 40 SAFE
    "Sự kiện hot: 10k vnd có ngay 5000 uc", # 500 ratio SCAM
]

for t in test_cases:
    print(f"Text: {t}")
    a = check_price_anomalies(t)
    print(f"Anomaly: {a}\n")

