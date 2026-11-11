+++
title = "बीजक"
about = "सानो व्यवसायको बिल: सामानको विवरण, मू.अ.कर १३% (वा --pan-only, कर बिना), नम्बर सहित र अभिलेखमा दर्ता"
items = true
series = "INV"
party = "buyer"

[fields]
seller = {label = "तपाईंको व्यवसाय (वा नाम)", me = "business|name", required = true}
seller_address = {label = "त्यसको ठेगाना", me = "business_address|address"}
seller_pan = {label = "तपाईंको स्थायी लेखा नम्बर (PAN) / मू.अ.कर दर्ता नम्बर", me = "pan", required = true}
seller_phone = {label = "तपाईंको फोन", me = "phone"}
buyer = {label = "क्रेताको नाम", required = true}
buyer_address = {label = "क्रेताको ठेगाना"}
buyer_pan = {label = "क्रेताको स्थायी लेखा नम्बर, भए"}
payment = {label = "भुक्तानीको तरिका: नगद, वा बैंक र खाता नम्बर", me = "payment"}
note = {label = "बिलमुनिको एक लाइन: बिक्री भएको सामान फिर्ता हुने छैन"}
+++

# {{seller}}

| {{tax_id_label}}: {{seller_pan}}{{#seller_address}}
| {{seller_address}}{{/seller_address}}{{#seller_phone}}
| फोन: {{seller_phone}}{{/seller_phone}}

## बीजक

| बीजक नं.: {{number}}
| मिति: {{date_full}}

| क्रेताको नाम: **{{buyer}}**{{#buyer_address}}
| ठेगाना: {{buyer_address}}{{/buyer_address}}{{#buyer_pan}}
| क्रेताको स्थायी लेखा नं. (PAN): {{buyer_pan}}{{/buyer_pan}}

{{items_table}}

**अक्षरेपी:** {{total_words}}

{{#payment}}भुक्तानी: {{payment}}

{{/payment}}{{#note}}{{note}}

{{/note}}| ....................
| {{seller}} को तर्फबाट
